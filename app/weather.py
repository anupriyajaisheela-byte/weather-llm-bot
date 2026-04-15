import os
import httpx
import logging

# Set up logging to catch errors in the Render terminal
logger = logging.getLogger("uvicorn.error")

async def fetch_weather(location: str):
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        return None

    # Use 'units=metric' for Celsius
    url = f"https://api.openweathermap.org/data/2.5/weather?q={location}&appid={api_key.strip()}&units=metric"
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            print(f"DEBUG WEATHER API: {resp.status_code}") # Watch for 200 in Render logs
            
            if resp.status_code == 200:
                return resp.json() 
            return None
    except Exception:
        return None

    # 1. Configuration
    base_url = "https://api.openweathermap.org/data/2.5/weather"
    # Units=metric ensures Celsius. Language=en is default.
    params = {
        "appid": api_key,
        "units": "metric"
    }
    
    # 2. Handle Location Type
    # Checks if input is "lat,lon" (e.g., from a map or precise extraction)
    if "," in location and all(p.strip().replace('.', '').replace('-', '').isdigit() for p in location.split(",")):
        lat, lon = location.split(",")
        params.update({"lat": lat.strip(), "lon": lon.strip()})
    else:
        # Standard city name search
        params.update({"q": location.strip()})

    # 3. API Call
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(base_url, params=params)
            
            # Print to Render logs for debugging
            print(f"DEBUG WEATHER API: Requesting {location} - Status {response.status_code}")

            if response.status_code == 200:
                data = response.json()

                # 4. Format the "Clean" Dictionary for the AI
                # This structure is exactly what your llm.py expects
                return {
                    "name": data.get("name"),
                    "country": data.get("sys", {}).get("country"),
                    "temp_c": data.get("main", {}).get("temp"),
                    "feels_like": data.get("main", {}).get("feels_like"),
                    "humidity": data.get("main", {}).get("humidity"),
                    "wind_speed": data.get("wind", {}).get("speed"),
                    "weather_summary": data.get("weather", [{}])[0].get("description", "clear")}
            # Non-200 responses are handled below
    except httpx.RequestError as e:
        logger.error(f"Weather API request error for {location}: {e}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error fetching weather for {location}: {e}")
        return None

    # If we reach here, either the response wasn't 200 or parsing failed
    logger.debug(f"Weather API returned non-200 for {location}: {response.status_code if 'response' in locals() else 'no response'}")
    return None