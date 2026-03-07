#!/home/gslee/llm-api-vault/venv/bin/python3
"""Interactive chat with GPT-5 Mini (OpenAI) - maintains conversation history."""

from base_chat import BaseChatClient


class GPT5MiniChat(BaseChatClient):
    MODEL = "gpt-5-mini"
    BANNER_NAME = "GPT-5 Mini Chat"
    ENV_VAR = "OPENAI_API_KEY"
    STREAM = True
    TEMPERATURE = None


if __name__ == "__main__":
    GPT5MiniChat().run()
