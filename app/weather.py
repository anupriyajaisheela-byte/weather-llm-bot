import os
import httpx

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# async def fetch_weather(location: str):
#     """Fetch simple current weather for a city name or 'lat,lon'. Returns a compact dict."""
#     if not OPENWEATHER_API_KEY:
#         return None
#     base = "https://api.openweathermap.org/data/2.5/weather"
#     params = {"appid": OPENWEATHER_API_KEY, "units": "metric"}
#     if "," in location and all(p.strip().replace('.', '').replace('-', '').isdigit() for p in location.split(",")):
#         lat, lon = location.split(",")
#         params.update({"lat": lat.strip(), "lon": lon.strip()})
#     else:
#         params.update({"q": location})
# Inside your weather fetching function
async def fetch_weather(location):
    api_key = os.getenv("OPENWEATHER_API_KEY")
    url = f"https://api.openweathermap.org/data/2.5/weather?q={location}&appid={api_key}&units=metric"
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        # ADD THIS LINE TO YOUR CODE:
        print(f"DEBUG WEATHER API: Status {resp.status_code}, Body: {resp.text}")
        
        if resp.status_code != 200:
            return None
        return resp.json()

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(base, params=params)
        if r.status_code != 200:
            return {"error": r.text}
        j = r.json()
        out = {
            "location_name": f"{j.get('name')}, {j.get('sys', {}).get('country')}",
            "temp_c": j.get('main', {}).get('temp'),
            "feels_like_c": j.get('main', {}).get('feels_like'),
            "humidity": j.get('main', {}).get('humidity'),
            "wind_m_s": j.get('wind', {}).get('speed'),
            "weather_summary": j.get('weather')[0].get('description') if j.get('weather') else None,
            "raw": j,
        }
        return out
