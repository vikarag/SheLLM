#!/home/gslee/llm-api-vault/venv/bin/python3
"""Telegram bot adapter for LLM chat clients (stub -- requires python-telegram-bot)."""

import os


class TelegramAdapter:
    """Connects a BaseChatClient to a Telegram bot interface.

    Per-chat-id session management with separate conversation history per chat.

    Supported Telegram commands:
        /clear  -- Reset conversation history
        /model  -- Show current model info
        /search <query> -- Force web search research

    Usage:
        ./gpt5mini_chat.py --telegram

    Requires:
        - TELEGRAM_BOT_TOKEN environment variable
        - pip install python-telegram-bot
    """

    def __init__(self, chat_client, bot_token=None):
        self.client = chat_client
        self.client._silent = True
        self.client._mode = "telegram"
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.sessions = {}  # chat_id -> messages list

    def get_or_create_session(self, chat_id):
        if chat_id not in self.sessions:
            self.sessions[chat_id] = []
        return self.sessions[chat_id]

    async def handle_message(self, chat_id, text):
        text = text.strip()
        if not text:
            return None

        if text == "/clear":
            self.sessions.pop(chat_id, None)
            return "Conversation cleared."

        if text == "/model":
            return self.client.format_banner()

        if text.startswith("/search "):
            query = text[8:].strip()
            if not query:
                return "Usage: /search <query>"
            text = f"/search {query}"

        messages = self.get_or_create_session(chat_id)
        answer = self.client.process_prompt(text, messages)
        return answer or "(No response)"

    def run(self):
        """Start the Telegram bot. Raises NotImplementedError until configured."""
        if not self.bot_token:
            raise NotImplementedError(
                "Telegram bot not configured.\n"
                "Set the TELEGRAM_BOT_TOKEN environment variable and install python-telegram-bot:\n"
                "  export TELEGRAM_BOT_TOKEN='your-bot-token'\n"
                "  pip install python-telegram-bot\n"
                "Then run: ./gpt5mini_chat.py --telegram"
            )

        try:
            from telegram import Update
            from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters
        except ImportError:
            raise NotImplementedError(
                "python-telegram-bot is not installed.\n"
                "Install it with: pip install python-telegram-bot"
            )

        async def _on_message(update: Update, context):
            chat_id = update.effective_chat.id
            text = update.message.text
            response = await self.handle_message(chat_id, text)
            await update.message.reply_text(response)

        async def _on_clear(update: Update, context):
            chat_id = update.effective_chat.id
            response = await self.handle_message(chat_id, "/clear")
            await update.message.reply_text(response)

        async def _on_model(update: Update, context):
            chat_id = update.effective_chat.id
            response = await self.handle_message(chat_id, "/model")
            await update.message.reply_text(response)

        app = ApplicationBuilder().token(self.bot_token).build()
        app.add_handler(CommandHandler("clear", _on_clear))
        app.add_handler(CommandHandler("model", _on_model))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_message))

        print(f"Telegram bot started (model: {self.client.MODEL})")
        app.run_polling()
