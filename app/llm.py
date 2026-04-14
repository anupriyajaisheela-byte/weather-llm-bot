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
HF_API_URL = os.getenv("HF_API_URL")  # optional Hugging Face inference endpoint
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-3.5-turbo")
MOCK_LLM = os.getenv("MOCK_LLM", "false").lower() == "true"

# Availability flags to avoid repeated failing calls at runtime
OPENAI_AVAILABLE = bool(OPENAI_KEY)
HF_AVAILABLE = bool(HF_API_URL)

client = None
if OPENAI_KEY:
    try:
        client = OpenAI(api_key=OPENAI_KEY)
    except Exception:
        # Fall back to legacy assignment for very old openai packages
        openai.api_key = OPENAI_KEY

async def _call_openai(messages):
    global OPENAI_AVAILABLE
    if not OPENAI_KEY or not OPENAI_AVAILABLE:
        return None
    try:
        def do_call():
            # Use the new OpenAI client for openai>=1.0.0
            if client is not None:
                return client.chat.completions.create(model=MODEL_NAME, messages=messages, temperature=0.2)
            # Fallback for older openai versions
            return openai.ChatCompletion.create(model=MODEL_NAME, messages=messages, temperature=0.2)

        resp = await asyncio.to_thread(do_call)
        # New client returns choices with message content
        try:
            return resp.choices[0].message.content.strip()
        except Exception:
            # Older response formats
            return getattr(resp.choices[0], 'text', str(resp)).strip()
    except Exception as e:
        # If quota/limit errors occur, mark OpenAI unavailable to speed future fallbacks
        msg = str(e)
        if 'insufficient_quota' in msg or 'quota' in msg or '429' in msg or 'RateLimit' in msg:
            OPENAI_AVAILABLE = False
            logger.warning("Disabling OpenAI for this session due to quota/limit error.")
        logger.exception("OpenAI call failed: %s", e)
        return None

# async def _call_hf(prompt):
#     global HF_AVAILABLE
#     if not HF_API_URL or not HF_AVAILABLE:
#         raise RuntimeError("No HF API URL configured or HF marked unavailable")
#     try:
#         async with httpx.AsyncClient(timeout=30) as client:
#             data = {"inputs": prompt}
#             headers = {}
#             hf_token = os.getenv("HF_API_KEY")
#             if hf_token:
#                 headers["Authorization"] = f"Bearer {hf_token}"
#             r = await client.post(HF_API_URL, json=data, headers=headers)
#             # handle explicit 410 to mark as unavailable
#             if r.status_code == 410:
#                 HF_AVAILABLE = False
#                 r.raise_for_status()
#             r.raise_for_status()
#             out = r.json()
#         # HF inference API may return string or dict depending on model
#             if isinstance(out, dict) and "generated_text" in out:
#                 return out["generated_text"].strip()
#             if isinstance(out, list) and len(out) and isinstance(out[0], dict) and "generated_text" in out[0]:
#                 return out[0]["generated_text"].strip()
#             if isinstance(out, str):
#                 return out.strip()
#             return str(out)
#     except Exception as e:
#         logger.exception("HF inference call failed: %s", e)
#         return None
async def _call_hf(prompt_text):
    import httpx  # Ensure httpx is imported at the top of your file
    import json

    url = os.getenv("HF_API_URL") 
    api_key = os.getenv("HF_API_KEY")
    
    if not url or not api_key:
        return "System: Hugging Face credentials missing."

    # FIX: Removed the extra " after application/json
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # The Router expects an OpenAI-style 'messages' list
    # The Router needs a specific 'Instruct' or 'Chat' model
    # Using Qwen 2.5 because it has 100% uptime on the HF Router right now
    payload = {
        "model": "Qwen/Qwen2.5-7B-Instruct", 
        "messages": [{"role": "user", "content": prompt_text}],
        "max_tokens": 500,
        "temperature": 0.7,
        "stream": False
    }
    
    try:
        async with httpx.AsyncClient() as client:
            # We send the payload as a JSON string
            response = await client.post(url, headers=headers, json=payload, timeout=20)
            
            # Check if the request was successful
            if response.status_code != 200:
                return f"HF Router Error: {response.status_code} - {response.text}"
                
            result = response.json()
            
            # Extracting the content from the new Router format
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            else:
                return f"Unexpected response format: {result}"
                
    except Exception as e:
        return f"Connection trouble: {str(e)}"    
    

