from dotenv import load_dotenv
load_dotenv()
import sys
import pathlib
import asyncio

# Ensure project root is on sys.path so we can import the app package
project_root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from app import llm

async def main():
    resp = await llm.get_response("Hello, can you tell me the weather?")
    print(resp)

if __name__ == '__main__':
    asyncio.run(main())
