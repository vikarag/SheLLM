# LLM API Vault

Interactive CLI chat scripts for multiple LLM providers with built-in **web search** powered by [Camoufox](https://github.com/daijro/camoufox) (anti-detect Firefox browser).

Each script maintains conversation history across turns, supports streaming, and can autonomously search the web and read full webpages when the model needs real-time information.

## Supported Models

| Script | Provider | Model | Tool Calling | Notes |
|--------|----------|-------|:---:|-------|
| `deepseek_chat.py` | DeepSeek | `deepseek-reasoner` / `deepseek-chat` | `deepseek-chat` only | Thinking mode with `deepseek-reasoner`; temperature only works with `deepseek-chat` |
| `kimi_chat.py` | Moonshot AI | `kimi-k2.5` | Yes | Thinking mode (CoT) toggle via `THINKING` flag |
| `gpt5mini_chat.py` | OpenAI | `gpt-5-mini` | Yes | |
| `gpt5nano_chat.py` | OpenAI | `gpt-5-nano` | Yes | Lightweight model |
| `mercury2_chat.py` | Inception Labs | `mercury-2` | Yes | Diffusion LLM, >1000 tok/sec |
| `mcp_web_search_server.py` | — | — | — | MCP server for web search (use with Claude Desktop etc.) |

## Features

- **Conversation memory** — chat history maintained until you type `clear`
- **Streaming** — tokens print as they arrive
- **Autonomous web search** — models decide when to search via function calling
- **Webpage reading** — models can fetch and read full page content from search results
- **Manual search** — type `/search <question>` to force a research workflow
- **Thinking mode** — visible chain-of-thought for DeepSeek Reasoner and Kimi K2.5
- **Configurable** — temperature, streaming, model selection via variables at the top of each script

## How Web Search Works

1. **Camoufox** launches a headless anti-detect Firefox browser (spoofed fingerprints, stealth mode)
2. Navigates to **DuckDuckGo Lite** — no API key required, free and unlimited
3. Parses search results (titles, URLs, snippets) and cleans redirect URLs
4. Models can also call `read_webpage` to fetch full page content from any URL
5. Up to 10 rounds of autonomous tool calls per turn, with a forced text answer fallback

## Setup

### 1. Clone and create virtual environment

```bash
git clone https://github.com/vikarag/llm-api-vault.git
cd llm-api-vault
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Install Camoufox browser binary

```bash
python -m camoufox fetch
```

### 3. Set your API keys

```bash
# Add to your ~/.bashrc or ~/.zshrc
export DEEPSEEK_API_KEY="your-key"
export MOONSHOT_API_KEY="your-key"
export OPENAI_API_KEY="your-key"
export INCEPTION_API_KEY="your-key"
```

### 4. Run any script

```bash
./deepseek_chat.py
./kimi_chat.py
./gpt5mini_chat.py
./gpt5nano_chat.py
./mercury2_chat.py
```

## Usage

### Basic chat
```
You: Explain quantum computing in simple terms
Assistant: Quantum computing uses quantum bits (qubits)...
```

### Autonomous web search (model decides to search)
```
You: What happened in the news today?
[Searching: latest news today March 2026...]
[Reading: https://apnews.com/...]
Assistant: Here's a summary of today's top stories...
```

### Manual research (`/search`)
```
You: /search relationship between Yi Seong-gye and Yi Ji-ran in Joseon founding
[Searching: Yi Seong-gye Yi Ji-ran sworn brothers Joseon founding...]
[Reading: https://namu.wiki/w/이지란...]
Assistant: Yi Ji-ran (1331-1402) was a Jurchen-born general who became...
```

### Commands
| Command | Action |
|---------|--------|
| `/search <question>` | Research a topic with web search |
| `clear` | Reset conversation history |
| `quit` / `exit` | End the session |

## MCP Server

The `mcp_web_search_server.py` provides web search as an MCP tool for use with Claude Desktop or other MCP clients.

Add to your Claude Desktop config (`~/.claude.json`):
```json
{
  "mcpServers": {
    "web-search": {
      "command": "/path/to/llm-api-vault/venv/bin/python",
      "args": ["/path/to/llm-api-vault/mcp_web_search_server.py"]
    }
  }
}
```

## Configuration

Each script has a settings block at the top:

```python
MODEL = "deepseek-chat"    # Model ID
STREAM = True              # Streaming on/off
TEMPERATURE = None         # 0.0-2.0 or None for default
THINKING = True            # (Kimi only) CoT thinking mode
```

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Chat Script    │────>│  web_search  │────>│   Camoufox      │
│  (any model)    │     │  .py module  │     │  (headless FF)  │
│                 │<────│              │<────│                 │
└─────────────────┘     └──────────────┘     └────────┬────────┘
        │                                             │
        │  tool calls                                 │
        │  (web_search / read_webpage)                v
        v                                    DuckDuckGo Lite
   LLM Provider API                         (no API key needed)
```

## License

MIT