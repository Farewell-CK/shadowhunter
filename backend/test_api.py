import asyncio
from ai_client import create_client
import time

async def test():
    client = await create_client()
    start = time.time()
    print("Sending chat request...")
    response = await client.chat("你好，请简短回复。")
    end = time.time()
    print(f"Response: {response}")
    print(f"Time taken: {end - start:.2f}s")

if __name__ == "__main__":
    asyncio.run(test())
