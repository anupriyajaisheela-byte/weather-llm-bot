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
        return resp.choices[0].message.content.strip()
    except Exception as e:
        if any(x in str(e) for x in ['insufficient_quota', '429']):
            OPENAI_AVAILABLE = False
        logger.exception("OpenAI call failed")
        return None

async def _call_hf(prompt_text):
    url = os.getenv("HF_API_URL") 
    api_key = os.getenv("HF_API_KEY")
    if not url or not api_key:
        return None

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "Qwen/Qwen2.5-7B-Instruct", 
        "messages": [{"role": "user", "content": prompt_text}],
        "max_tokens": 500,
        "temperature": 0.7
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=20)
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            return None
    except Exception as e:
        logger.error(f"HF Connection trouble: {str(e)}")
        return None

async def get_response(user_message, weather_data=None, history=None):
    # 1. Format the data string strictly for context
    # We check for "temp_c" or "name" because that's what your fetch_weather returns
    if weather_data and ("temp_c" in weather_data or "main" in weather_data):
        # Support both the 'clean' dict and the 'raw' API response
        temp = weather_data.get("temp_c") or weather_data.get("main", {}).get("temp")
        city = weather_data.get("name")
        desc = weather_data.get("weather_summary") or weather_data.get("weather", [{}])[0].get("description")
        
        context_text = f"KNOWLEDGE: The current temperature in {city} is {temp}°C and conditions are {desc}."
    else:
        context_text = "KNOWLEDGE: No live data provided."

    # 2. Stronger Instructions
    system_instruction = (
        "You are WeatherGPT. You MUST use the KNOWLEDGE block about current conditions. "
        "Use this as your absolute source of truth. Do NOT apologize for lacking real-time access."
    )

    messages = [{"role": "system", "content": system_instruction}]
    if history:
        messages.extend(history)
    
    messages.append({"role": "user", "content": f"{context_text}\n\nQuestion: {user_message}"})

    # 3. Call Logic (Try OpenAI first, then HF)
    if OPENAI_AVAILABLE:
        resp = await _call_openai(messages)
        if resp and "check a weather website" not in resp.lower(): 
            return resp

    if HF_AVAILABLE:
        prompt_text = "\n".join([m["content"] for m in messages])
        resp = await _call_hf(prompt_text)
        if resp: 
            return resp

    # 4. Final Fallback
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
    # Check for name/temp_c instead of "main"
    if not weather or ("temp_c" not in weather and "main" not in weather):
        return "I don't have an LLM configured or live weather data right now."
    
    temp = weather.get("temp_c") or weather.get("main", {}).get("temp")
    loc = weather.get("name", "location")
    
    if lang == 'hi':
        return f"{loc} में तापमान {temp}°C है।"
    return f"In {loc}, the temperature is {temp}°C."