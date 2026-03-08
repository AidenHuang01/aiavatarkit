from logging import getLogger, NullHandler
from datetime import datetime
from typing import AsyncGenerator
from openai import AsyncClient
from . import ChatProcessor


class GrokProcessor(ChatProcessor):
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "grok-4-1-fast-non-reasoning",
        temperature: float = 0.7,
        max_tokens: int = 0,
        system_message_content: str = None,
        history_count: int = 10,
        history_timeout: float = 60.0
    ):
        self.logger = getLogger(__name__)
        self.logger.addHandler(NullHandler())

        self.api_key = api_key
        self.base_url = "https://api.x.ai/v1"
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.system_message_content = system_message_content
        self.history_count = history_count
        self.history_timeout = history_timeout
        self.histories = []
        self.last_chat_at = datetime.utcnow()
        self.on_start_processing = None

    def reset_histories(self):
        self.histories.clear()

    async def build_messages(self, text):
        messages = []

        # System message
        if self.system_message_content:
            messages.append({"role": "system", "content": self.system_message_content})

        # Histories
        messages.extend(self.histories[-1 * self.history_count:])

        # Current user message
        messages.append({"role": "user", "content": text})

        return messages

    async def chat(self, text: str) -> AsyncGenerator[str, None]:
        try:
            async_client = AsyncClient(
                api_key=self.api_key,
                base_url=self.base_url
            )

            if (datetime.utcnow() - self.last_chat_at).total_seconds() > self.history_timeout:
                self.reset_histories()

            if self.on_start_processing:
                await self.on_start_processing()

            messages = await self.build_messages(text)

            params = {
                "messages": messages,
                "model": self.model,
                "temperature": self.temperature,
                "stream": True,
            }
            if self.max_tokens:
                params["max_tokens"] = self.max_tokens

            response_text = ""
            stream = await async_client.chat.completions.create(**params)

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    response_text += content
                    yield content

            # Save to history
            if response_text:
                self.histories.append(messages[-1])
                self.histories.append({"role": "assistant", "content": response_text})

        except Exception as ex:
            self.logger.error(f"Error at chat: {str(ex)}")
            raise ex

        finally:
            self.last_chat_at = datetime.utcnow()
            if not async_client.is_closed():
                await async_client.close()
