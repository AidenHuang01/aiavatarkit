# STT Latency Optimization

## Problem Analysis

Looking at your logs, the STT latency is extremely high:
- **First request**: STT: 23.51s
- **Second request**: STT: 17.33s

This is caused by the **batch processing approach** in the current implementation:

### Current Flow (Batch Mode):
```
1. Wait for speech to start
2. Record entire speech
3. Wait for 0.8s silence
4. Send ALL audio to Soniox
5. Wait for complete transcription
6. Return result
```

**Total time = Recording time + Silence timeout + Network + Transcription**

---

## Solution: Streaming Recognition

I've created a new `SonioxStreamingVoiceRequestListener` that uses **real-time streaming**:

### New Flow (Streaming Mode):
```
1. Wait for speech to start
2. Stream audio chunks to Soniox IMMEDIATELY (every 50ms)
3. Receive partial results while user is still speaking
4. Wait for 0.8s silence
5. Finalize transcription
6. Return result
```

**Total time = Silence timeout + Small finalization delay (~0.5s)**

---

## Key Improvements

### 1. Parallel Processing
- **Old**: Record → Send → Transcribe (sequential)
- **New**: Record + Send + Transcribe (parallel)

### 2. Immediate Streaming
```python
# Audio is sent to Soniox as soon as it's captured
while recording:
    data = stream.read(50ms)
    await ws.send(data)  # Send immediately, don't wait
```

### 3. Real-time Results
```python
# Receive transcription tokens while user is still speaking
async def _receive_results(ws, final_transcript):
    while True:
        result = await ws.recv()
        for token in result["tokens"]:
            if token["is_final"]:
                final_transcript.append(token["text"])
```

### 4. Pre-roll Buffer
```python
# Keep 1 second of audio before speech starts
# This captures the beginning of speech more accurately
audio_buffer = []  # Last 1 second
if speech_detected:
    for chunk in audio_buffer:
        await ws.send(chunk)  # Send pre-roll
```

---

## Expected Performance

### Before (Batch Mode):
- Recording: 10-15s (user speaking)
- Silence timeout: 0.8s
- Network + Transcription: 5-10s
- **Total: 15-25s** ❌

### After (Streaming Mode):
- Recording: 10-15s (user speaking, but streaming in parallel)
- Silence timeout: 0.8s
- Finalization: 0.5-1s
- **Total: 1.3-2s** ✅

**Expected improvement: 10-20x faster!**

---

## How to Use

I've already updated `run_vrc.py` to use the streaming version:

```python
STT_SERVICE = "soniox_streaming"  # Changed from "soniox"
```

### Configuration Options:

```python
# Fast response (recommended)
STT_SERVICE = "soniox_streaming"
request_listener = SonioxStreamingVoiceRequestListener(
    api_key=SONIOX_API_KEY,
    volume_threshold=-50,      # Speech detection threshold
    silence_timeout=0.8,       # How long to wait after speech ends
    min_duration=0.3,          # Minimum speech length
    lang="zh",                 # Language
    rate=16000,
    device_index=INPUT_DEVICE
)

# Old batch mode (high latency)
STT_SERVICE = "soniox"
request_listener = SonioxVoiceRequestListener(...)

# Google Speech API (fallback)
STT_SERVICE = "google"
request_listener = None
```

---

## Testing

Run your script again and you should see:
```
📊 [TIMING] STT: 1.5s | TTFT: 0.66s | TTS: 0.09s
```

Instead of:
```
📊 [TIMING] STT: 23.51s | TTFT: 0.66s | TTS: 0.09s
```

---

## Technical Details

### WebSocket Connection
```python
ws_url = "wss://stt-rt.soniox.com/transcribe-websocket"
```

### Audio Streaming
- Chunk size: 50ms (800 samples at 16kHz)
- Format: PCM 16-bit little-endian
- Immediate send: No buffering delay

### Voice Activity Detection
- Pre-roll: 1 second buffer before speech
- Detection: Volume > -50dB
- End detection: 0.8s continuous silence

### Error Handling
- WebSocket timeout: 5s
- Finalization timeout: 3s
- Automatic reconnection on errors

---

## Troubleshooting

### If latency is still high:

1. **Check network latency**:
   ```bash
   ping stt-rt.soniox.com
   ```

2. **Reduce silence timeout**:
   ```python
   silence_timeout=0.5  # Faster, but may cut off speech
   ```

3. **Adjust volume threshold**:
   ```python
   volume_threshold=-45  # More sensitive (may pick up noise)
   volume_threshold=-55  # Less sensitive (may miss quiet speech)
   ```

4. **Check audio device**:
   ```python
   import sounddevice
   print(sounddevice.query_devices())
   ```

---

## Files Changed

1. **Created**: `aiavatar/listeners/soniox_streaming.py` - New streaming listener
2. **Modified**: `run_vrc.py` - Updated to use streaming mode by default

The old batch mode is still available if you need it by setting `STT_SERVICE = "soniox"`.
