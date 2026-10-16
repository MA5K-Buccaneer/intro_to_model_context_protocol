import asyncio
import sys
import os
from dotenv import load_dotenv
from contextlib import AsyncExitStack

from mcp_client import MCPClient
from core.claude import Claude
from core.openai_compat import OpenAICompatLLM

from core.cli_chat import CliChat
from core.cli import CliApp

load_dotenv()

# OpenAI-compatible provider config (Gemini, Groq, OpenRouter, Ollama, ...)
llm_model = os.getenv("LLM_MODEL", "")
llm_base_url = os.getenv("LLM_BASE_URL", "")
llm_api_key = os.getenv("LLM_API_KEY", "")

# Anthropic Config (used only when LLM_BASE_URL is not set)
claude_model = os.getenv("CLAUDE_MODEL", "")
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")

if llm_base_url:
    assert llm_model, "Error: LLM_MODEL cannot be empty. Update .env"
    assert llm_api_key, "Error: LLM_API_KEY cannot be empty. Update .env"
else:
    assert claude_model, "Error: CLAUDE_MODEL cannot be empty. Update .env"
    assert anthropic_api_key, (
        "Error: ANTHROPIC_API_KEY cannot be empty. Update .env"
    )


async def main():
    if llm_base_url:
        claude_service = OpenAICompatLLM(
            model=llm_model, base_url=llm_base_url, api_key=llm_api_key
        )
    else:
        claude_service = Claude(model=claude_model)

    server_scripts = sys.argv[1:]
    clients = {}

    command, args = (
        ("uv", ["run", "mcp_server.py"])
        if os.getenv("USE_UV", "0") == "1"
        else ("python", ["mcp_server.py"])
    )

    async with AsyncExitStack() as stack:
        doc_client = await stack.enter_async_context(
            MCPClient(command=command, args=args)
        )
        clients["doc_client"] = doc_client

        for i, server_script in enumerate(server_scripts):
            client_id = f"client_{i}_{server_script}"
            client = await stack.enter_async_context(
                MCPClient(command="uv", args=["run", server_script])
            )
            clients[client_id] = client

        chat = CliChat(
            doc_client=doc_client,
            clients=clients,
            claude_service=claude_service,
        )

        cli = CliApp(chat)
        await cli.initialize()
        await cli.run()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
