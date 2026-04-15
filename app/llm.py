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
# Use a valid HF model ID here. Qwen and Llama 3.2 are reliable choices.
HF_MODEL_NAME = os.getenv("HF_MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")
OPENAI_MODEL_NAME = os.getenv("MODEL_NAME", "gpt-3.5-turbo")
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
                return client.chat.completions.create(model=OPENAI_MODEL_NAME, messages=messages, temperature=0.2)
            return openai.ChatCompletion.create(model=OPENAI_MODEL_NAME, messages=messages, temperature=0.2)

        resp = await asyncio.to_thread(do_call)
        return resp.choices[0].message.content.strip()
    except Exception as e:
        msg = str(e)
        if any(err in msg for err in ['insufficient_quota', '429', 'RateLimit']):
            OPENAI_AVAILABLE = False
            logger.warning("Disabling OpenAI due to quota/limits.")
        logger.exception("OpenAI call failed: %s", e)
        return None

async def _call_hf(prompt_text):
    url = os.getenv("HF_API_URL") 
    api_key = os.getenv("HF_API_KEY")
    model_id = os.getenv("HF_MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")
    
    if not url or not api_key:
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # The Router requires this specific format
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt_text}],
        "max_tokens": 500,
        "temperature": 0.7
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=20)
            
            if response.status_code != 200:
                logger.error(f"HF Error: {response.status_code} - {response.text}")
                return None
                
            result = response.json()
            # The Router returns an OpenAI-style response
            return result["choices"][0]["message"]["content"].strip()
                
    except Exception as e:
        logger.error(f"HF Connection trouble: {str(e)}")
        return None
async def get_response(user_message, weather_data=None, history=None):
    history = history or []
    if MOCK_LLM:
        return f"[MOCK] Simulated reply based on: {user_message}"

    system_prompt = (
        "You are WeatherGPT. Answer clearly. If weather data is provided, use it. "
        "Respond in the same language as the user."
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)

    user_block = user_message
    if weather_data:
        user_block = f"WeatherData: {weather_data}\n\nUser: {user_message}"

    messages.append({"role": "user", "content": user_block})

    # --- 1. TRY OPENAI ---
    if OPENAI_AVAILABLE:
        resp = await _call_openai(messages)
        if resp: return resp

    # --- 2. TRY HUGGING FACE ---
    if HF_AVAILABLE:
        # Convert messages list to a string for standard HF or keep as list for Router
        prompt_text = "\n".join([m["content"] for m in messages])
        resp = await _call_hf(prompt_text)
        if resp: return resp

    # --- 3. LAST RESORT FALLBACK (The local/offline logic) ---
    lang = detect_language(user_message or '')
    
    # Check if this is just a greeting
    if not weather_data and is_greeting(user_message):
        return greeting_reply(lang)

    # Return the simple formatted string (Fixes UnboundLocalError)
    return simple_reply(lang, weather_data)

# --- Helper Functions ---

def detect_language(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ['qué', 'clima', 'hola']): return 'es'
    if any(w in t for w in ['météo', 'bonjour']): return 'fr'
    if any(w in t for w in ['क्या', 'मौसम']): return 'hi'
    return 'en'

def is_greeting(text: str) -> bool:
    t = (text or "").lower().strip()
    return t in ['hi', 'hello', 'hey', 'namaste']

def greeting_reply(lang: str):
    replies = {
        'es': '¡Hola! Dame una ubicación para el clima.',
        'hi': 'नमस्ते! मौसम के लिए कृपया स्थान बताएं।',
        'en': 'Hi! Provide a location for weather details.'
    }
    return replies.get(lang, replies['en'])

def simple_reply(lang: str, weather: dict):
    # This prevents the UnboundLocalError by ensuring defaults exist
    if not weather:
        return "I'm sorry, I couldn't get the weather and the AI is offline."
    
    # Map both OpenWeather and your custom dictionary formats
    main = weather.get('main', {})
    temp = main.get('temp', weather.get('temp_c', 'N/A'))
    loc = weather.get('name', weather.get('location_name', 'Unknown'))
    summary = weather.get('weather_summary', 'clear')

    if lang == 'hi':
        return f"{loc} में: {summary}, तापमान {temp}°C."
    return f"In {loc}: {summary}, temperature {temp}°C."