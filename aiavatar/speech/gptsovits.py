import aiohttp
from urllib.parse import urlencode
from . import SpeechControllerBase, VoiceClip
from .soundplayers import SoundPlayerBase


class GPTSoVITSSpeechController(SpeechControllerBase):
    def __init__(
        self,
        *,
        base_url: str = "http://localhost:9880",
        refer_wav_path: str,
        prompt_text: str,
        prompt_language: str = "中文",
        text_language: str = "中文",
        device_index: int = -1,
        playback_margin: float = 0.1,
        use_subprocess: bool = True,
        subprocess_timeout: float = 5.0,
        sound_player: SoundPlayerBase = None
    ):
        """
        GPT-SoVITS TTS Controller

        Args:
            base_url: API endpoint (default: http://localhost:9880)
            refer_wav_path: Path to reference audio file
            prompt_text: Text content of the reference audio
            prompt_language: Language of prompt text (default: 中文)
            text_language: Language of text to synthesize (default: 中文)
            device_index: Audio device index
            playback_margin: Playback margin in seconds
            use_subprocess: Whether to use subprocess for playback
            subprocess_timeout: Subprocess timeout in seconds
            sound_player: Custom sound player instance
        """
        super().__init__(
            base_url=base_url,
            device_index=device_index,
            playback_margin=playback_margin,
            use_subprocess=use_subprocess,
            subprocess_timeout=subprocess_timeout,
            sound_player=sound_player
        )
        self.refer_wav_path = refer_wav_path
        self.prompt_text = prompt_text
        self.prompt_language = prompt_language
        self.text_language = text_language

    async def download(self, voice: VoiceClip):
        """Download audio from GPT-SoVITS API"""
        params = {
            "refer_wav_path": self.refer_wav_path,
            "prompt_text": self.prompt_text,
            "prompt_language": self.prompt_language,
            "text": voice.text,
            "text_language": self.text_language
        }

        url = f"{self.base_url}?{urlencode(params)}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    voice.audio_clip = await response.read()
                else:
                    raise Exception(f"GPT-SoVITS API error: {response.status}")
