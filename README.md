# shellm

A lightweight [OpenClaw](https://github.com/openclaw) alternative. One base class, 11 built-in tools, extend in 15 lines.

**shellm** is a minimal CLI chat framework for tool-using LLMs. It gives any OpenAI-compatible model web search, shell access, cron scheduling, persistent memory, and chat logging -- out of the box, with zero config.

```bash
echo "Summarize today's news" | ./gpt5mini_chat.py --daemon stdin
```

## Why shellm?

| | OpenClaw | shellm |
|---|---------|--------|
| Setup | Config files, plugin system, dependencies | One Python class. `pip install openai camoufox` |
| Add a model | Write adapter, register, configure | 15 lines: subclass, set 3 attributes, done |
| Tool system | Plugin architecture | Built-in: search, shell, cron, memory, chat logs |
| Modes | Interactive | Interactive, daemon (stdin/file/socket), Telegram |
| Footprint | Heavy | ~500 lines of core code |

## Quick Start

```bash
git clone https://github.com/vikarag/shellm.git
cd shellm
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m camoufox fetch

export OPENAI_API_KEY="your-key"
./gpt5mini_chat.py
```

That's it. You're chatting with tools.

## Add Your Own Model (15 lines)

```python
#!/usr/bin/env python3
from base_chat import BaseChatClient

class MyChat(BaseChatClient):
    MODEL = "my-model-id"
    BANNER_NAME = "My Model"
    ENV_VAR = "MY_API_KEY"
    BASE_URL = "https://api.example.com/v1"  # omit for OpenAI

if __name__ == "__main__":
    MyChat().run()
```

Override `build_params()` for custom behavior (see `deepseek_chat.py` for an example).

## Built-in Tools (11)

Every model gets all of these automatically:

| Tool | What it does |
|------|-------------|
| `web_search` | DuckDuckGo search via Camoufox (headless anti-detect Firefox) |
| `read_webpage` | Fetch and read full page content from any URL |
| `run_command` | Execute shell commands (with confirmation + blocklist) |
| `cron_create` | Schedule cron jobs |
| `cron_list` | List current cron jobs |
| `cron_delete` | Remove a cron job |
| `memory_write` | Save to persistent shared memory (JSON) |
| `memory_read` | Read stored memories |
| `memory_search` | Search memories by keyword |
| `memory_delete` | Delete a memory entry |
| `chat_log_read` | Query past conversations across all models |

The model decides when to use them. Up to 10 tool-call rounds per turn.

## Run Modes

```bash
# Interactive (default)
./gpt5mini_chat.py

# Pipe a prompt
echo "What is 2+2?" | ./gpt5mini_chat.py --daemon stdin

# JSON output
echo "What is 2+2?" | ./gpt5mini_chat.py --daemon stdin --json

# Batch from file
./gpt5mini_chat.py --daemon file --input prompts.txt --output responses.txt

# Unix socket server (concurrent access)
./gpt5mini_chat.py --daemon socket --socket-path /tmp/gpt5mini.sock

# Telegram bot
export TELEGRAM_BOT_TOKEN="your-token"
./gpt5mini_chat.py --telegram
```

## Interactive Commands

| Command | Action |
|---------|--------|
| `/search <query>` | Force a web research workflow |
| `clear` | Reset conversation history |
| `quit` / `exit` | End session |

## Chat Logging

Every conversation turn is automatically saved to `chat_logs.json` with:
- Timestamp (KST/UTC+9), model name, run mode
- Full user input and assistant response
- All tool calls made during the turn
- Response duration in milliseconds

The LLM can read its own past logs via the `chat_log_read` tool.

## Architecture

```
BaseChatClient (base_chat.py, ~500 loc)
  ├── 11 built-in tools
  ├── Streaming + batch response handling
  ├── Optional reasoning/thinking display
  ├── Chat logging (chat_logs.json)
  ├── System timezone awareness (KST)
  ├── Daemon mode (daemon_mode.py)
  └── Telegram adapter (telegram_adapter.py)

Subclasses: 15-50 lines each
  ├── gpt5mini_chat.py    (OpenAI, config only)
  ├── gpt5nano_chat.py    (OpenAI, config only)
  ├── mercury2_chat.py    (Inception Labs, config only)
  ├── kimi_chat.py        (Moonshot AI, +thinking mode toggle)
  └── deepseek_chat.py    (DeepSeek, +reasoner/chat conditional logic)
```

## Included Models

| Script | Provider | Key env var |
|--------|----------|-------------|
| `gpt5mini_chat.py` | OpenAI | `OPENAI_API_KEY` |
| `gpt5nano_chat.py` | OpenAI | `OPENAI_API_KEY` |
| `deepseek_chat.py` | DeepSeek | `DEEPSEEK_API_KEY` |
| `kimi_chat.py` | Moonshot AI | `MOONSHOT_API_KEY` |
| `mercury2_chat.py` | Inception Labs | `INCEPTION_API_KEY` |

## MCP Server

`mcp_web_search_server.py` exposes web search as an MCP tool for Claude Desktop or other MCP clients:

```json
{
  "mcpServers": {
    "web-search": {
      "command": "/path/to/shellm/venv/bin/python",
      "args": ["/path/to/shellm/mcp_web_search_server.py"]
    }
  }
}
```

## License

MIT
