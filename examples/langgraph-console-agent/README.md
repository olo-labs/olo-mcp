# LangGraph Console Agent Example

This separate Python 3.12 console project connects to the MCP server running in Docker at `http://127.0.0.1:8000/mcp`. It never imports or starts the server process itself.

It demonstrates a production-oriented LangChain/LangGraph agent boundary while staying small enough to study:

- MCP tool discovery over Streamable HTTP
- explicit tool allow-listing
- OpenAI primary and fallback models
- durable LangGraph conversation checkpoints in SQLite
- model-call, tool-call, recursion, input-size, and wall-clock limits
- model and tool retry middleware with exponential backoff
- automatic long-conversation summarization
- PII redaction/masking and API-key blocking
- deterministic prompt-injection and secret-extraction checks
- optional human approval before MCP tool calls
- structured JSON logs without prompts or secrets
- MCP startup health checks and clear failure behavior
- conversation thread IDs and a one-shot mode for scripts

No sample can provide every control required for every production threat model. This one provides layered defaults and clearly identifies what must change before an internet-facing deployment.

## Why this uses a separate virtual environment

The server uses the current MCP Python SDK 2.x. The current LangChain MCP adapter depends on the maintained MCP 1.x client. The two SDK generations interoperate over the MCP protocol, but cannot be installed together in one Python environment.

Keep the server and console agent in separate virtual environments. Docker already isolates the server side.

## Architecture

```text
Console user
    |
    v
Input and prompt-injection guardrails
    |
    v
LangChain create_agent (LangGraph runtime)
    |-- PII middleware
    |-- call limits and timeout
    |-- retry and fallback models
    |-- context summarization
    |-- SQLite checkpoints
    |-- optional human approval
    |
    v
Allow-listed LangChain MCP tools
    |
    | Streamable HTTP
    v
Docker: http://127.0.0.1:8000/mcp
    |
    +-- hello
    +-- get_current_time
    +-- calculate
```

## 1. Start the MCP server in Docker

From the repository root:

```bash
docker compose up -d
docker compose ps
curl http://127.0.0.1:8000/health
```

Expected health response:

```json
{"status":"ok"}
```

If port 8000 is already occupied, set a different port in the repository-root `.env`, then use the same port in this example's `MCP_URL`.

## 2. Create the agent's separate environment

Linux or macOS:

```bash
cd examples/langgraph-console-agent
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

Windows PowerShell:

```powershell
Set-Location examples/langgraph-console-agent
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Edit `.env` and set `OPENAI_API_KEY`. The key is read from the environment and is never logged or committed.

## 3. Run the console agent

```bash
python -m agent_app
```

Example prompts:

```text
Say hello to Rahul.
What time is it on the MCP server?
Use the calculator to multiply 25 by 12.
Divide 10 by zero and explain the error.
```

Console commands:

```text
/help   show help
/tools  show the allow-listed MCP tools
/new    start a new persisted conversation thread
/quit   exit
```

One-shot mode for scripts:

```bash
python -m agent_app --prompt "Use the calculator to multiply 25 by 12"
```

Reuse a durable conversation:

```bash
python -m agent_app --thread-id customer-demo
```

## Human approval mode

Set this in `.env`:

```env
REQUIRE_TOOL_APPROVAL=true
```

Every MCP tool call then pauses before execution. The console displays the tool name and arguments and accepts an explicit approve or reject decision. LangGraph's checkpointer is required for this pause/resume flow and is already configured.

The bundled MCP tools are read-only or deterministic, so approval is disabled by default. For destructive tools, enable approval and use per-tool risk policies rather than approving every action equally.

## Guardrail layers

1. Environment configuration is validated before network or model calls.
2. The MCP URL must be absolute and point to `/mcp`.
3. Only `ALLOWED_MCP_TOOLS` are exposed to the model; missing expected tools fail startup.
4. Empty, oversized, malformed, and obvious instruction-extraction prompts are blocked.
5. Email addresses are redacted, credit cards are masked, and OpenAI-shaped API keys are blocked across input, output, and tool results.
6. The system prompt treats tool output as untrusted data and forbids secret or hidden-reasoning disclosure.
7. Model calls, tool calls, graph recursion, and total turn time are bounded.
8. Transient model and tool failures receive bounded exponential-backoff retries.
9. A fallback model is attempted after the primary model fails.
10. Output rendering returns only the final assistant message, not internal graph state or traces.

The prompt-injection detector is intentionally small and deterministic. It is one layer, not a claim that prompt injection is solved. For higher-risk deployments add policy-specific classifiers, authorization at each tool, tenant isolation, audit storage, and adversarial evaluations.

## Persistence and privacy

Conversation checkpoints are stored at `.agent-state/checkpoints.sqlite` by default. This is durable and appropriate for a single local process. The file can contain user and model content even though PII middleware reduces common exposures.

For a scaled service, replace SQLite with the supported PostgreSQL checkpointer and define retention, encryption, backup, tenant-isolation, and deletion policies. Do not commit checkpoint files.

## Observability

Application logs are JSON and intentionally omit prompt text, tool arguments, credentials, and model responses. Optional LangSmith tracing can be enabled through the variables shown in `.env.example`; tracing may transmit conversation content, so configure its privacy and retention settings before enabling it.

## Tests

```bash
pytest
```

Tests require no OpenAI key and make no paid model calls. They cover configuration, input guardrails, tool allow-listing, and safe final-message rendering. The repository GitHub workflow runs them in an isolated virtual environment before publishing the Docker image.

## Troubleshooting

**MCP health check fails:** Confirm `docker compose ps`, call `/health`, and verify `MCP_URL` uses the same host port exposed by Docker.

**Dependency resolver tries to downgrade `mcp`:** You are installing the agent into the server's virtual environment. Create the separate `.venv` inside this example directory.

**OpenAI authentication fails:** Confirm `OPENAI_API_KEY` is set in this example's `.env` and has not been copied into the repository-root environment file.

**A prompt is blocked:** Remove secrets or injection-style instructions. For controlled security research, set `STRICT_PROMPT_GUARD=false` and use an isolated test account.

**The agent stops after several calls:** The configured model/tool-call or recursion limit prevented a runaway loop. Increase limits only after inspecting why the agent needed more calls.

**SQLite is locked:** Only run one writer against the local checkpoint file. Use a different `AGENT_CHECKPOINT_DB` per process or migrate to a production database-backed checkpointer.

## Before deploying beyond a laptop

- Add authentication and authorization to the MCP server.
- Terminate TLS at a trusted reverse proxy.
- Keep the MCP server on a private network.
- Give every tool a least-privilege, user-aware authorization check.
- Use a secrets manager rather than `.env` files.
- Replace SQLite for multi-process or multi-host deployments.
- Add rate limiting, cost budgets, tracing policies, red-team tests, and alerting.
- Pin and regularly update dependencies after compatibility and security tests.