async def get_response(user_message, weather_data=None, history=None):
    history = history or []
    # Quick local testing mode without external API calls
    if MOCK_LLM:
        return f"[MOCK] Simulated reply based on: {user_message}"
    system_prompt = (
        "You are WeatherGPT, an assistant specialized in weather information and forecasts. "
        "Always answer clearly and concisely. If weather facts are provided, incorporate them accurately into your reply. "
        "Respond in the same language as the user. If you cannot access live weather, provide best-effort guidance and explain how to get up-to-date data. "
        "If the user asks for location-specific weather and you were given weather data, rely on that data for numbers and conditions."
    )
    
    

    messages = [{"role": "system", "content": system_prompt}]
    for h in history:
        messages.append(h)

    user_block = user_message
    if weather_data:
        user_block = f"WeatherData: {weather_data}\n\nUser: {user_message}"

    messages.append({"role": "user", "content": user_block})

    # Try OpenAI first if configured
    if OPENAI_KEY:
        resp = await _call_openai(messages)
        if resp:
            return resp
        logger.warning("OpenAI configured but call returned no response, falling back.")

    # Fallback to Hugging Face inference API if provided
    if HF_API_URL:
        prompt_text = "\n".join([m["content"] for m in messages if isinstance(m, dict)])
        resp = await _call_hf(prompt_text)
        if resp:
            return resp
        logger.warning("HF inference configured but call returned no response, falling back.")

    # As a last resort, return a simple helpful message
    # Offline fallback: try to answer based on provided weather_data, and return in user's language using simple heuristics
    def detect_language(text: str) -> str:
        t = text.lower()
        if any(w in t for w in ['qué', 'clima', 'tiempo', 'hola', 'buenos']):
            return 'es'
        if any(w in t for w in ['météo', 'bonjour', 'quel', 'il fait']):
            return 'fr'
        if any(w in t for w in ['tempo', 'olá', 'bom', 'clima']):
            return 'pt'
        if any(w in t for w in ['क्या', 'मौसम', 'कैसा']):
            return 'hi'
        return 'en'

    def simple_reply(lang: str, weather: dict):
        if weather:
            loc = weather.get('location_name') or 'the location'
            summary = weather.get('weather_summary') or 'conditions'
            temp = weather.get('temp_c')
            feels = weather.get('feels_like_c')
            if lang == 'es':
                return f"En {loc}: {summary}, temperatura {temp}°C (sensación {feels}°C)."
            if lang == 'fr':
                return f"À {loc} : {summary}, {temp}°C (ressenti {feels}°C)."
            if lang == 'pt':
                return f"Em {loc}: {summary}, {temp}°C (sensação {feels}°C)."
            if lang == 'hi':
                return f"{loc} में: {summary}, तापमान {temp}°C (अनुभव {feels}°C)."
            return f"In {loc}: {summary}, temperature {temp}°C (feels like {feels}°C)."
        else:
            if lang == 'es':
                return "No tengo un LLM configurado ni datos meteorológicos. Por favor, proporcione una ubicación o configure las claves de API."
            if lang == 'fr':
                return "Je n'ai pas de LLM configuré ni de données météo. Veuillez fournir une localisation ou configurer les clés API."
            if lang == 'pt':
                return "Não tenho um LLM configurado nem dados meteorológicos. Por favor, forneça uma localização ou configure as chaves de API."
            if lang == 'hi':
                return "मेरे पास LLM या मौसम डेटा कॉन्फ़िगर नहीं है। कृपया स्थान दें या API कुंजियाँ सेट करें।"
            return "I don't have an LLM configured or weather data. Please provide a location or set API keys."

    def is_greeting(text: str) -> bool:
        if not text:
            return False
        t = text.lower().strip()
        greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening']
        return any(t == g or t.startswith(g + ' ') or t.startswith(g + '!') for g in greetings)

    def greeting_reply(lang: str):
        if lang == 'es':
            return '¡Hola! Puedo dar información meteorológica si me proporcionas una ubicación o si configuras las claves de API.'
        if lang == 'fr':
            return 'Bonjour ! Je peux fournir la météo si vous fournissez une localisation ou configurez les clés API.'
        if lang == 'pt':
            return 'Olá! Posso fornecer informações meteorológicas se você fornecer uma localização ou configurar as chaves de API.'
        if lang == 'hi':
            return 'नमस्ते! यदि आप स्थान दें या API कुंजियाँ सेट करें तो मैं मौसम की जानकारी दे सकता/सकती हूँ।'
        return "Hi! I can provide weather info if you give a location or set API keys."
    
    lang = detect_language(user_message or '')
    if not OPENAI_KEY and not HF_API_URL and not weather_data:
        if is_greeting(user_message or ''):
            return greeting_reply(lang)

    return simple_reply(lang, weather_data)
