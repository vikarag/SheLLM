#!/home/gslee/llm-api-vault/venv/bin/python3
"""Interactive chat with GPT-5 Nano (OpenAI) - maintains conversation history."""

from base_chat import BaseChatClient


class GPT5NanoChat(BaseChatClient):
    MODEL = "gpt-5-nano"
    BANNER_NAME = "GPT-5 Nano Chat"
    ENV_VAR = "OPENAI_API_KEY"
    STREAM = True
    TEMPERATURE = None


if __name__ == "__main__":
    GPT5NanoChat().run()
