# Speech-to-Text (STT) Architecture Documentation

## Overview

This document explains how the Speech-to-Text (STT) system works in the AIAvatarKit when running `run_vrc.py`. The system captures audio from a specified input device, processes it to detect speech, and sends it to an STT service (Soniox or Google Speech API) for transcription.

---

## System Flow Diagram

```
┌─────────────────┐
│  Audio Device   │ (e.g., CABLE Output - VRChat audio)
│  (INPUT_DEVICE) │
└────────┬────────┘
         │ Raw audio stream (PCM 16-bit, 16kHz)
         ▼
┌─────────────────────────────────────────────────────┐
│  SonioxVoiceRequestListener / VoiceRequestListener  │
│  (inherits from SpeechListenerBase)                 │
└────────┬────────────────────────────────────────────┘
         │
         ├─► 1. Audio Capture (record_audio)
         │   ├─ Opens sounddevice.InputStream
         │   ├─ Reads audio in 0.05s chunks (50ms frames)
         │   ├─ Calculates volume (dB) for each chunk
         │   └─ Voice Activity Detection (VAD)
         │
         ├─► 2. Voice Activity Detection
         │   ├─ Monitors volume threshold (-50dB default)
         │   ├─ Detects speech start (volume > threshold)
         │   ├─ Detects speech end (silence > timeout)
         │   └─ Validates duration (min: 0.3s, max: 20s)
         │
         ├─► 3. Audio Buffer Management
         │   ├─ Buffers 100ms before speech start
         │   ├─ Continues recording during speech
         │   └─ Stops after silence timeout (0.8s)
         │
         └─► 4. Transcription (transcribe)
             ├─ Soniox: WebSocket streaming API
             │   ├─ Connects to wss://stt-rt.soniox.com
             │   ├─ Sends config + audio chunks
             │   └─ Receives real-time tokens
             │
             └─ Google: REST API
                 ├─ Base64 encodes audio
                 ├─ POST to speech.googleapis.com
                 └─ Returns transcript JSON
```

---

## Detailed Component Breakdown

### 1. Entry Point: `run_vrc.py`

**Configuration:**
```python
INPUT_DEVICE = 10   # CABLE Output (captures VRChat audio)
OUTPUT_DEVICE = 21  # CABLE Input (sends TTS to VRChat)
STT_SERVICE = "soniox"  # or "google"
```

**Initialization:**
```python
request_listener = SonioxVoiceRequestListener(
    api_key=SONIOX_API_KEY,
    volume_threshold=-50,      # dB threshold for speech detection
    timeout=0.8,               # Silence duration to stop recording
    detection_timeout=10.0,    # Max time waiting for speech
    lang="zh",                 # Language code
    rate=16000,                # Sample rate (16kHz)
    device_index=INPUT_DEVICE  # Audio input device
)

app = AIAvatar(
    request_listener=request_listener,
    input_device=INPUT_DEVICE,
    language="zh-CN",
    ...
)
```

---

### 2. Audio Capture Pipeline

#### 2.1 Starting the Listening Loop

**File:** `aiavatar/bot.py:137-242`

When `app.start_chat()` is called:
1. Enters the main chat loop
2. Calls `request_listener.get_request()` (line 162)
3. Waits for audio input and transcription

**File:** `aiavatar/listeners/soniox.py:107-114`

```python
async def get_request(self):
    await self.start_listening()  # Start audio capture
    resp = self.last_recognized_text
    self.last_recognized_text = None
    return resp
```

---

#### 2.2 Audio Recording with Voice Activity Detection (VAD)

**File:** `aiavatar/listeners/__init__.py:95-174`

The `record_audio()` method implements a sophisticated VAD system:

**Step 1: Open Audio Stream**
```python
stream = sounddevice.InputStream(
    device=device_index,        # INPUT_DEVICE (10)
    channels=1,                 # Mono audio
    samplerate=16000,           # 16kHz
    dtype=numpy.int16           # 16-bit PCM
)
```

