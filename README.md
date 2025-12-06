# Doctor's Assistant API – Deployment Guide

## Overview

This service is a FastAPI-based microservice that receives structured JSON payloads describing patient information, normalizes and formats the data, and sends it to an LLM (e.g., OpenAI GPT-4o, GPT-5, GPT-5.1) to receive structured diagnostic suggestions and next steps **in Persian**.

It exposes a RESTful API with automatic Swagger documentation and is ready to deploy in any production environment (bare metal, Docker, or systemd).

---

## Project Structure

```
clinical-intake-api/
│
├── main.py              # FastAPI application (entry point)
├── bot_client.py        # Handles communication with OpenAI API
├── requirements.txt     # Python dependencies
└── README.md            # (this file)
```

---

## Environment

* The chatbot_api environment was installed on the server. To install dependencies, run the below code:
```bash
pip install -r requirements.txt
```

---

## Environment Variables

Before starting the API, set the following from the env_variables.txt file:

```bash
export OUR_API_KEY="<Our_API_KEY>"
export MODEL="gpt-5"
export MAX_RETRIES=2
export CLIENT_TIMEOUT=120
```

## Run the API (Development Mode)

You can start the API manually using:

```bash
uvicorn main:app --host 0.0.0.0 --port 8080 --workers 2
```

* The API will listen on **port 8080**.
* It will be accessible at: `http://<SERVER_IP>:8080`

---

## Run the API (Production Mode)

### Option A – With **systemd** (recommended for bare metal)

Create a unit file:

```ini
# /etc/systemd/system/clinical-intake.service
[Unit]
Description=Clinical Intake API
After=network.target

[Service]
User=ai
WorkingDirectory=/home/ai/clinical-intake-api
Environment=OPENAI_API_KEY=<your_api_key_here>
Environment=MODEL=gpt-5
Environment=MAX_RETRIES=2
ExecStart=/home/ai/clinical-intake-api/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8080 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable clinical-intake
sudo systemctl start clinical-intake
sudo systemctl status clinical-intake
```

---

### Option B – With **Docker**

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8080

ENV MODEL=gpt-5
ENV MAX_RETRIES=2
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
```

Build and run:

```bash
docker build -t clinical-intake-api .
docker run -d -p 8080:8080 -e OPENAI_API_KEY=<your_api_key_here> clinical-intake-api
```

---

## Endpoints

### 1. Health check

```
GET /healthz
```

Response:

```json
{"status": "healthy"}
```

### 2. Analyze patient data

```
POST /triage/analyze
Content-Type: application/json
```

Example request:

```json
{
  "age": 52,
  "sex": "female",
  "chief_complaint": "3-day history of pleuritic chest pain and cough.",
  "duration": 2,
  "past_medical_history": "HTN, type 2 diabetes",
  "medications": "lisinopril 20 mg qd, metformin 500 mg BID",
  "allergies": "penicillin (hives)",
  "social_history": "smoking: 10 pack-years, quit 5 yrs ago",
  "temp": 37,
  "BP_S": 150,
  "BP_D": 80,
  "HR": 92,
  "SpO2": 98
}
```

Example response:

```json
{
  "message": "ok",
  "user_slots": "CC (chief complaint): ...",
  "bot_raw": {
    "clinical_summary": "بیمار با درد پلوریتیک و سرفه مراجعه کرده...",
    "differential_dx": [...],
    "next_steps": [...],
    "suggested_specialist": "پزشک داخلی",
    "follow_up_questions": [...],
    "red_flags": [...],
    "when_to_seek_care": "...",
    "handoff_notes": "...",
    "safety_disclaimer": "..."
  }
}
```

---

## Swagger API Docs

After the server starts, visit:
 `http://<SERVER_IP>:8080/docs`

* Interactive UI to test all endpoints.
* Automatically generated OpenAPI JSON: `http://<SERVER_IP>:8080/openapi.json`

---

## Observability

* **Health check:** `GET /healthz`
* **Logs:** Managed by `systemd`, `docker logs`, or forwarded to your centralized logging solution.
* **Rate limiting / auth:** Recommend applying at the reverse proxy (e.g., Nginx or API Gateway) level.


