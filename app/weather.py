import os
import httpx
import logging

logger = logging.getLogger("uvicorn.error")

async def fetch_weather(location: str):
    """Fetch current weather for a city name or 'lat,lon'."""
    api_key = os.getenv("OPENWEATHER_API_KEY")
    
    if not api_key:
        logger.error("OPENWEATHER_API_KEY is missing!")
        return None

    # 1. Prepare URL
    base = "https://api.openweathermap.org/data/2.5/weather"
    params = {"appid": api_key, "units": "metric"}
    
    # Handle lat,lon or city name
    if "," in location and all(p.strip().replace('.', '').replace('-', '').isdigit() for p in location.split(",")):
        lat, lon = location.split(",")
        params.update({"lat": lat.strip(), "lon": lon.strip()})
    else:
        params.update({"q": location})

    # 2. Make the Request
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(base, params=params)
            
            # This is your debugging line for Render Logs
            print(f"DEBUG WEATHER API: Status {resp.status_code}, Body: {resp.text}")

            if resp.status_code != 200:
                logger.error(f"Weather API Error: {resp.status_code}")
                return None
            
            j = resp.json()

            # 3. Format the data clearly for llm.py
            # We provide BOTH the full 'main' dict and simplified keys to be safe
            return {
                "name": j.get('name'),
                "main": j.get('main', {}),
                "weather": j.get('weather', [{}]),
                "location_name": f"{j.get('name')}, {j.get('sys', {}).get('country')}",
                "temp_c": j.get('main', {}).get('temp'),
                "weather_summary": j.get('weather')[0].get('description') if j.get('weather') else "clear"
            }
    except Exception as e:
        logger.error(f"Weather Fetch Exception: {str(e)}")
        return None