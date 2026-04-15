from fastapi import FastAPI, Request
import re
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
import os
from dotenv import load_dotenv
from app import llm, weather
import logging
import traceback

load_dotenv()
logger = logging.getLogger("uvicorn.error")
app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

def extract_location_from_message(text: str):
    if not text: return None
    t = text.lower().strip()
    
    # regex for "weather in <city>" or "<city> weather"
    m = re.search(r"(?:weather in|what is the weather in|how is the weather in) ([\w\s,.-]+)", t)
    if not m:
        m = re.search(r"([\w\s,.-]+) weather", t)
    
    if m:
        loc = m.group(1).strip()
        return loc.replace("what is", "").replace("the", "").strip()

    # Fallback for 1-2 word city names
    words = t.split()
    if len(words) <= 2 and words[0] not in ["hi", "hello", "hey"]:
        return t
    return None

@app.get("/")
async def index():
    return FileResponse("static/index.html")

@app.post("/api/chat")
async def chat(req: Request):
    try:
        data = await req.json()
        message = data.get("message") or data.get("prompt")
        history = data.get("history") or []

        if not message:
            return JSONResponse({"reply": "No message provided"}, status_code=422)

        # 1. Extraction & Weather Fetch
        location = data.get("location") or extract_location_from_message(message)
        weather_data = None
        if location:
            # Important: Ensure your weather.py has 'async def fetch_weather'
            weather_data = await weather.fetch_weather(location)
        
        # 2. Get AI response (Passing the dictionary directly)
        response = await llm.get_response(message, weather_data=weather_data, history=history)
        
        return JSONResponse({
            "reply": response, 
            "weather": weather_data
        })

    except Exception as e:
        logger.error(f"Error in /api/chat: {traceback.format_exc()}")
        return JSONResponse({
            "reply": "I'm sorry, I'm having trouble connecting to my weather sensors. Try again in a moment?"
        }, status_code=200)