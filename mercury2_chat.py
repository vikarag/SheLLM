#!/home/gslee/llm-api-vault/venv/bin/python3
"""Interactive chat with Mercury-2 (Inception Labs) - maintains conversation history."""

from base_chat import BaseChatClient


class Mercury2Chat(BaseChatClient):
    MODEL = "mercury-2"
    BANNER_NAME = "Mercury-2 Chat"
    ENV_VAR = "INCEPTION_API_KEY"
    BASE_URL = "https://api.inceptionlabs.ai/v1"
    STREAM = True
    TEMPERATURE = None


if __name__ == "__main__":
    Mercury2Chat().run()
