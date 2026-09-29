# Simple MCP Server

A deliberately small, production-clean learning project built with Python 3.12 and the [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk). It exposes three tools over the recommended Streamable HTTP transport, runs locally or in Docker, and publishes a multi-architecture image to Docker Hub after tests pass on `main`.

The current 2.x SDK renamed its high-level `FastMCP` class to `MCPServer`. This project uses that current API rather than the legacy v1 import.

## What this server exposes

| Tool | Inputs | Result |
| --- | --- | --- |
| `hello` | `name: string` | A greeting such as `Hello Rahul!` |
| `get_current_time` | None | ISO 8601 date/time and configured timezone |
| `calculate` | `a`, `b`, and `operation` | Inputs, operation, and numeric result |

Supported calculator operations are `add`, `subtract`, `multiply`, and `divide`. Invalid operations and division by zero become clear MCP tool errors rather than server crashes.

The endpoints are:

- MCP: `http://localhost:8000/mcp`
- Health: `http://localhost:8000/health`

## How MCP works

MCP (Model Context Protocol) is a standard way for an AI application to discover and call capabilities exposed by another process or service.

```text
User
 |
 v
AI / MCP Client
 |
 | asks what tools are available
 v
MCP Server
 |
 +-- hello()
 |
 +-- get_current_time()
 |
 +-- calculate()
 |
 v
Tool result
 |
 v
AI
 |
 v
User
```

### Core concepts

**MCP client:** The MCP-speaking part of an application or model host. It connects to a server, discovers capabilities, sends calls, and receives results.

**MCP server:** The service in this repository. It advertises capabilities and executes valid requests.

**Tool:** A function the model may choose to call, such as `calculate`.

**Tool schema:** The machine-readable description of a tool's parameters and return shape. The SDK generates it from the Python type hints and docstring.

**Tool call:** A client's request to execute a named tool with specific arguments.

**Tool result:** The text or structured data returned to the client after execution.

### Tool discovery

When a client connects, it asks the server what it can do:

```text
Client
   |
   | Connect
   v
MCP Server
   |
   | Advertise tools
   v
hello
get_current_time
calculate
```

For the user question `What is 25 * 12?`, a model may choose this call:

```text
calculate(a=25, b=12, operation="multiply")
```

The MCP result includes:

```json
{
  "a": 25,
  "b": 12,
  "operation": "multiply",
  "result": 300
}
```

The model can then answer: `25 × 12 = 300`.

## Project structure

```text
simple-mcp-server/
├── .github/
│   └── workflows/
│       └── docker-publish.yml
├── app/
│   ├── __init__.py
│   └── server.py
├── tests/
│   ├── integration/
│   │   ├── test_http_server.py
│   │   └── test_mcp_in_process.py
│   └── unit/
│       ├── test_config.py
│       └── test_tools.py
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile
├── LICENSE
├── README.md
├── docker-compose.yml
├── requirements-dev.txt
└── requirements.txt
```

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `TZ` | `Asia/Kolkata` | IANA timezone used by `get_current_time` |
| `MCP_HOST` | `0.0.0.0` | HTTP bind address |
| `MCP_PORT` | `8000` | HTTP listen port |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` |

Copy the example when using Docker's `--env-file` or Docker Compose:

```bash
cp .env.example .env
```

PowerShell equivalent:

```powershell
Copy-Item .env.example .env
```

The application has safe defaults, so an `.env` file is not required. Python does not automatically load `.env`; export or set variables in the shell if changing them for a non-Docker run.

## Run locally with Python

Python 3.12 is recommended.

Linux or macOS:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
pytest
python -m app.server
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
pytest
python -m app.server
```

The logs show startup, host, port, tool calls, and major errors in the console. Stop the server with `Ctrl+C`.

## Connecting an MCP Client

For a local server, connect a Streamable HTTP compatible MCP client to:

```text
http://localhost:8000/mcp
```

A remote deployment behind TLS and a reverse proxy might use:

```text
https://mcp.example.com/mcp
```

The `/mcp` path is the actual default exposed by the official SDK. It is a protocol endpoint, not a normal webpage; opening it directly in a browser may show a method or protocol error.

This minimal Python client discovers and calls the tools:

```python
import asyncio

from mcp import Client


async def main() -> None:
    async with Client("http://localhost:8000/mcp") as client:
        tools = await client.list_tools()
        print([tool.name for tool in tools.tools])

        result = await client.call_tool(
            "calculate",
            {"a": 25, "b": 12, "operation": "multiply"},
        )
        if result.is_error:
            print(result.content)
        else:
            print(result.structured_content)


asyncio.run(main())
```

Expected tool list:

```text
['hello', 'get_current_time', 'calculate']
```

## Tests

Install development dependencies and run:

```bash
pytest
```

Run only fast unit tests:

```bash
pytest tests/unit
```

Run only integration tests:

```bash
pytest -m integration
```

The unit suite covers greeting validation, all calculator operations and errors, timezone behavior, and environment configuration. The integration suite checks generated tool schemas, in-memory MCP discovery and calls, expected MCP error results, the ASGI health route, and a real Streamable HTTP server subprocess on a temporary port. The GitHub workflow runs the complete suite before the image publishing job can start.

## Docker

### Build and run locally

```bash
docker build -t simple-mcp-server .
docker run --rm \
  --name simple-mcp-server \
  -p 8000:8000 \
  --env-file .env \
  simple-mcp-server
```

