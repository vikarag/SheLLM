#!/home/gslee/llm-api-vault/venv/bin/python3
"""shellm Research Engine -- GPT-5 Mini for web research, summarization, and fact-finding."""

from base_chat import BaseChatClient


class GPT5MiniChat(BaseChatClient):
    MODEL = "gpt-5-mini"
    BANNER_NAME = "shellm Research"
    ENV_VAR = "OPENAI_API_KEY"
    STREAM = True
    TEMPERATURE = None


if __name__ == "__main__":
    GPT5MiniChat().run()