**Step 2: Process Audio in Real-Time**
```python
while stream.active:
    # Read 50ms chunks (0.05s * 16000 = 800 samples)
    data, overflowed = stream.read(int(self.rate * 0.05))

    # Calculate volume in decibels
    volume = self.get_volume_db(data)

    # Voice Activity Detection logic...
```

**Step 3: Voice Activity Detection States**

```
State Machine:
┌──────────────┐
│   WAITING    │ (not recording)
│ volume < -50 │
└──────┬───────┘
       │ volume > -50dB
       ▼
┌──────────────┐
│  RECORDING   │ (capturing speech)
│ volume > -50 │
└──────┬───────┘
       │ volume < -50dB
       ▼
┌──────────────┐
│   SILENT     │ (waiting for timeout)
│ silence < 0.8s│
└──────┬───────┘
       │ silence > 0.8s
       ▼
┌──────────────┐
│     STOP     │ (return audio buffer)
└──────────────┘
```

**Key Parameters:**
- `volume_threshold`: -50dB (speech detection threshold)
- `timeout`: 0.8s (silence duration to stop)
- `min_duration`: 0.3s (minimum speech length)
- `max_duration`: 20s (maximum recording length)
- `detection_timeout`: 10s (max wait for any speech)

**Step 4: Audio Buffer Management**
```python
if not is_recording:
    if volume > self.volume_threshold:
        # Keep last 100ms before speech start
        audio_data = audio_data[-100:]
        is_recording = True
```

**Step 5: Return Recorded Audio**
```python
if current_time - silence_start_time > self.timeout:
    recorded_length = current_time - start_time - self.timeout
    if recorded_length >= self.min_duration:
        return b"".join(audio_data)  # Raw PCM bytes
```

---

### 3. Speech Recognition (Transcription)

#### 3.1 Soniox WebSocket API

**File:** `aiavatar/listeners/soniox.py:43-105`

**Step 1: Establish WebSocket Connection**
```python
ws_url = "wss://stt-rt.soniox.com/transcribe-websocket"
async with websockets.connect(ws_url) as ws:
```

**Step 2: Send Configuration**
```python
config = {
    "api_key": self.api_key,
    "model": "stt-rt-v4",           # Real-time model
    "language_hints": ["zh"],        # Chinese language
    "audio_format": "pcm_s16le",     # 16-bit PCM little-endian
    "sample_rate": 16000,
    "num_channels": 1,
    "enable_endpoint_detection": False
}
await ws.send(json.dumps(config))
```

**Step 3: Stream Audio Data**
```python
chunk_size = 3840  # ~240ms at 16kHz
for i in range(0, len(audio_data), chunk_size):
    chunk = audio_data[i:i + chunk_size]
    await ws.send(chunk)  # Send binary audio chunk
    await asyncio.sleep(0.01)

await ws.send("")  # Signal end of audio
```

**Step 4: Receive Transcription Results**
```python
final_tokens = []
while True:
    message = await asyncio.wait_for(ws.recv(), timeout=5.0)
    result = json.loads(message)

    # Extract final tokens
    for token in result.get("tokens", []):
        if token.get("is_final") and token.get("text"):
            final_tokens.append(token["text"])

    # Check if finished
    if result.get("finished"):
        break

return "".join(final_tokens)  # Complete transcript
```

---

#### 3.2 Google Speech API (Alternative)

**File:** `aiavatar/listeners/__init__.py:176-205`

**Step 1: Encode Audio**
```python
audio_b64 = base64.b64encode(audio_data).decode("utf-8")
```

**Step 2: Send REST Request**
```python
request_body = {
    "config": {
        "encoding": "LINEAR16",
        "sampleRateHertz": 16000,
        "languageCode": "zh-CN"
    },
    "audio": {
        "content": audio_b64
    }
}

async with session.post(
    f"https://speech.googleapis.com/v1/speech:recognize?key={api_key}",
    json=request_body
) as resp:
    j = await resp.json()
    return j["results"][0]["alternatives"][0]["transcript"]
```

---

### 4. Integration with AIAvatar Chat Loop

**File:** `aiavatar/bot.py:156-169`