PowerShell uses backticks for multiline commands, or run the same `docker run` command on one line.

The image uses `python:3.12-slim`, installs runtime dependencies only, and runs as the unprivileged user `appuser`. Python output is unbuffered so logs appear immediately.

Check health:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok"}
```

Follow logs:

```bash
docker logs -f simple-mcp-server
```

### Docker Compose

Docker Compose automatically reads a local `.env` file when present. Without one, the documented defaults are used.

```bash
docker compose up -d
docker compose logs -f
docker compose restart
docker compose down
```

The Compose service maps port `8000`, restarts unless stopped, and builds the local image as `local/simple-mcp-server:latest` unless `DOCKERHUB_USERNAME` is set.

## Pull from Docker Hub

After the workflow publishes the image:

```bash
docker pull <username>/simple-mcp-server:latest
```

Run it:

```bash
docker run -d \
  --name simple-mcp-server \
  --restart unless-stopped \
  -p 8000:8000 \
  -e TZ=Asia/Kolkata \
  <username>/simple-mcp-server:latest
```

Both `linux/amd64` and `linux/arm64` images are published in one multi-architecture manifest.

## Automatic Docker Hub Publishing

The workflow at `.github/workflows/docker-publish.yml` runs for a push or merge to `main`, can be started manually, and also supports tags shaped like `v1.0.0`.

```text
Commit / Merge to main
          ↓
GitHub Action starts
          ↓
Tests
          ↓
Docker Buildx
          ↓
Docker Hub Login
          ↓
Multi-architecture image push
          ↓
Docker Hub
```

Every successful `main` build publishes:

```text
<username>/simple-mcp-server:latest
<username>/simple-mcp-server:sha-<short-commit-sha>
```

A tag such as `v1.2.3` additionally publishes semantic tags such as `1.2.3` and `1.2`. If tests fail, the dependent publish job does not run.

### Required GitHub secrets

Create these repository secrets:

- `DOCKERHUB_USERNAME`: your Docker Hub username
- `DOCKERHUB_TOKEN`: a Docker Hub access token, not your account password

In GitHub, go to:

```text
Repository
→ Settings
→ Secrets and variables
→ Actions
→ New repository secret
```

Create a Docker Hub repository named `simple-mcp-server` under the same account. Verify workflow runs at:

```text
GitHub
→ Repository
→ Actions
→ Docker Publish
```

## First deployment checklist

1. Create a GitHub repository.
2. Create the Docker Hub repository `simple-mcp-server`.
3. Create a Docker Hub access token with permission to write to that repository.
4. Add `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` as GitHub Actions repository secrets.
5. Clone the GitHub repository and copy these project files into it, or add the desired Git remote to this repository.
6. Commit the code.
7. Push the `main` branch.
8. Open GitHub Actions and select **Docker Publish**.
9. Confirm the test job passes.
10. Confirm the multi-architecture build and publish job passes.
11. Confirm `latest` and `sha-...` appear in Docker Hub.
12. Pull with `docker pull USERNAME/simple-mcp-server:latest`.
13. Run the container and confirm `http://localhost:8000/health` returns `{"status":"ok"}`.
14. Connect an MCP client to `http://localhost:8000/mcp`.

Typical first push commands:

```bash
git add .
git commit -m "Add simple MCP server"
git push origin main
```

## Security notes

This is a learning server and intentionally has no authentication. Do not expose it directly to the public internet in this form.

- For a local-only Docker deployment, publish only on loopback: `-p 127.0.0.1:8000:8000`.
- Put remote deployments behind HTTPS, authentication, request limits, and appropriate network controls.
- The tools do not execute shell commands, access arbitrary files, or return environment variables.
- Inputs are type-checked through MCP schemas, and expected failures are returned as tool errors.
- Logs identify tool calls but do not record secrets.
- `/health` is intentionally public and contains no private data.

Authentication and authorization are sensible future additions, but are omitted here so the MCP fundamentals remain easy to study.

## Troubleshooting

**The port is already in use:** Choose another port consistently, for example `MCP_PORT=8001`, and map that port in Docker. With Compose, setting `MCP_PORT=8001` updates both sides of the mapping.

**PowerShell blocks virtual-environment activation:** Run `Set-ExecutionPolicy -Scope Process Bypass`, then retry `.venv\Scripts\Activate.ps1`, or use `.venv\Scripts\python.exe` directly.

**The server is running but `/mcp` looks broken in a browser:** That path expects MCP protocol requests. Test `/health` with `curl` or `Invoke-RestMethod`, then connect with an MCP client.

**A tool call fails:** Check `result.is_error` in the client and read the returned content. Check server logs with `docker logs -f simple-mcp-server` or `docker compose logs -f`.

**The container is unhealthy:** Run `docker inspect simple-mcp-server`, check the health log, and verify that `MCP_PORT` is a valid port. Then inspect application logs.

**Docker Hub login fails in GitHub Actions:** Confirm both secret names are exact, the username owns the target repository, and the token has write permission. Use an access token rather than the Docker Hub password.

**The image is not published:** Open the **Docker Publish** workflow. The publish job waits for tests; a failed test or build intentionally prevents a push.

**A remote hostname returns an MCP connection error:** Terminate TLS at a correctly configured reverse proxy, forward requests to the container, and add authentication before exposing the service. Verify the final client URL ends in `/mcp` and does not redirect to a different origin.

## License

MIT
