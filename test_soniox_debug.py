#!/usr/bin/env python3
"""
Test script to debug Soniox streaming recognition issues.
This will help identify why speech is detected but not recognized.
"""

import asyncio
import json
import logging
import numpy
import sounddevice
import websockets
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s : %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
from config import SONIOX_API_KEY

INPUT_DEVICE = 1  # Your audio input device
VOLUME_THRESHOLD = -50
SAMPLE_RATE = 16000
CHANNELS = 1
LANG = "zh"


def get_volume_db(data: numpy.ndarray, ref: int = 32768) -> float:
    amplitude = numpy.max(numpy.abs(data))
    if amplitude == 0:
        amplitude = 1
    return float(20 * numpy.log10(amplitude / ref))


async def test_soniox_streaming():
    """Test Soniox streaming with detailed logging"""

    ws_url = "wss://stt-rt.soniox.com/transcribe-websocket"

    logger.info("=" * 60)
    logger.info("Soniox Streaming Test")
    logger.info("=" * 60)
    logger.info(f"Device: {INPUT_DEVICE}")
    logger.info(f"Sample Rate: {SAMPLE_RATE}")
    logger.info(f"Language: {LANG}")
    logger.info(f"Volume Threshold: {VOLUME_THRESHOLD}dB")
    logger.info("=" * 60)

    try:
        async with websockets.connect(ws_url) as ws:
            # Send configuration
            config = {
                "api_key": SONIOX_API_KEY,
                "model": "stt-rt-v4",
                "language_hints": [LANG],
                "audio_format": "pcm_s16le",
                "sample_rate": SAMPLE_RATE,
                "num_channels": CHANNELS,
                "enable_endpoint_detection": False,
            }

            logger.info(f"📤 Sending config: {json.dumps(config, indent=2)}")
            await ws.send(json.dumps(config))

            # Wait for config acknowledgment
            await asyncio.sleep(0.1)

            # State variables
            is_recording = False
            silence_start_time = None
            recording_start_time = None
            audio_buffer = []
            total_bytes_sent = 0
            chunk_count = 0

            # Open audio stream
            stream = sounddevice.InputStream(
                device=INPUT_DEVICE,
                channels=CHANNELS,
                samplerate=SAMPLE_RATE,
                dtype=numpy.int16
            )
            stream.start()
            logger.info("🎧 Audio stream started")

            # Create receive task
            async def receive_results():
                message_count = 0
                all_tokens = []

                try:
                    while True:
                        message = await asyncio.wait_for(ws.recv(), timeout=10.0)
                        result = json.loads(message)
                        message_count += 1

                        logger.info(f"📥 Message #{message_count}: {json.dumps(result, ensure_ascii=False)}")

                        if result.get("error_code"):
                            logger.error(f"❌ Error: {result.get('error_code')} - {result.get('error_message')}")
                            break

                        tokens = result.get("tokens", [])
                        for token in tokens:
                            all_tokens.append(token)
                            is_final = token.get("is_final", False)
                            text = token.get("text", "")
                            logger.info(f"  🔤 Token: '{text}' (final={is_final})")

                        if result.get("finished"):
                            logger.info(f"✅ Session finished. Total messages: {message_count}, Total tokens: {len(all_tokens)}")
                            break

                except asyncio.TimeoutError:
                    logger.warning(f"⏱️  Receive timeout after {message_count} messages")
                except Exception as ex:
                    logger.error(f"❌ Receive error: {ex}")

                return all_tokens

            receive_task = asyncio.create_task(receive_results())

            try:
                logger.info("👂 Listening for speech...")

                while stream.active:
                    # Read audio chunk (50ms)
                    data, overflowed = stream.read(int(SAMPLE_RATE * 0.05))
                    if overflowed:
                        logger.warning("⚠️  Audio buffer overflow")

                    volume = get_volume_db(data)
                    current_time = time.time()

                    # Voice Activity Detection
                    if not is_recording:
                        # Waiting for speech
                        audio_buffer.append(data)
                        if len(audio_buffer) > 20:  # Keep last 1 second
                            audio_buffer.pop(0)

                        if volume > VOLUME_THRESHOLD:
                            # Speech detected
                            is_recording = True
                            recording_start_time = current_time
                            logger.info(f"🎤 Speech detected! Volume: {volume:.2f}dB")

                            # Send pre-roll
                            logger.info(f"📤 Sending {len(audio_buffer)} pre-roll chunks...")
                            for buffered_chunk in audio_buffer:
                                chunk_bytes = buffered_chunk.tobytes()
                                await ws.send(chunk_bytes)
                                total_bytes_sent += len(chunk_bytes)
                            audio_buffer.clear()
                            logger.info(f"📤 Pre-roll sent: {total_bytes_sent} bytes")

                    else:
                        # Currently recording
                        chunk_bytes = data.tobytes()
                        await ws.send(chunk_bytes)
                        total_bytes_sent += len(chunk_bytes)
                        chunk_count += 1

                        if chunk_count % 20 == 0:  # Log every 1 second
                            logger.info(f"📤 Streaming... {total_bytes_sent} bytes sent, volume: {volume:.2f}dB")

                        if volume <= VOLUME_THRESHOLD:
                            # Silence detected
                            if silence_start_time is None:
                                silence_start_time = current_time
                                logger.info(f"🔇 Silence detected at {volume:.2f}dB")
                            elif current_time - silence_start_time > 0.8:
                                # Silence timeout
                                recording_duration = current_time - recording_start_time - 0.8
                                logger.info(f"✅ Speech ended. Duration: {recording_duration:.2f}s")
                                logger.info(f"📤 Total sent: {total_bytes_sent} bytes ({total_bytes_sent/SAMPLE_RATE/2:.2f}s of audio)")
                                break
                        else:
                            # Voice detected again
                            if silence_start_time is not None:
                                logger.info(f"🔊 Voice resumed at {volume:.2f}dB")
                            silence_start_time = None

                    await asyncio.sleep(0.001)

                # Signal end of audio
                logger.info("📤 Sending end-of-stream signal")
                await ws.send("")

                # Wait for final results
                logger.info("⏳ Waiting for final results...")
                all_tokens = await asyncio.wait_for(receive_task, timeout=10.0)

                # Analyze results
                logger.info("=" * 60)
                logger.info("RESULTS ANALYSIS")
                logger.info("=" * 60)
                logger.info(f"Total tokens received: {len(all_tokens)}")

                final_tokens = [t for t in all_tokens if t.get("is_final")]
                non_final_tokens = [t for t in all_tokens if not t.get("is_final")]

                logger.info(f"Final tokens: {len(final_tokens)}")
                logger.info(f"Non-final tokens: {len(non_final_tokens)}")

                if final_tokens:
                    final_text = "".join([t.get("text", "") for t in final_tokens])
                    logger.info(f"✅ Final transcript: '{final_text}'")
                else:
                    logger.warning("⚠️  No final tokens received!")
                    if non_final_tokens:
                        non_final_text = "".join([t.get("text", "") for t in non_final_tokens])
                        logger.info(f"ℹ️  Non-final text: '{non_final_text}'")

                logger.info("=" * 60)

            finally:
                stream.stop()
                stream.close()
                if not receive_task.done():
                    receive_task.cancel()

    except Exception as ex:
        logger.error(f"❌ Test failed: {ex}", exc_info=True)


if __name__ == "__main__":
    print("\n🧪 Starting Soniox Streaming Debug Test")
    print("Speak clearly into your microphone after 'Speech detected' message\n")

    asyncio.run(test_soniox_streaming())