```python
# Measure STT timing
stt_start_time = asyncio.get_event_loop().time()
request_text = await self.request_listener.get_request()
stt_end_time = asyncio.get_event_loop().time()

if not request_text:
    continue  # Keep listening

stt_duration = stt_end_time - stt_start_time
logger.info(f"👤 User: {request_text}")
logger.info(f"📊 [TIMING] STT: {stt_duration:.2f}s")
```

The recognized text is then:
1. Sent to the LLM (Grok/ChatGPT) for response generation
2. Streamed back to TTS (GPT-SoVITS) for speech synthesis
3. Played through OUTPUT_DEVICE to VRChat

---

## Audio Format Specifications

| Parameter | Value | Description |
|-----------|-------|-------------|
| Sample Rate | 16000 Hz | Standard for speech recognition |
| Bit Depth | 16-bit | PCM signed integer |
| Channels | 1 (Mono) | Single audio channel |
| Encoding | LINEAR16 / pcm_s16le | Raw PCM format |
| Frame Size | 800 samples | 50ms chunks (0.05s × 16kHz) |
| Chunk Size (Soniox) | 3840 bytes | ~240ms of audio |

---

## Performance Metrics

**Typical Latencies:**
- **Audio Capture**: Real-time (50ms frame processing)
- **VAD Detection**: 0.8s after speech ends (silence timeout)
- **Soniox Transcription**: 0.5-2s (streaming, depends on audio length)
- **Google Transcription**: 1-3s (batch processing)
- **Total STT Duration**: 1.5-5s (capture + transcription)

**Logged in console:**
```
📊 [TIMING] STT: 2.34s | TTFT: 0.45s | TTS: 0.12s
```

---

## Configuration Options

### Volume Threshold Calibration

**Auto-calibration** (default):
```python
auto_noise_filter_threshold=True  # Measures ambient noise
noise_margin=20.0                 # Adds 20dB to noise level
```

**Manual setting:**
```python
volume_threshold_db=-50  # Fixed threshold
```

### Language Support

**Soniox:**
```python
lang="zh"    # Chinese
lang="en"    # English
lang="ja"    # Japanese
```

**Google:**
```python
language="zh-CN"  # Chinese (Simplified)
language="en-US"  # English (US)
language="ja-JP"  # Japanese
```

---

## Error Handling

### Audio Buffer Overflow
```python
if overflowed:
    logger.warning("Audio buffer has overflowed")
```
**Cause:** System can't process audio fast enough
**Solution:** Reduce other CPU load or increase buffer size

### Detection Timeout
```python
if time.time() - last_detected_time > detection_timeout:
    logger.info(f"Voice detection timeout: {detection_timeout}")
    break
```
**Cause:** No speech detected within 10 seconds
**Solution:** Returns empty result, continues listening

### Transcription Errors
```python
if result.get("error_code"):
    logger.error(f"Soniox error: {result.get('error_message')}")
```
**Common errors:**
- Invalid API key
- Network timeout
- Unsupported audio format

---

## Debugging Tips

### 1. Check Audio Devices
```python
import sounddevice
print(sounddevice.query_devices())
```

### 2. Monitor Volume Levels
The system prints real-time volume during noise calibration:
```
Current: -45.23dB
Noise level: -52.34dB
Set volume threshold: -32dB
```

### 3. Test STT Service
Run the example:
```bash
python example/soniox.py
```

### 4. Enable Verbose Logging
```python
import logging
logging.getLogger("aiavatar").setLevel(logging.DEBUG)
```

---

## Summary

The STT system follows this complete flow:

1. **Audio Capture**: `sounddevice` reads from INPUT_DEVICE in 50ms chunks
2. **VAD Processing**: Monitors volume to detect speech start/end
3. **Buffer Management**: Collects audio data during speech activity
4. **Transcription**: Sends audio to Soniox (WebSocket) or Google (REST)
5. **Text Return**: Recognized text flows back to AIAvatar chat loop
6. **LLM Processing**: Text is sent to Grok/ChatGPT for response
7. **TTS Output**: Response is synthesized and played to OUTPUT_DEVICE

The entire pipeline is asynchronous, allowing real-time processing with minimal latency.
