import asyncio
from src.config import settings
from src.services.embedding_service import get_ai_client

async def test_connection():
    print(f"Connecting to: {settings.ai_base_url or 'OpenAI default'}...")

    client = get_ai_client()

    try:
        # Send a simple text message
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello! Are you receiving my messages?"}
            ],
            temperature=0.7
        )

        print("\nSuccess! AI Response:")
        print("-" * 20)
        print(response.choices[0].message.content)

    except Exception as e:
        print(f"\nFailed to connect: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
