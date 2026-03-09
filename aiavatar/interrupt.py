"""
Keyboard interrupt handler for AIAvatar.
Allows user to interrupt AI response with hotkey (Ctrl+Space by default).
"""

import asyncio
from logging import getLogger, NullHandler
from pynput import keyboard
import threading


class InterruptHandler:
    """
    Handles keyboard interrupts to stop AI response generation.
    """

    def __init__(self, hotkey: str = "<ctrl>+<space>"):
        self.logger = getLogger(__name__)
        self.logger.addHandler(NullHandler())

        self.hotkey = hotkey
        self.interrupt_requested = False
        self.listener = None
        self.listener_thread = None

    def start(self):
        """Start listening for hotkey"""
        if self.listener is not None:
            return

        def on_activate():
            self.interrupt_requested = True
            self.logger.info(f"⚡ Interrupt requested via {self.hotkey}")

        self.listener = keyboard.GlobalHotKeys({
            self.hotkey: on_activate
        })

        self.listener_thread = threading.Thread(target=self.listener.start, daemon=True)
        self.listener_thread.start()

        self.logger.info(f"⌨️  Interrupt handler started. Press {self.hotkey} to interrupt AI response.")

    def stop(self):
        """Stop listening for hotkey"""
        if self.listener:
            self.listener.stop()
            self.listener = None
            self.listener_thread = None

    def is_interrupted(self) -> bool:
        """Check if interrupt was requested (without resetting)"""
        return self.interrupt_requested

    def reset(self):
        """Reset interrupt flag"""
        if self.interrupt_requested:
            self.logger.info("🔄 Interrupt flag reset")
        self.interrupt_requested = False

    def check_and_reset(self) -> bool:
        """Check interrupt status and reset flag"""
        interrupted = self.interrupt_requested
        if interrupted:
            self.interrupt_requested = False
            self.logger.info("🛑 Interrupt flag consumed")
        return interrupted
