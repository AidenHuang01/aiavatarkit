import asyncio
import io
import wave
from aiavatar.speech.azurespeech import AzureSpeechController
from config import AZURE_SPEECH_KEY, AZURE_REGION

async def test_azure_audio():
    controller = AzureSpeechController(
        api_key=AZURE_SPEECH_KEY,
        region=AZURE_REGION,
        speaker_name="zh-CN-XiaoxiaoNeural",
        speaker_gender="Female",
        lang="zh-CN",
        device_index=19
    )

    # Download audio
    voice = controller.prefetch("こんにちは！")
    await voice.download_task

    # Save to file for inspection
    with open("test_audio.wav", "wb") as f:
        f.write(voice.audio_clip)

    # Check wave format
    with wave.open(io.BytesIO(voice.audio_clip), "rb") as f:
        print(f"Channels: {f.getnchannels()}")
        print(f"Sample width: {f.getsampwidth()}")
        print(f"Frame rate: {f.getframerate()}")
        print(f"Compression type: {f.getcomptype()}")
        print(f"Compression name: {f.getcompname()}")
        print(f"Number of frames: {f.getnframes()}")

if __name__ == "__main__":
    asyncio.run(test_azure_audio())
