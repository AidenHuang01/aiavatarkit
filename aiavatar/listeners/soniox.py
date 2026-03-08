import asyncio
import json
from logging import getLogger, NullHandler
from typing import Dict, List, Optional
import websockets
from . import RequestListenerBase, SpeechListenerBase


class SpeakerSegment:
    """表示一个说话者的语音片段"""
    def __init__(self, speaker_id: str, text: str, start_time: float = 0.0):
        self.speaker_id = speaker_id
        self.text = text
        self.start_time = start_time


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
        device_index: int = -1,
        enable_speaker_diarization: bool = True,
        primary_speaker_strategy: str = "first"  # "first", "longest", "most_recent"
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
        self.last_speaker_segments: List[SpeakerSegment] = []
        self.on_start_listening = None
        self.ws_url = "wss://stt-rt.soniox.com/transcribe-websocket"
        self.enable_speaker_diarization = enable_speaker_diarization
        self.primary_speaker_strategy = primary_speaker_strategy

    async def on_request(self, text: str):
        self.last_recognized_text = text
        self.stop_listening()

    def select_primary_speaker(self, segments: List[SpeakerSegment]) -> Optional[str]:
        """
        从多个说话者中选择主要说话者

        策略:
        - "first": 选择第一个说话的人
        - "longest": 选择说话内容最长的人
        - "most_recent": 选择最后说话的人
        """
        if not segments:
            return None

        if self.primary_speaker_strategy == "first":
            return segments[0].text

        elif self.primary_speaker_strategy == "longest":
            # 按说话者分组，计算每个人的总文本长度
            speaker_texts: Dict[str, str] = {}
            for seg in segments:
                if seg.speaker_id not in speaker_texts:
                    speaker_texts[seg.speaker_id] = ""
                speaker_texts[seg.speaker_id] += seg.text

            # 找到说话最多的人
            longest_speaker = max(speaker_texts.items(), key=lambda x: len(x[1]))
            return longest_speaker[1]

        elif self.primary_speaker_strategy == "most_recent":
            return segments[-1].text

        return None

    async def transcribe(self, audio_data: bytes) -> str:
        """使用 Soniox WebSocket API 进行语音识别，支持说话者识别"""

        config = {
            "api_key": self.api_key,
            "model": "stt-rt-v4",
            "language_hints": [self.lang],
            "audio_format": "pcm_s16le",
            "sample_rate": self.rate,
            "num_channels": self.channels,
            "enable_endpoint_detection": False,
            "enable_speaker_diarization": self.enable_speaker_diarization,
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
                speaker_segments: List[SpeakerSegment] = []
                current_speaker = None
                current_text = ""

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
                                text = token["text"]
                                speaker = token.get("speaker")

                                final_tokens.append(token)

                                # 处理说话者切换
                                if self.enable_speaker_diarization and speaker is not None:
                                    if speaker != current_speaker:
                                        # 保存上一个说话者的内容
                                        if current_speaker is not None and current_text:
                                            speaker_segments.append(
                                                SpeakerSegment(current_speaker, current_text)
                                            )
                                        current_speaker = speaker
                                        current_text = text
                                    else:
                                        current_text += text
                                else:
                                    current_text += text

                        # 会话结束
                        if result.get("finished"):
                            # 保存最后一个说话者的内容
                            if current_speaker is not None and current_text:
                                speaker_segments.append(
                                    SpeakerSegment(current_speaker, current_text)
                                )
                            break

                    except asyncio.TimeoutError:
                        self.logger.warning("Soniox transcribe timeout")
                        break

                # 保存说话者片段信息
                self.last_speaker_segments = speaker_segments

                # 如果启用了说话者识别且有多个说话者
                if self.enable_speaker_diarization and len(speaker_segments) > 1:
                    self.logger.info(f"检测到 {len(set(s.speaker_id for s in speaker_segments))} 个说话者")
                    for seg in speaker_segments:
                        self.logger.info(f"  说话者 {seg.speaker_id}: {seg.text}")

                    # 选择主要说话者
                    primary_text = self.select_primary_speaker(speaker_segments)
                    if primary_text:
                        return primary_text

                # 如果没有启用说话者识别或只有一个说话者，返回所有文本
                if final_tokens:
                    return "".join([t["text"] for t in final_tokens])

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
