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
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-3.5-turbo")
MOCK_LLM = os.getenv("MOCK_LLM", "false").lower() == "true"

OPENAI_AVAILABLE = bool(OPENAI_KEY)
HF_AVAILABLE = bool(HF_API_URL)

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
        try:
            return resp.choices[0].message.content.strip()
        except Exception:
            return getattr(resp.choices[0], 'text', str(resp)).strip()
    except Exception as e:
        msg = str(e)
        if any(x in msg for x in ['insufficient_quota', 'quota', '429', 'RateLimit']):
            OPENAI_AVAILABLE = False
            logger.warning("Disabling OpenAI due to quota/limit error.")
        logger.exception("OpenAI call failed: %s", e)
        return None

async def _call_hf(prompt_text):
    url = os.getenv("HF_API_URL") 
    api_key = os.getenv("HF_API_KEY")
    
    if not url or not api_key:
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "Qwen/Qwen2.5-7B-Instruct", 
        "messages": [{"role": "user", "content": prompt_text}],
        "max_tokens": 500,
        "temperature": 0.7,
        "stream": False
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=20)
            if response.status_code != 200:
                logger.error(f"HF Router Error: {response.status_code}")
                return None
                
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            return None
    except Exception as e:
        logger.error(f"HF Connection trouble: {str(e)}")
        return None

async def get_response(user_message, weather_data=None, history=None):
    if MOCK_LLM:
        return f"[MOCK] Simulated reply based on: {user_message}"

    # 1. Prepare Weather Context
    if weather_data and isinstance(weather_data, dict):
        # OpenWeather format: data['main']['temp']
        main = weather_data.get('main', {})
        temp = main.get('temp', weather_data.get('temp_c', 'N/A'))
        city = weather_data.get('name', weather_data.get('location_name', 'Unknown'))
        desc = weather_data.get('weather', [{}])[0].get('description', 'clear')
        context_text = f"REAL-TIME DATA: In {city}, it is {temp}°C with {desc}."
    else:
        context_text = "REAL-TIME DATA: Not available."

    # 2. Build Messages
    system_instruction = (
        "You are WeatherGPT. You MUST use the REAL-TIME DATA provided. "
        "Do not say you don't have access to live data. "
        "Respond clearly and concisely."
    )

    messages = [{"role": "system", "content": system_instruction}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": f"{context_text}\n\nUser Question: {user_message}"})

    # 3. Try OpenAI
    if OPENAI_AVAILABLE:
        resp = await _call_openai(messages)
        if resp: return resp

    # 4. Try Hugging Face
    if HF_AVAILABLE:
        # Convert messages to a single string for HF
        prompt_text = "\n".join([m["content"] for m in messages])
        resp = await _call_hf(prompt_text)
        if resp: return resp

    # 5. Last Resort Fallback Logic
    return handle_offline_fallback(user_message, weather_data)

def handle_offline_fallback(user_message, weather_data):
    lang = detect_language(user_message)
    if is_greeting(user_message) and not weather_data:
        return greeting_reply(lang)
    return simple_reply(lang, weather_data)

def detect_language(text):
    t = text.lower()
    if any(w in t for w in ['qué', 'clima', 'hola']): return 'es'
    if any(w in t for w in ['météo', 'bonjour']): return 'fr'
    if any(w in t for w in ['क्या', 'मौसम']): return 'hi'
    return 'en'

def is_greeting(text):
    t = text.lower().strip()
    return t in ['hi', 'hello', 'hey', 'namaste']

def greeting_reply(lang):
    replies = {'es': '¡Hola!', 'fr': 'Bonjour !', 'hi': 'नमस्ते!', 'en': 'Hello!'}
    return f"{replies.get(lang, 'Hello!')} I can provide weather info if you give a location."

def simple_reply(lang, weather):
    if not weather:
        return "I don't have an LLM configured or live weather data right now."
    
    main = weather.get('main', {})
    temp = main.get('temp', weather.get('temp_c', 'N/A'))
    loc = weather.get('name', 'location')
    
    if lang == 'hi':
        return f"{loc} में तापमान {temp}°C है।"
    return f"In {loc}, the temperature is {temp}°C."