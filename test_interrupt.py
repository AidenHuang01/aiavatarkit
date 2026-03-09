"""
Test script to verify interrupt functionality works correctly.
"""

import asyncio
import logging
from aiavatar.interrupt import InterruptHandler

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s : %(message)s'
)

logger = logging.getLogger(__name__)


async def test_interrupt():
    """Test interrupt handler"""

    handler = InterruptHandler(hotkey="<ctrl>+<space>")
    handler.start()

    logger.info("=" * 60)
    logger.info("Interrupt Handler Test")
    logger.info("=" * 60)
    logger.info("Press Ctrl+Space to test interrupt")
    logger.info("Simulating AI response generation...")
    logger.info("=" * 60)

    # Simulate LLM streaming
    sentences = [
        "这是第一句话。",
        "这是第二句话。",
        "这是第三句话。",
        "这是第四句话。",
        "这是第五句话。",
    ]

    interrupted = False

    for i, sentence in enumerate(sentences):
        # Check for interrupt
        if handler.is_interrupted():
            logger.info(f"⚡ Interrupt detected at sentence {i+1}")
            interrupted = True
            break

        logger.info(f"📝 Generating: {sentence}")
        await asyncio.sleep(1.5)  # Simulate generation time

    if interrupted:
        handler.reset()
        logger.info("🛑 Generation stopped by interrupt")
    else:
        logger.info("✅ Generation completed normally")

    handler.stop()
    logger.info("=" * 60)
    logger.info("Test completed")


if __name__ == "__main__":
    asyncio.run(test_interrupt())
