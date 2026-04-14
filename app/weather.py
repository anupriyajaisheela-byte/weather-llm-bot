import os
import httpx

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

async def fetch_weather(location: str):
    """Fetch simple current weather for a city name or 'lat,lon'. Returns a compact dict."""
    if not OPENWEATHER_API_KEY:
        return None
    base = "https://api.openweathermap.org/data/2.5/weather"
    params = {"appid": OPENWEATHER_API_KEY, "units": "metric"}
    if "," in location and all(p.strip().replace('.', '').replace('-', '').isdigit() for p in location.split(",")):
        lat, lon = location.split(",")
        params.update({"lat": lat.strip(), "lon": lon.strip()})
    else:
        params.update({"q": location})

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
