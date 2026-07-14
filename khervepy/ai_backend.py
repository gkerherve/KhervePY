"""Multi-provider AI backend for the KhervePY assistant.

Talks to Claude (Anthropic), OpenAI, Mistral and a local Ollama server over
plain ``urllib`` — no third-party SDKs. Two operations are exposed:

* :func:`list_models` — fetch the models a provider currently offers (the
  "refresh" button), so the picker always reflects what your key can use.
* :func:`chat` — send a conversation and return the assistant's reply text.

API keys are never stored here; the caller passes them in from ``QSettings``.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import json
from urllib import error, request

ANTHROPIC_VERSION = "2023-06-01"

# System prompt that shapes the assistant into a coding helper.
SYSTEM_PROMPT = (
    "You are an expert Python coding assistant embedded in KhervePY, a "
    "lightweight IDE. Help the user write, explain and debug code. When the "
    "user shares a file, review it for mistakes and suggest concrete fixes. "
    "Prefer clear, correct, idiomatic code. Put code in fenced ``` blocks and "
    "keep prose concise."
)


class AIError(RuntimeError):
    """A provider request failed (bad key, no network, server error…)."""


# Agent system prompt + tool catalogue (used when "Agent" mode is on).
AGENT_SYSTEM_PROMPT = (
    "You are a coding agent embedded in the KhervePY IDE, working on the user's "
    "open project. You have tools to act directly: use get_open_files to see "
    "what is open, read_file to view a file, write_file to create or edit a "
    "file (always pass the FULL new file contents), and git_commit to stage all "
    "changes and commit. Prefer acting with the tools over asking the user to "
    "copy-paste. Make minimal, correct changes and briefly explain what you did."
)

AGENT_TOOLS = [
    {
        "name": "get_open_files",
        "description": "List files currently open in the editor and which is active.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "read_file",
        "description": "Read a UTF-8 text file from the project.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string",
                                    "description": "Path relative to project root"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": ("Create or overwrite a UTF-8 text file in the project. "
                        "Provide the complete new file contents."),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string",
                         "description": "Path relative to project root"},
                "content": {"type": "string",
                            "description": "The full new file contents"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "git_commit",
        "description": "Stage all changes and create a git commit.",
        "input_schema": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
    },
]


# --- provider catalogue ------------------------------------------------------
PROVIDERS: dict[str, dict] = {
    "anthropic": {
        "label": "Claude (Anthropic)",
        "needs_key": True,
        "key_url": "https://console.anthropic.com/settings/keys",
        "key_help": (
            "Sign in at console.anthropic.com → Settings → API Keys → "
            "'Create Key', then paste the key (starts with 'sk-ant-')."
        ),
        "defaults": [
            "claude-opus-4-8", "claude-sonnet-5", "claude-haiku-4-5-20251001",
        ],
    },
    "openai": {
        "label": "OpenAI (GPT)",
        "needs_key": True,
        "key_url": "https://platform.openai.com/api-keys",
        "key_help": (
            "Sign in at platform.openai.com → API keys → 'Create new secret "
            "key', then paste it (starts with 'sk-')."
        ),
        "defaults": ["gpt-4o", "gpt-4o-mini", "o1-mini"],
    },
    "mistral": {
        "label": "Mistral",
        "needs_key": True,
        "key_url": "https://console.mistral.ai/api-keys",
        "key_help": (
            "Sign in at console.mistral.ai → API Keys → 'Create new key', "
            "then paste it here."
        ),
        "defaults": ["mistral-large-latest", "mistral-small-latest",
                     "codestral-latest"],
    },
    "ollama": {
        "label": "Ollama (local, no key)",
        "needs_key": False,
        "key_url": "https://ollama.com/download",
        "key_help": (
            "Install Ollama from ollama.com and start it, then pull a model, "
            "e.g. `ollama pull llama3`. No API key is needed — it runs on your "
            "machine at localhost:11434."
        ),
        "defaults": [],
    },
}

PROVIDER_ORDER = ["anthropic", "openai", "mistral", "ollama"]
OLLAMA_HOST = "http://localhost:11434"


# --- HTTP helpers ------------------------------------------------------------
def _send(url: str, headers: dict, payload: dict | None, method: str,
          timeout: int) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    hdrs = dict(headers)
    if data is not None:
        hdrs.setdefault("content-type", "application/json")
    req = request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise AIError(_error_message(body) or f"HTTP {exc.code} {exc.reason}")
    except error.URLError as exc:
        host = url.split("/")[2] if "//" in url else url
        raise AIError(f"Cannot reach {host}: {exc.reason}")
    except (TimeoutError, ValueError) as exc:
        raise AIError(f"Request failed: {exc}")


def _error_message(body: str) -> str:
    try:
        obj = json.loads(body)
    except ValueError:
        return body[:200]
    err = obj.get("error", obj)
    if isinstance(err, dict):
        return err.get("message") or err.get("type") or ""
    return str(err)


# --- public API --------------------------------------------------------------
def list_models(provider: str, key: str, timeout: int = 30) -> list[str]:
    """Return the model ids ``provider`` currently offers for ``key``."""
    if provider == "anthropic":
        d = _send("https://api.anthropic.com/v1/models",
                  {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION},
                  None, "GET", timeout)
        return [m["id"] for m in d.get("data", [])]
    if provider == "openai":
        d = _send("https://api.openai.com/v1/models",
                  {"Authorization": f"Bearer {key}"}, None, "GET", timeout)
        ids = [m["id"] for m in d.get("data", [])]
        chat_ids = [i for i in ids
                    if i.startswith(("gpt", "o1", "o3", "o4", "chatgpt"))]
        return sorted(chat_ids or ids)
    if provider == "mistral":
        d = _send("https://api.mistral.ai/v1/models",
                  {"Authorization": f"Bearer {key}"}, None, "GET", timeout)
        return sorted({m["id"] for m in d.get("data", [])})
    if provider == "ollama":
        d = _send(f"{OLLAMA_HOST}/api/tags", {}, None, "GET", timeout)
        return [m["name"] for m in d.get("models", [])]
    raise AIError(f"Unknown provider: {provider}")


def chat(provider: str, key: str, model: str, messages: list[dict],
         system: str = SYSTEM_PROMPT, timeout: int = 120) -> str:
    """Send ``messages`` (list of ``{role, content}``) and return the reply."""
    if provider == "anthropic":
        d = _send(
            "https://api.anthropic.com/v1/messages",
            {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION},
            {"model": model, "max_tokens": 2048, "system": system,
             "messages": messages},
            "POST", timeout,
        )
        parts = [b.get("text", "") for b in d.get("content", [])
                 if b.get("type") == "text"]
        return "".join(parts).strip() or "(no response)"
    if provider in ("openai", "mistral"):
        base = ("https://api.openai.com" if provider == "openai"
                else "https://api.mistral.ai")
        d = _send(
            f"{base}/v1/chat/completions",
            {"Authorization": f"Bearer {key}"},
            {"model": model,
             "messages": [{"role": "system", "content": system}] + messages},
            "POST", timeout,
        )
        return d["choices"][0]["message"]["content"].strip()
    if provider == "ollama":
        d = _send(
            f"{OLLAMA_HOST}/api/chat", {},
            {"model": model,
             "messages": [{"role": "system", "content": system}] + messages,
             "stream": False},
            "POST", timeout,
        )
        return d["message"]["content"].strip()
    raise AIError(f"Unknown provider: {provider}")


# --- agentic tool loop -------------------------------------------------------
def run_agent(provider, key, model, messages, tool_runner, log,
              system=AGENT_SYSTEM_PROMPT, timeout=180, max_steps=8) -> str:
    """Run a tool-calling loop until the model produces a final answer.

    ``tool_runner(name, args) -> str`` executes a tool and returns its result;
    ``log(name, args, result)`` is called for each tool use (for the UI).
    """
    if provider == "anthropic":
        return _anthropic_agent(key, model, messages, system, tool_runner, log,
                                timeout, max_steps)
    if provider in ("openai", "mistral"):
        base = "https://api.openai.com" if provider == "openai" else "https://api.mistral.ai"
        return _openai_agent(base, key, model, messages, system, tool_runner,
                             log, timeout, max_steps)
    if provider == "ollama":
        return _ollama_agent(model, messages, system, tool_runner, log,
                             timeout, max_steps)
    raise AIError(f"Unknown provider: {provider}")


def _anthropic_agent(key, model, messages, system, tool_runner, log,
                     timeout, max_steps):
    url = "https://api.anthropic.com/v1/messages"
    headers = {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION}
    tools = [{"name": t["name"], "description": t["description"],
              "input_schema": t["input_schema"]} for t in AGENT_TOOLS]
    conv = [{"role": m["role"], "content": m["content"]} for m in messages]
    for _ in range(max_steps):
        d = _send(url, headers,
                  {"model": model, "max_tokens": 4096, "system": system,
                   "messages": conv, "tools": tools}, "POST", timeout)
        content = d.get("content", [])
        tool_uses = [b for b in content if b.get("type") == "tool_use"]
        text = "".join(b.get("text", "") for b in content
                       if b.get("type") == "text").strip()
        if not tool_uses:
            return text or "(no response)"
        conv.append({"role": "assistant", "content": content})
        results = []
        for tu in tool_uses:
            args = tu.get("input", {}) or {}
            out = tool_runner(tu["name"], args)
            log(tu["name"], args, out)
            results.append({"type": "tool_result", "tool_use_id": tu["id"],
                            "content": out})
        conv.append({"role": "user", "content": results})
    return "(stopped after too many tool steps)"


def _openai_agent(base, key, model, messages, system, tool_runner, log,
                  timeout, max_steps):
    url = f"{base}/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}"}
    tools = [{"type": "function", "function": {
        "name": t["name"], "description": t["description"],
        "parameters": t["input_schema"]}} for t in AGENT_TOOLS]
    conv = [{"role": "system", "content": system}]
    conv += [{"role": m["role"], "content": m["content"]} for m in messages]
    for _ in range(max_steps):
        d = _send(url, headers, {"model": model, "messages": conv,
                                 "tools": tools}, "POST", timeout)
        msg = d["choices"][0]["message"]
        calls = msg.get("tool_calls") or []
        if not calls:
            return (msg.get("content") or "").strip() or "(no response)"
        conv.append(msg)
        for call in calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except ValueError:
                args = {}
            out = tool_runner(name, args)
            log(name, args, out)
            conv.append({"role": "tool", "tool_call_id": call.get("id"),
                         "content": out})
    return "(stopped after too many tool steps)"


def _ollama_agent(model, messages, system, tool_runner, log, timeout, max_steps):
    url = f"{OLLAMA_HOST}/api/chat"
    tools = [{"type": "function", "function": {
        "name": t["name"], "description": t["description"],
        "parameters": t["input_schema"]}} for t in AGENT_TOOLS]
    conv = [{"role": "system", "content": system}]
    conv += [{"role": m["role"], "content": m["content"]} for m in messages]
    for _ in range(max_steps):
        d = _send(url, {}, {"model": model, "messages": conv, "tools": tools,
                            "stream": False}, "POST", timeout)
        msg = d.get("message", {})
        calls = msg.get("tool_calls") or []
        if not calls:
            return (msg.get("content") or "").strip() or "(no response)"
        conv.append(msg)
        for call in calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {}
            out = tool_runner(name, args)
            log(name, args, out)
            conv.append({"role": "tool", "name": name, "content": out})
    return "(stopped after too many tool steps)"
