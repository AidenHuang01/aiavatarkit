"""
Debug script to trace exactly what happens during interrupt.
"""

import asyncio
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s : %(message)s'
)

logger = logging.getLogger(__name__)


class MockAvatarController:
    def __init__(self, interrupt_handler):
        self.requests = []
        self.interrupt_handler = interrupt_handler
        self._should_stop = False

    def set_text(self, text):
        logger.info(f"📝 Queued: '{text}' (queue size: {len(self.requests) + 1})")
        self.requests.append(text)

    def set_stop(self):
        logger.info("🛑 set_stop() called")
        self.requests.append(None)

    def force_stop(self):
        logger.info(f"⚠️  force_stop() called - clearing {len(self.requests)} queued items")
        self._should_stop = True
        self.requests.clear()

    async def start(self):
        logger.info("🎬 Avatar controller started")
        while True:
            # Check interrupt
            if self._should_stop or (self.interrupt_handler and self.interrupt_handler.is_interrupted()):
                if self.interrupt_handler and self.interrupt_handler.is_interrupted():
                    logger.info("⚡ Avatar detected interrupt - force stopping")
                    self.force_stop()
                logger.info("🏁 Avatar controller stopped")
                break

            if len(self.requests) > 0:
                req = self.requests.pop(0)
                if req is None:
                    logger.info("🏁 Avatar received stop signal")
                    break

                logger.info(f"🔊 Playing: '{req}'")
                await asyncio.sleep(2.0)  # Simulate TTS playback
                logger.info(f"✅ Finished: '{req}'")
            else:
                await asyncio.sleep(0.01)


async def test_interrupt_flow():
    """Test the complete interrupt flow"""
    from aiavatar.interrupt import InterruptHandler

    handler = InterruptHandler(hotkey="<ctrl>+<space>")
    handler.start()

    avatar = MockAvatarController(handler)

    logger.info("=" * 60)
    logger.info("Interrupt Flow Test")
    logger.info("=" * 60)
    logger.info("Simulating LLM streaming response...")
    logger.info("Press Ctrl+Space to interrupt")
    logger.info("=" * 60)

    # Start avatar task
    avatar_task = asyncio.create_task(avatar.start())

    # Simulate LLM streaming
    sentences = [
        "主人，复仇的故事好刺激呀。",
        "青叶想听呢。",
        "快告诉我吧。",
        "喵，好期待哦。",
        "人家等不及了。",
    ]

    interrupted = False

    for i, sentence in enumerate(sentences):
        # Check for interrupt BEFORE processing
        if handler.is_interrupted():
            logger.info(f"⚡ Interrupt detected at sentence {i+1}")
            interrupted = True
            break

        logger.info(f"🤖 LLM generated: '{sentence}'")
        avatar.set_text(sentence)

        # Simulate streaming delay
        await asyncio.sleep(0.5)

    if interrupted:
        logger.info("🛑 Stopping avatar due to interrupt...")
        avatar.force_stop()
        if not avatar_task.done():
            avatar_task.cancel()
            try:
                await avatar_task
            except asyncio.CancelledError:
                logger.info("✅ Avatar task cancelled")
        handler.reset()
    else:
        logger.info("✅ LLM generation completed normally")
        avatar.set_stop()
        await avatar_task

    handler.stop()
    logger.info("=" * 60)
    logger.info("Test completed")


if __name__ == "__main__":
    asyncio.run(test_interrupt_flow())
