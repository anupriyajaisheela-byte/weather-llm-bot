from dotenv import load_dotenv
load_dotenv()
import sys
import pathlib
import os
import asyncio

# Ensure project root on path
project_root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

# Disable mock for this run
os.environ['MOCK_LLM'] = 'false'

from app import weather, llm

async def main():
    loc = 'Chennai'
    w = await weather.fetch_weather(loc)
    print('Weather raw:', w)
    resp = await llm.get_response(f"What is the weather in {loc}?", weather_data=w)
    print('\nLLM reply:\n', resp)

if __name__ == '__main__':
    asyncio.run(main())
