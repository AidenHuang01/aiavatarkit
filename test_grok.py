import asyncio
import time
from aiavatar.processors.grok import GrokProcessor
from config import GROK_API_KEY


async def test_grok():
    print("=" * 60)
    print("Testing Grok API")
    print("=" * 60)

    # Initialize Grok processor
    grok = GrokProcessor(
        api_key=GROK_API_KEY,
        model="grok-4-1-fast-non-reasoning",
        temperature=0.7,
        max_tokens=512,
    )

    test_message = "你好你好"
    print(f"\n📤 Sending message: {test_message}")

    # Timing variables
    start_time = time.time()
    first_token_time = None
    response_text = ""

    print("\n⏱️  Waiting for response...\n")

    try:
        async for chunk in grok.chat(test_message):
            if first_token_time is None:
                first_token_time = time.time()
                ttft = first_token_time - start_time
                print(f"✅ First token received in {ttft:.3f}s")
                print(f"\n📥 Response: ", end="", flush=True)

            response_text += chunk
            print(chunk, end="", flush=True)

        end_time = time.time()
        total_time = end_time - start_time

        print("\n")
        print("=" * 60)
        print("📊 Timing Statistics:")
        print(f"  - Time to First Token (TTFT): {ttft:.3f}s")
        print(f"  - Total Response Time: {total_time:.3f}s")
        print(f"  - Response Length: {len(response_text)} characters")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_grok())
