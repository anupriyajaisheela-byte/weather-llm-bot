from fastapi import FastAPI, Request
import re
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from app import llm, weather
import logging
import traceback

# Load environment variables
load_dotenv()

logger = logging.getLogger("uvicorn.error")

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- HELPER FUNCTIONS ---

def extract_location_from_message(text: str):
    """
    Smarter extraction to find city names in common sentences
    or single-word messages.
    """
    if not text: 
        return None
    t = text.lower().strip()
    
    # 1. Match "weather in <location>"
    m = re.search(r"weather in ([\w\s,.-]+)", t)
    if m:
        return m.group(1).strip()
    
    # 2. Match "<location> weather"
    m = re.search(r"([\w\s,.-]+) weather", t)
    if m:
        loc = m.group(1).strip()
        # Remove filler words
        loc = loc.replace("what is", "").replace("how is", "").replace("the", "").strip()
        if len(loc) > 0:
            return loc

    # 3. If it's a short 1-2 word message, assume it's a city (e.g., "London" or "New York")
    words = t.split()
    if len(words) <= 2 and words[0] not in ["hi", "hello", "help", "hey"]:
        return t
        
    return None

# --- ROUTES ---

@app.get("/")
async def index():
    return FileResponse("static/index.html")

@app.get('/favicon.ico')
async def favicon():
    fav_path = "static/favicon.ico"
    if os.path.exists(fav_path):
        return FileResponse(fav_path)
    return Response(status_code=204)

@app.post("/api/chat")
async def chat(req: Request):
    try:
        data = await req.json()
    except Exception:
        return JSONResponse({"reply": "Invalid JSON"}, status_code=400)

    # Get user message and history
    message = data.get("message") or data.get("prompt") or data.get("text")
    history = data.get("history") or []

    if not message:
        return JSONResponse({"reply": "No message provided"}, status_code=422)

    # Try to find a location
    location = data.get("location") or extract_location_from_message(message)

    try:
        weather_data = None
        if location:
            weather_data = await weather.fetch_weather(location)
        
        # This helps you debug in your terminal
        print(f"DEBUG: Message: {message}, Location: {location}, History Length: {len(history)}")
        
        # Get AI response
        response = await llm.get_response(message, weather_data=weather_data, history=history)
        
        return JSONResponse({
            "reply": response, 
            "weather": weather_data
        })

    except Exception as e:
        # Log the error so you can see it in the terminal
        tb = traceback.format_exc()
        logger.error(f"Error in /api/chat: {tb}")

        # Return a 200 status so the UI doesn't show a 'Server Error' popup
        debug_mode = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes")
        return JSONResponse({
            "reply": "I'm sorry, I'm having a bit of trouble processing that right now. Could you try asking again?",
            "error": str(e) if debug_mode else None
        }, status_code=200)