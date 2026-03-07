import aiohttp
from . import SpeechControllerBase, VoiceClip
from .soundplayers import SoundPlayerBase


class FishAudioSpeechController(SpeechControllerBase):
    def __init__(self, api_key: str, *, model: str="s1", base_url: str=None, device_index: int=-1, playback_margin: float=0.1, use_subprocess=True, subprocess_timeout: float=5.0, sound_player: SoundPlayerBase=None):
        super().__init__(
            base_url=base_url or "https://api.fish.audio/v1",
            device_index=device_index,
            playback_margin=playback_margin,
            use_subprocess=use_subprocess,
            subprocess_timeout=subprocess_timeout,
            sound_player=sound_player
        )
        self.api_key = api_key
        self.model = model

    async def download(self, voice: VoiceClip):
        url = f"{self.base_url}/tts"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "model": self.model
        }
        json_data = {
            "text": voice.text
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=json_data) as response:
                if response.status == 200:
                    voice.audio_clip = await response.read()
                else:
                    error_text = await response.text()
                    self.logger.error(f"Fish Audio API error: {response.status} - {error_text}")
