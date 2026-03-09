import asyncio
import json
from logging import getLogger, NullHandler
import numpy
import time
import traceback
import websockets
import sounddevice
from . import RequestListenerBase


class SonioxStreamingVoiceRequestListener(RequestListenerBase):
    """
    Streaming version of Soniox STT that sends audio in real-time
    and receives transcription results while user is still speaking.
    This dramatically reduces latency compared to batch processing.
    """
    def __init__(
        self,
        api_key: str,
        volume_threshold: int = -50,
        silence_timeout: float = 0.8,
        min_duration: float = 0.3,
        lang: str = "zh",
        rate: int = 16000,
        channels: int = 1,
        device_index: int = -1
    ):
        self.logger = getLogger(__name__)
        self.logger.addHandler(NullHandler())

        self.api_key = api_key
        self.volume_threshold = volume_threshold
        self.silence_timeout = silence_timeout
        self.min_duration = min_duration
        self.lang = lang
        self.rate = rate
        self.channels = channels
        self.device_index = device_index
        self.ws_url = "wss://stt-rt.soniox.com/transcribe-websocket"

        self.is_listening = False
        self.last_recognized_text = None

    def get_volume_db(self, data: numpy.ndarray, ref: int = 32768) -> float:
        amplitude = numpy.max(numpy.abs(data))
        if amplitude == 0:
            amplitude = 1
        return float(20 * numpy.log10(amplitude / ref))

    async def stream_recognize(self) -> str:
        """
        Stream audio to Soniox in real-time and get transcription results
        while the user is still speaking.
        """
        try:
            async with websockets.connect(self.ws_url) as ws:
                # Send configuration
                # Map language codes to Soniox format
                lang_map = {
                    "zh": "cmn-Hans-CN",  # Chinese Mandarin Simplified
                    "zh-CN": "cmn-Hans-CN",
                    "en": "en",
                    "ja": "ja",
                }
                soniox_lang = lang_map.get(self.lang, self.lang)

                config = {
                    "api_key": self.api_key,
                    "model": "stt-rt-v4",
                    "language": soniox_lang,  # Use 'language' instead of 'language_hints'
                    "audio_format": "pcm_s16le",
                    "sample_rate": self.rate,
                    "num_channels": self.channels,
                    "enable_endpoint_detection": False,
                    "enable_dictation": True,  # Better for conversational speech
                }
                await ws.send(json.dumps(config))
                self.logger.info(f"📤 Sent config: {config}")

                # State variables
                is_recording = False
                silence_start_time = None
                recording_start_time = None
                audio_buffer = []
                final_transcript = []
                total_bytes_sent = 0

                # Open audio stream
                stream = sounddevice.InputStream(
                    device=self.device_index,
                    channels=self.channels,
                    samplerate=self.rate,
                    dtype=numpy.int16
                )
                stream.start()

                # Create tasks for sending and receiving
                receive_task = asyncio.create_task(self._receive_results(ws, final_transcript))

                try:
                    while stream.active:
                        # Read audio chunk (50ms)
                        data, overflowed = stream.read(int(self.rate * 0.05))
                        if overflowed:
                            self.logger.warning("Audio buffer overflow")

                        volume = self.get_volume_db(data)
                        current_time = time.time()

                        # Voice Activity Detection
                        if not is_recording:
                            # Waiting for speech to start
                            audio_buffer.append(data)
                            if len(audio_buffer) > 20:  # Keep last 1 second
                                audio_buffer.pop(0)

                            if volume > self.volume_threshold:
                                # Speech detected - start recording
                                is_recording = True
                                recording_start_time = current_time
                                self.logger.info("🎤 Speech detected, streaming to Soniox...")

                                # Send buffered audio (pre-roll)
                                for buffered_chunk in audio_buffer:
                                    chunk_bytes = buffered_chunk.tobytes()
                                    await ws.send(chunk_bytes)
                                    total_bytes_sent += len(chunk_bytes)
                                audio_buffer.clear()
                                self.logger.info(f"📤 Sent {total_bytes_sent} bytes pre-roll")

                        else:
                            # Currently recording
                            # Send audio chunk immediately to Soniox
                            chunk_bytes = data.tobytes()
                            await ws.send(chunk_bytes)
                            total_bytes_sent += len(chunk_bytes)

                            if volume <= self.volume_threshold:
                                # Silence detected
                                if silence_start_time is None:
                                    silence_start_time = current_time
                                elif current_time - silence_start_time > self.silence_timeout:
                                    # Silence timeout reached - stop recording
                                    recording_duration = current_time - recording_start_time - self.silence_timeout

                                    if recording_duration < self.min_duration:
                                        self.logger.info(f"Recording too short: {recording_duration:.2f}s")
                                        is_recording = False
                                        silence_start_time = None
                                        final_transcript.clear()
                                        total_bytes_sent = 0
                                        continue

                                    self.logger.info(f"✅ Speech ended ({recording_duration:.2f}s), finalizing...")
                                    self.logger.info(f"📤 Total audio sent: {total_bytes_sent} bytes ({total_bytes_sent/self.rate/2:.2f}s)")
                                    break
                            else:
                                # Voice detected again - reset silence timer
                                silence_start_time = None

                        await asyncio.sleep(0.001)  # Small delay to prevent CPU spinning

                    # Signal end of audio
                    self.logger.info("📤 Sending end-of-stream signal")
                    await ws.send("")

                    # Wait for final results (with timeout)
                    self.logger.info("⏳ Waiting for final transcription results...")
                    await asyncio.wait_for(receive_task, timeout=5.0)

                finally:
                    stream.stop()
                    stream.close()
                    if not receive_task.done():
                        receive_task.cancel()

                # Return final transcript
                result = "".join(final_transcript).strip()
                self.logger.info(f"📝 Final transcript: '{result}' ({len(final_transcript)} tokens)")
                return result if result else None

        except asyncio.TimeoutError:
            self.logger.warning("Soniox transcription timeout")
            return None
        except Exception as ex:
            self.logger.error(f"Error in stream_recognize: {str(ex)}\n{traceback.format_exc()}")
            return None

    async def _receive_results(self, ws, final_transcript: list):
        """
        Continuously receive transcription results from Soniox WebSocket.
        Updates final_transcript list with finalized tokens.
        """
        try:
            message_count = 0
            while True:
                message = await asyncio.wait_for(ws.recv(), timeout=5.0)
                result = json.loads(message)
                message_count += 1

                # Debug: Log all received messages
                self.logger.debug(f"📥 Soniox message #{message_count}: {result}")

                # Check for errors
                if result.get("error_code"):
                    self.logger.error(f"Soniox error: {result.get('error_code')} - {result.get('error_message')}")
                    break

                # Extract tokens (both final and non-final for debugging)
                tokens = result.get("tokens", [])
                if tokens:
                    final_tokens = [t for t in tokens if t.get("is_final")]
                    non_final_tokens = [t for t in tokens if not t.get("is_final")]

                    self.logger.info(f"🔤 Tokens: {len(final_tokens)} final, {len(non_final_tokens)} non-final")

                    # Log token details
                    for token in tokens:
                        is_final = token.get("is_final", False)
                        text = token.get("text", "")
                        self.logger.info(f"  {'✓' if is_final else '~'} '{text}' (final={is_final})")

                        if is_final and text:
                            final_transcript.append(text)

                # Check if session finished
                if result.get("finished"):
                    self.logger.info(f"✅ Soniox session finished. Total messages: {message_count}")
                    break

        except asyncio.TimeoutError:
            self.logger.warning(f"⏱️  Receive timeout after {message_count} messages")
        except Exception as ex:
            self.logger.error(f"Error receiving results: {str(ex)}\n{traceback.format_exc()}")

    async def get_request(self):
        """
        Main entry point called by AIAvatar to get user speech input.
        """
        self.logger.info("Listening... (SonioxStreamingVoiceRequestListener)")

        recognized_text = await self.stream_recognize()

        if recognized_text:
            self.logger.info(f"Recognized: {recognized_text}")
        else:
            self.logger.info("No speech recognized")

        return recognized_text
