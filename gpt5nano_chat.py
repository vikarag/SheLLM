#!/home/gslee/shellm/venv/bin/python3
"""SheLLM Lightweight Engine -- GPT-5 Nano for simpler tasks in the background"""

from base_chat import BaseChatClient


class GPT5MiniChat(BaseChatClient):
    MODEL = "gpt-5-nano"
    BANNER_NAME = "SheLLM Nano"
    ENV_VAR = "OPENAI_API_KEY"
    STREAM = False
    TEMPERATURE = None


if __name__ == "__main__":
    GPT5MiniChat().run()
