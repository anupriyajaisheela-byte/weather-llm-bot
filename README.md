# WeatherGPT

A minimal ChatGPT-like weather chatbot built with FastAPI and a configurable LLM backend (OpenAI or Hugging Face Inference API). It fetches live weather from OpenWeatherMap and instructs the LLM to use that data when answering.

Environment variables (copy from `.env.example`):

- `OPENWEATHER_API_KEY` — required to fetch live weather from OpenWeatherMap
- `OPENAI_API_KEY` — optional; if set the app will use OpenAI (recommended)
- `HF_API_URL` and `HF_API_KEY` — optional Hugging Face inference endpoint and token as fallback
- `MODEL_NAME` — optional OpenAI model name (default `gpt-3.5-turbo`)

Quick start (local):

1. Create a virtual environment and install deps:

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1    # PowerShell (Windows)
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and fill in your keys (do NOT commit `.env`):

```powershell
copy .env.example .env
# edit .env with your editor and add OPENAI_API_KEY / OPENWEATHER_API_KEY as needed
```

3. Run the app (development):

```powershell
python manage.py runserver --host=127.0.0.1 --port=8000
```

4. Test the chat endpoint (PowerShell example):

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/chat -Method Post -Body (ConvertTo-Json @{message='Is it raining in Madrid?'}) -ContentType 'application/json'
```

Notes:

- If using `openai` package >= 1.0.0, the code uses the new `OpenAI` client surface. If you prefer to keep the older API, pin the package:

```bash
pip install openai==0.28
```

- If your Hugging Face model returns HTTP 410, update `HF_API_URL` to a currently available model or use a hosted inference endpoint.

Build Docker image:

```bash
docker build -t weathergpt:latest .
```

CI/CD:

A GitHub Actions workflow `.github/workflows/ci-cd.yml` is included — it runs a basic sanity check and builds/pushes a Docker image to GitHub Container Registry. Configure repository secrets for full deployment.
