"""Interactive and one-shot console entry point."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from langchain.agents.middleware import PIIDetectionError

from agent_app.config import ConfigurationError, Settings
from agent_app.guardrails import GuardrailViolation
from agent_app.logging_config import configure_logging
from agent_app.runtime import build_runtime

logger = logging.getLogger(__name__)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LangGraph console agent using the Dockerized MCP server"
    )
    parser.add_argument("--prompt", help="Run one prompt and exit")
    parser.add_argument(
        "--thread-id",
        help="Conversation/checkpoint ID (a random ID is used by default)",
    )
    return parser.parse_args()


async def _run() -> int:
    project_directory = Path(__file__).resolve().parents[1]
    load_dotenv(project_directory / ".env")
    arguments = _arguments()

    try:
        settings = Settings.from_env()
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    configure_logging(settings.log_level)
    thread_id = arguments.thread_id or uuid4().hex

    try:
        async with build_runtime(settings) as runtime:
            print("Simple MCP LangGraph Agent")
            print(f"MCP: {settings.mcp_url}")
            print(f"Tools: {', '.join(runtime.tool_names)}")
            print(f"Thread: {thread_id}")

            if arguments.prompt:
                print(await runtime.invoke(arguments.prompt, thread_id))
                return 0

            print("Commands: /help, /tools, /new, /quit")
            while True:
                try:
                    user_input = input("\nyou> ")
                except (EOFError, KeyboardInterrupt):
                    print("\nGoodbye.")
                    return 0

                command = user_input.strip().lower()
                if command in {"/quit", "/exit"}:
                    print("Goodbye.")
                    return 0
                if command == "/help":
                    print("Ask for a greeting, current time, or calculation.")
                    print("/new starts a new persisted conversation thread.")
                    continue
                if command == "/tools":
                    print(", ".join(runtime.tool_names))
                    continue
                if command == "/new":
                    thread_id = uuid4().hex
                    print(f"Started thread {thread_id}")
                    continue

                try:
                    print(f"agent> {await runtime.invoke(user_input, thread_id)}")
                except (GuardrailViolation, PIIDetectionError) as exc:
                    print(f"Blocked by guardrail: {exc}")
                except TimeoutError:
                    logger.warning("Agent turn exceeded its timeout")
                    print("The request timed out. Try a smaller request.")
                except Exception as exc:
                    logger.error("Agent turn failed: %s", type(exc).__name__)
                    print("The agent could not complete the request. Check the logs.")
    except (ConnectionError, GuardrailViolation, TimeoutError) as exc:
        logger.error("Agent startup failed: %s", type(exc).__name__)
        print(f"Startup error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        logger.error("Agent startup failed: %s", type(exc).__name__)
        print("The agent could not start. Check the logs.", file=sys.stderr)
        return 1


def main() -> None:
    """Run the async console and return an OS-appropriate exit code."""
    raise SystemExit(asyncio.run(_run()))
