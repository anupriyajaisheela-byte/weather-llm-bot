import os
import logging
import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("uvicorn.error")

async def _call_hf(prompt_text):
    # These MUST match the keys in your Render Dashboard
    url = os.getenv("HF_API_URL") 
    api_key = os.getenv("HF_API_KEY")
    model_id = os.getenv("HF_MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")
    
    if not url or not api_key:
        logger.error("Missing HF_API_URL or HF_API_KEY")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # The NEW Router payload format
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt_text}],
        "max_tokens": 500,
        "temperature": 0.7
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=20)
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
            else:
                logger.error(f"HF Error: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        logger.error(f"Connection trouble: {str(e)}")
        return None

def simple_reply(lang: str, weather: dict):
    if not weather or 'main' not in weather:
        return "I found the location, but the weather data is currently unavailable. The AI is also offline."
    
    # Mapping OpenWeather's actual structure
    temp = weather.get('main', {}).get('temp', 'N/A')
    loc = weather.get('name', 'Unknown location')
    desc = weather.get('weather', [{}])[0].get('description', 'clear skies')

    if lang == 'hi':
        return f"{loc} में: {desc}, तापमान {temp}°C है।"
    return f"In {loc}: It's {desc} with a temperature of {temp}°C."

async def get_response(user_message, weather_data=None, history=None):
    # Try the AI first
    prompt = f"User asked: {user_message}. Context Weather: {weather_data}"
    ai_response = await _call_hf(prompt)
    
    if ai_response:
        return ai_response
        
    # If AI fails, use the safe fallback
    lang = 'hi' if any(word in user_message.lower() for word in ['मौसम', 'नमस्ते']) else 'en'
    return simple_reply(lang, weather_data)