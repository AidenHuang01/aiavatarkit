# Keyboard Interrupt Feature

## Overview

I've added a keyboard interrupt feature that allows you to stop AI response generation and audio playback at any time by pressing **Ctrl+Space**.

## What Was Added

### 1. New Interrupt Handler (`aiavatar/interrupt.py`)
- Listens for keyboard hotkey in background thread
- Uses `pynput` library for global hotkey detection
- Default hotkey: `Ctrl+Space`

### 2. Updated AIAvatar (`aiavatar/bot.py`)
- Added `enable_interrupt` parameter (default: True)
- Added `interrupt_hotkey` parameter (default: `<ctrl>+<space>`)
- Checks for interrupt during LLM response streaming
- Cancels avatar task and stops TTS playback when interrupted

### 3. Updated Speech Controller (`aiavatar/speech/__init__.py`)
- Added `stop()` method to cancel current playback
- Tracks current playback task for cancellation

### 4. Updated run_vrc.py
- Enabled interrupt feature by default
- Shows hotkey info on startup

## Installation

You need to install the `pynput` library:

```bash
pip install pynput
```

## Usage

### Default Behavior
```python
app = AIAvatar(
    enable_interrupt=True,  # Enabled by default
    interrupt_hotkey="<ctrl>+<space>",  # Default hotkey
    ...
)
```

### Custom Hotkey
```python
# Use Ctrl+C
app = AIAvatar(
    interrupt_hotkey="<ctrl>+c",
    ...
)

# Use Ctrl+Shift+Q
app = AIAvatar(
    interrupt_hotkey="<ctrl>+<shift>+q",
    ...
)

# Use Alt+X
app = AIAvatar(
    interrupt_hotkey="<alt>+x",
    ...
)
```

### Disable Interrupt
```python
app = AIAvatar(
    enable_interrupt=False,
    ...
)
```

## How It Works

1. **During LLM Response Generation:**
   - Checks interrupt flag every 10ms in the streaming loop
   - If interrupted, stops generating response immediately
   - Cancels avatar task to stop TTS

2. **During Audio Playback:**
   - Cancels the current playback task
   - Stops speech controller
   - Returns to listening mode

3. **Logging:**
   ```
   [INFO] ⚡ Interrupt requested via <ctrl>+<space>
   [INFO] 🔇 Audio playback stopped
   ```

## Workflow

```
User speaks → STT → LLM generates response → TTS plays audio
                                ↓
                    [Press Ctrl+Space anytime]
                                ↓
                    Stop generation + Stop audio → Return to listening
```

## Testing

Run your script:
```bash
python run_vrc.py
```

You should see:
```
--- ⚡ 按 Ctrl+Space 可随时中断 AI 回复 ---
```

While AI is responding, press **Ctrl+Space** to interrupt.

## Notes

- The interrupt is checked during LLM streaming, so there may be a small delay (up to 10ms)
- Audio playback is cancelled immediately
- The interrupt handler runs in a background thread and doesn't affect performance
- Works on Windows, macOS, and Linux

## Troubleshooting

### If pynput is not installed:
```bash
pip install pynput
```

### If hotkey doesn't work:
- Make sure the terminal/console window has focus
- Try a different hotkey combination
- Check if the hotkey is already used by another application

### On Linux, if you get permission errors:
You may need to run with appropriate permissions for keyboard monitoring, or use a different hotkey library.
