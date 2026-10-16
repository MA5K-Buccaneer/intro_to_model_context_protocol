# MCP Chat

MCP Chat is a command-line chat app that talks to an LLM and gives it access to documents, tools and prompts served over the MCP (Model Context Protocol). It supports document retrieval with `@`, slash commands backed by MCP prompts, and extra MCP servers passed on the command line.

This version is built on **MCP Python SDK v2** and can use either:

- **Claude** through the Anthropic API, or
- **any OpenAI-compatible API**: Google Gemini, Groq, OpenRouter, Ollama, and others (several have free tiers).

## Prerequisites

- Python 3.10+
- An API key for one of the following:
  - an OpenAI-compatible provider (for example a free Gemini key from https://aistudio.google.com/apikey), or
  - Anthropic

## Setup

### Step 1: Configure the environment variables

Your API key goes in a file named `.env` in the project root, next to `main.py`:

```
intro_to_model_context_protocol/
├── .env          <-- put your API key here
├── main.py
├── mcp_server.py
└── ...
```

Create the file if it doesn't exist. `main.py` loads it on startup, so you don't need to export anything in your shell. Which variable holds the key depends on the provider:

- **OpenAI-compatible provider** (Gemini, Groq, OpenRouter, Ollama): `LLM_API_KEY`
- **Claude**: `ANTHROPIC_API_KEY`

The provider is chosen like this: if `LLM_BASE_URL` is set, the app uses the OpenAI-compatible API; otherwise it uses Claude.

Keep `.env` out of version control (add it to `.gitignore`), since it contains your secret key.

#### Option A: OpenAI-compatible API

```
LLM_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai/"
LLM_MODEL="gemini-3.5-flash-lite"
LLM_API_KEY="paste-your-key-here"
```

Other providers only need different values for these three variables:

| Provider   | `LLM_BASE_URL`                                              | `LLM_MODEL` (example)                   | Get a key                              |
| ---------- | ----------------------------------------------------------- | --------------------------------------- | -------------------------------------- |
| Gemini     | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-3.5-flash-lite`                 | https://aistudio.google.com/apikey     |
| Groq       | `https://api.groq.com/openai/v1`                            | `llama-3.3-70b-versatile`               | https://console.groq.com/keys          |
| OpenRouter | `https://openrouter.ai/api/v1`                              | any model whose name ends in `:free`    | https://openrouter.ai/keys             |
| Ollama     | `http://localhost:11434/v1`                                 | any model you have pulled locally       | not needed (set any non-empty value)   |

The model you pick must support tool calling (function calling), because the app uses tools to read and edit documents.

#### Option B: Claude (Anthropic API)

Leave `LLM_BASE_URL` empty or remove it, then set:

```
CLAUDE_MODEL=""       # A Claude model ID, for example claude-sonnet-5-5
ANTHROPIC_API_KEY="paste-your-key-here"  # From https://console.anthropic.com/settings/keys
```

#### Other settings

```
USE_UV=1  # 1 = start the MCP server with "uv run", 0 = start it with "python"
```

### Step 2: Install dependencies

#### Option 1: Setup with uv (Recommended)

[uv](https://github.com/astral-sh/uv) is a fast Python package installer and resolver.

1. Install uv, if not already installed:

```bash
pip install uv
```

2. Create a virtual environment and install dependencies from `pyproject.toml`:

```bash
uv sync
```

3. Run the project (set `USE_UV=1` in `.env`):

```bash
uv run main.py
```

#### Option 2: Setup without uv

1. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -e .
```

3. Run the project (set `USE_UV=0` in `.env`):

```bash
python main.py
```

### Connecting extra MCP servers

Any extra arguments are treated as MCP server scripts. Each one is started with `uv run <script>` and its tools are made available to the model:

```bash
uv run main.py my_other_server.py
```

## Usage

### Basic Interaction

Type your message and press Enter to chat with the model.

### Document Retrieval

Use the @ symbol followed by a document ID to include document content in your query:

```
> Tell me about @deposition.md
```

### Commands

Use the / prefix to run a prompt defined in the MCP server:

```
> /format deposition.md
```

Commands auto-complete when you press Tab.

## Upgrading from MCP SDK v1

This project was ported from MCP Python SDK v1 to v2. The changes that affect this code are:

| Area             | v1                                       | v2                                          |
| ---------------- | ---------------------------------------- | ------------------------------------------- |
| Server class     | `from mcp.server.fastmcp import FastMCP` | `from mcp.server.mcpserver import MCPServer` |
| Prompt helpers   | `mcp.server.fastmcp.prompts.base`        | `mcp.server.mcpserver.prompts.base`         |
| Field names      | camelCase (`inputSchema`, `isError`, `mimeType`) | snake_case (`input_schema`, `is_error`, `mime_type`) |

## Using an OpenAI-compatible provider

`core/openai_compat.py` defines `OpenAICompatLLM`, a drop-in replacement for `core/claude.py`'s `Claude` class with the same methods. The rest of the app still works with Anthropic-style messages and tools. `OpenAICompatLLM` translates them in both directions:

- messages, `tool_use` and `tool_result` blocks become OpenAI chat messages and `tool_calls`;
- tool schemas have the keys some providers reject (such as `title` and `$schema`) removed;
- responses are converted back into an Anthropic `Message`;
- provider-specific data on tool calls (such as Gemini's `thought_signature`) is saved and sent back on the next request.

The Claude-only `thinking` options are ignored when using an OpenAI-compatible provider.

## Development

### Adding New Documents

Edit the `mcp_server.py` file to add new documents to the `docs` dictionary.

### Implementing MCP Features

Remaining TODO in `mcp_server.py`: add a `summarize` prompt.

### Linting and Typing Check

There are no lint or type checks implemented.
