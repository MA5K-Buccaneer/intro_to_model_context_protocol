import json
import uuid

from openai import OpenAI
from anthropic.types import Message, TextBlock, ToolUseBlock


class OpenAICompatLLM:
    """Drop-in replacement for core.claude.Claude that talks to any
    OpenAI-compatible API (Gemini, Groq, OpenRouter, Ollama, ...).

    The rest of the app keeps using Anthropic-style messages and tools;
    this class translates them on the way out and back.
    """

    def __init__(self, model: str, base_url: str, api_key: str):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        # Provider-specific data attached to tool calls (e.g. Gemini's
        # thought_signature) that must be sent back on the next request
        self._tool_call_extras: dict[str, dict] = {}

    def add_user_message(self, messages: list, message):
        user_message = {
            "role": "user",
            "content": message.content
            if isinstance(message, Message)
            else message,
        }
        messages.append(user_message)

    def add_assistant_message(self, messages: list, message):
        assistant_message = {
            "role": "assistant",
            "content": message.content
            if isinstance(message, Message)
            else message,
        }
        messages.append(assistant_message)

    def text_from_message(self, message: Message):
        return "\n".join(
            [block.text for block in message.content if block.type == "text"]
        )

    def chat(
        self,
        messages,
        system=None,
        temperature=1.0,
        stop_sequences=[],
        tools=None,
        thinking=False,
        thinking_budget=1024,
    ) -> Message:
        # thinking / thinking_budget are Claude-specific and ignored here
        params = {
            "model": self.model,
            "max_tokens": 8000,
            "messages": _to_openai_messages(
                messages, system, self._tool_call_extras
            ),
            "temperature": temperature,
        }

        if stop_sequences:
            params["stop"] = stop_sequences

        if tools:
            params["tools"] = [_to_openai_tool(t) for t in tools]

        response = self.client.chat.completions.create(**params)
        return _to_anthropic_message(
            response, self.model, self._tool_call_extras
        )


def _get(block, key, default=None):
    if isinstance(block, dict):
        return block.get(key, default)
    return getattr(block, key, default)


def _to_openai_messages(
    messages: list, system=None, tool_call_extras: dict | None = None
) -> list[dict]:
    tool_call_extras = tool_call_extras or {}
    result = []
    if system:
        result.append({"role": "system", "content": system})

    for message in messages:
        role = message["role"]
        content = message["content"]

        if isinstance(content, str):
            result.append({"role": role, "content": content})
            continue

        texts = []
        tool_calls = []
        tool_results = []
        for block in content:
            block_type = _get(block, "type")
            if block_type == "text":
                texts.append(_get(block, "text", ""))
            elif block_type == "tool_use":
                tool_call = {
                    "id": _get(block, "id"),
                    "type": "function",
                    "function": {
                        "name": _get(block, "name"),
                        "arguments": json.dumps(_get(block, "input", {})),
                    },
                }
                if tool_call["id"] in tool_call_extras:
                    tool_call["extra_content"] = tool_call_extras[tool_call["id"]]
                tool_calls.append(tool_call)
            elif block_type == "tool_result":
                tool_results.append(
                    {
                        "role": "tool",
                        "tool_call_id": _get(block, "tool_use_id"),
                        "content": str(_get(block, "content", "")),
                    }
                )

        if role == "assistant":
            assistant_message = {"role": "assistant", "content": "\n".join(texts)}
            if tool_calls:
                assistant_message["tool_calls"] = tool_calls
            result.append(assistant_message)
        else:
            # Tool results must directly follow the assistant tool call
            result.extend(tool_results)
            if texts:
                result.append({"role": "user", "content": "\n".join(texts)})

    return result


def _clean_schema(schema):
    """Strip JSON-schema keys some providers (e.g. Gemini) reject."""
    if isinstance(schema, list):
        return [_clean_schema(s) for s in schema]
    if not isinstance(schema, dict):
        return schema

    cleaned = {}
    for key, value in schema.items():
        if key in ("title", "$schema"):
            continue
        if key == "properties" and isinstance(value, dict):
            cleaned[key] = {name: _clean_schema(s) for name, s in value.items()}
        else:
            cleaned[key] = _clean_schema(value)
    return cleaned


def _to_openai_tool(tool: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description") or "",
            "parameters": _clean_schema(tool["input_schema"]),
        },
    }


def _to_anthropic_message(
    response, model: str, tool_call_extras: dict
) -> Message:
    choice = response.choices[0]
    content = []

    if choice.message.content:
        content.append(TextBlock(type="text", text=choice.message.content))

    for tool_call in choice.message.tool_calls or []:
        tool_call_id = tool_call.id or f"call_{uuid.uuid4().hex}"
        extra_content = getattr(tool_call, "extra_content", None)
        if extra_content:
            tool_call_extras[tool_call_id] = extra_content
        content.append(
            ToolUseBlock(
                type="tool_use",
                id=tool_call_id,
                name=tool_call.function.name,
                input=json.loads(tool_call.function.arguments or "{}"),
            )
        )

    if choice.message.tool_calls:
        stop_reason = "tool_use"
    elif choice.finish_reason == "length":
        stop_reason = "max_tokens"
    else:
        stop_reason = "end_turn"

    usage = response.usage
    return Message(
        id=response.id or f"msg_{uuid.uuid4().hex}",
        type="message",
        role="assistant",
        model=model,
        content=content,
        stop_reason=stop_reason,
        usage={
            "input_tokens": usage.prompt_tokens if usage else 0,
            "output_tokens": usage.completion_tokens if usage else 0,
        },
    )
