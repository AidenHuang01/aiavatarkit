import asyncio
import json
from logging import getLogger, NullHandler
import websockets
from . import RequestListenerBase, SpeechListenerBase


class SonioxVoiceRequestListener(RequestListenerBase, SpeechListenerBase):
    def __init__(
        self,
        api_key: str,
        volume_threshold: int = -50,
        timeout: float = 0.8,
        detection_timeout: float = 10.0,
        min_duration: float = 0.3,
        max_duration: float = 20.0,
        lang: str = "zh",
        rate: int = 16000,
        channels: int = 1,
        device_index: int = -1
    ):
        super().__init__(
            api_key,
            self.on_request,
            volume_threshold,
            timeout,
            detection_timeout,
            min_duration,
            max_duration,
            lang,
            rate,
            channels,
            device_index
        )
        self.last_recognized_text = None
        self.on_start_listening = None
        self.ws_url = "wss://stt-rt.soniox.com/transcribe-websocket"

    async def on_request(self, text: str):
        self.last_recognized_text = text
        self.stop_listening()

    async def transcribe(self, audio_data: bytes) -> str:
        """使用 Soniox WebSocket API 进行语音识别"""

        config = {
            "api_key": self.api_key,
            "model": "stt-rt-v4",  # 使用标准实时模型
            "language_hints": [self.lang],  # 语言提示
            "audio_format": "pcm_s16le",
            "sample_rate": self.rate,
            "num_channels": self.channels,
            "enable_endpoint_detection": False,
        }

        try:
            async with websockets.connect(self.ws_url) as ws:
                # 发送配置
                await ws.send(json.dumps(config))

                # 分块发送音频数据
                chunk_size = 3840
                for i in range(0, len(audio_data), chunk_size):
                    chunk = audio_data[i:i + chunk_size]
                    await ws.send(chunk)
                    await asyncio.sleep(0.01)

                # 发送空字符串表示音频结束
                await ws.send("")

                # 接收识别结果
                final_tokens = []

                while True:
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=5.0)
                        result = json.loads(message)

                        # 检查错误
                        if result.get("error_code"):
                            self.logger.error(f"Soniox error: {result.get('error_code')} - {result.get('error_message')}")
                            break

                        # 提取 final tokens
                        for token in result.get("tokens", []):
                            if token.get("is_final") and token.get("text"):
                                final_tokens.append(token["text"])

                        # 会话结束
                        if result.get("finished"):
                            break

                    except asyncio.TimeoutError:
                        self.logger.warning("Soniox transcribe timeout")
                        break

                # 组合所有 final tokens
                if final_tokens:
                    return "".join(final_tokens)

                return None

        except Exception as ex:
            self.logger.error(f"Error in Soniox transcribe: {str(ex)}")
            return None

    async def get_request(self):
        if self.on_start_listening:
            await self.on_start_listening()

        await self.start_listening()
        resp = self.last_recognized_text
        self.last_recognized_text = None
        return resp
