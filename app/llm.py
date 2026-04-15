import os
import logging
import openai
import asyncio
from openai import OpenAI
import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("uvicorn.error")

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
HF_API_URL = os.getenv("HF_API_URL")
HF_API_KEY = os.getenv("HF_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-3.5-turbo")
MOCK_LLM = os.getenv("MOCK_LLM", "false").lower() == "true"

OPENAI_AVAILABLE = bool(OPENAI_KEY)

client = None
if OPENAI_KEY:
    try:
        client = OpenAI(api_key=OPENAI_KEY)
    except Exception:
        openai.api_key = OPENAI_KEY

async def _call_openai(messages):
    global OPENAI_AVAILABLE
    if not OPENAI_KEY or not OPENAI_AVAILABLE:
        return None
    try:
        def do_call():
            if client is not None:
                return client.chat.completions.create(model=MODEL_NAME, messages=messages, temperature=0.2)
            return openai.ChatCompletion.create(model=MODEL_NAME, messages=messages, temperature=0.2)

        resp = await asyncio.to_thread(do_call)
        return resp.choices[0].message.content.strip()
    except Exception as e:
        msg = str(e).lower()
        if any(err in msg for err in ['quota', '429', 'ratelimit']):
            OPENAI_AVAILABLE = False
            logger.warning("OpenAI quota exceeded. Falling back to Hugging Face.")
        return None

async def _call_hf(prompt_text):
    # Use the router URL specifically
    # Even if your Render env has the old URL, this ensures we use the new one
    url = "https://router.huggingface.co/hf-inference/v1/chat/completions"
    
    if not HF_API_KEY:
        return None

    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }

    # The Router requires this specific payload format
    payload = {
        "model": "Qwen/Qwen2.5-7B-Instruct", 
        "messages": [{"role": "user", "content": prompt_text}],
        "max_tokens": 500,
        "temperature": 0.7
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=20)
            
            if response.status_code != 200:
                logger.error(f"HF Router Error: {response.status_code} - {response.text}")
                return None
                
            result = response.json()
            if "choices" in result:
                return result["choices"][0]["message"]["content"]
            return None
                
    except Exception as e:
        logger.error(f"HF Connection trouble: {str(e)}")
        return None

async def get_response(user_message, weather_data=None, history=None):
    history = history or []
    if MOCK_LLM:
        return f"[MOCK] Weather summary: {weather_data}"

    system_prompt = (
        "You are WeatherGPT. Use the provided WeatherData to answer the user. "
        "Be concise and respond in the same language as the user."
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    for h in history:
        messages.append(h)

    user_block = user_message
    if weather_data and "error" not in weather_data:
        user_block = (
            f"WeatherData: {weather_data['weather_summary']}, {weather_data['temp_c']}°C. "
            f"Location: {weather_data['location_name']}\n\n"
            f"User: {user_message}"
        )

    messages.append({"role": "user", "content": user_block})

    # 1. Try OpenAI
    if OPENAI_AVAILABLE:
        resp = await _call_openai(messages)
        if resp: return resp

    # 2. Try Hugging Face
    prompt_text = "\n".join([m["content"] for m in messages])
    resp = await _call_hf(prompt_text)
    if resp: return resp

    # 3. Last Resort (Simple Logic)
    if weather_data and isinstance(weather_data, dict):
    # OpenWeather typically uses 'main' for temperature and 'name' for city
    # We check both the direct key and the nested 'main' key to be safe
        temp = weather_data.get('main', {}).get('temp', weather_data.get('temp', 'N/A'))
        loc = weather_data.get('name', weather_data.get('location_name', 'Unknown'))
    
    return f"Currently, I can see it's {temp}°C in {loc}."