import asyncio
import json
from logging import getLogger, NullHandler
from typing import Dict, List, Optional
import websockets
import sounddevice
import numpy
import time
from . import RequestListenerBase


class SpeakerSegment:
    """表示一个说话者的语音片段"""
    def __init__(self, speaker_id: str, text: str, start_time: float = 0.0):
        self.speaker_id = speaker_id
        self.text = text
        self.start_time = start_time


class SonioxVoiceRequestListener(RequestListenerBase):
    def __init__(
        self,
        api_key: str,
        volume_threshold: int = -50,
        timeout: float = 0.5,
        detection_timeout: float = 5.0,
        min_duration: float = 0.3,
        max_duration: float = 20.0,
        lang: str = "zh",
        rate: int = 16000,
        channels: int = 1,
        device_index: int = -1,
        enable_speaker_diarization: bool = False,
        primary_speaker_strategy: str = "first"
    ):
        self.logger = getLogger(__name__)
        self.logger.addHandler(NullHandler())

        self.api_key = api_key
        self.volume_threshold = volume_threshold
        self.timeout = timeout
        self.detection_timeout = detection_timeout
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.lang = lang
        self.rate = rate
        self.channels = channels
        self.device_index = device_index
        self.enable_speaker_diarization = enable_speaker_diarization
        self.primary_speaker_strategy = primary_speaker_strategy

        self.last_recognized_text = None
        self.last_speaker_segments: List[SpeakerSegment] = []
        self.on_start_listening = None
        self.ws_url = "wss://stt-rt.soniox.com/transcribe-websocket"

    def get_volume_db(self, data: numpy.ndarray, ref: int = 32768) -> float:
        amplitude = numpy.max(numpy.abs(data))
        if amplitude == 0:
            amplitude = 1
        return float(20 * numpy.log10(amplitude / ref))

    def select_primary_speaker(self, segments: List[SpeakerSegment]) -> Optional[str]:
        if not segments:
            return None

        if self.primary_speaker_strategy == "first":
            return segments[0].text
        elif self.primary_speaker_strategy == "longest":
            speaker_texts: Dict[str, str] = {}
            for seg in segments:
                if seg.speaker_id not in speaker_texts:
                    speaker_texts[seg.speaker_id] = ""
                speaker_texts[seg.speaker_id] += seg.text
            longest_speaker = max(speaker_texts.items(), key=lambda x: len(x[1]))
            return longest_speaker[1]
        elif self.primary_speaker_strategy == "most_recent":
            return segments[-1].text

        return None

    async def stream_audio_realtime(self, ws):
        """实时流式发送音频到 WebSocket"""
        stream = sounddevice.InputStream(
            device=self.device_index,
            channels=self.channels,
            samplerate=self.rate,
            dtype=numpy.int16
        )

        start_time = time.time()
        is_recording = False
        silence_start_time = time.time()
        is_silent = False
        last_detected_time = time.time()
        stream.start()

        try:
            while stream.active:
                data, overflowed = stream.read(int(self.rate * 0.05))
                if overflowed:
                    self.logger.warning("Audio buffer has overflowed")

                current_time = time.time()
                volume = self.get_volume_db(data)

                if not is_recording:
                    if volume > self.volume_threshold:
                        is_recording = True
                        start_time = current_time
                        last_detected_time = current_time
                        # 开始发送音频
                        await ws.send(data.tobytes())
                else:
                    # 发送音频数据
                    await ws.send(data.tobytes())

                    if volume <= self.volume_threshold:
                        if is_silent:
                            if current_time - silence_start_time > self.timeout:
                                # 检测到静音结束
                                recorded_length = current_time - start_time - self.timeout
                                if recorded_length >= self.min_duration:
                                    # 发送结束信号
                                    await ws.send("")
                                    break
                                else:
                                    self.logger.info(f"Too short: {recorded_length}")
                                    is_recording = False
                        else:
                            silence_start_time = current_time
                            is_silent = True
                    else:
                        is_silent = False
                        last_detected_time = current_time

                    if current_time - start_time > self.max_duration:
                        self.logger.info(f"Max recording duration reached")
                        await ws.send("")
                        break

                if self.detection_timeout > 0 and time.time() - last_detected_time > self.detection_timeout:
                    self.logger.info(f"Voice detection timeout")
                    if is_recording:
                        await ws.send("")
                    break

        finally:
            stream.stop()
            stream.close()

    async def get_request(self):
        if self.on_start_listening:
            await self.on_start_listening()

        self.logger.info(f"Listening... ({self.__class__.__name__})")
        self.last_recognized_text = None

        config = {
            "api_key": self.api_key,
            "model": "stt-rt-v4",
            "language_hints": [self.lang],
            "audio_format": "pcm_s16le",
            "sample_rate": self.rate,
            "num_channels": self.channels,
            "enable_endpoint_detection": True,
            "enable_speaker_diarization": self.enable_speaker_diarization,
        }

        try:
            async with websockets.connect(self.ws_url) as ws:
                # 发送配置
                await ws.send(json.dumps(config))

                # 创建并行任务：发送音频和接收结果
                send_task = asyncio.create_task(self.stream_audio_realtime(ws))

                # 接收识别结果
                final_tokens = []
                speaker_segments: List[SpeakerSegment] = []
                current_speaker = None
                current_text = ""

                while True:
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        result = json.loads(message)

                        if result.get("error_code"):
                            self.logger.error(f"Soniox error: {result.get('error_code')} - {result.get('error_message')}")
                            break

                        for token in result.get("tokens", []):
                            if token.get("is_final") and token.get("text"):
                                text = token["text"]
                                speaker = token.get("speaker")
                                final_tokens.append(token)

                                if self.enable_speaker_diarization and speaker is not None:
                                    if speaker != current_speaker:
                                        if current_speaker is not None and current_text:
                                            speaker_segments.append(SpeakerSegment(current_speaker, current_text))
                                        current_speaker = speaker
                                        current_text = text
                                    else:
                                        current_text += text
                                else:
                                    current_text += text

                        if result.get("finished"):
                            if current_speaker is not None and current_text:
                                speaker_segments.append(SpeakerSegment(current_speaker, current_text))
                            break

                    except asyncio.TimeoutError:
                        # 检查发送任务是否完成
                        if send_task.done():
                            # 等待最后的结果
                            await asyncio.sleep(0.5)
                            continue
                        break

                # 等待发送任务完成
                await send_task

                self.last_speaker_segments = speaker_segments

                if self.enable_speaker_diarization and len(speaker_segments) > 1:
                    self.logger.info(f"检测到 {len(set(s.speaker_id for s in speaker_segments))} 个说话者")
                    primary_text = self.select_primary_speaker(speaker_segments)
                    if primary_text:
                        return primary_text

                if final_tokens:
                    return "".join([t["text"] for t in final_tokens])

                return None

        except Exception as ex:
            self.logger.error(f"Error in Soniox: {str(ex)}")
            return None
