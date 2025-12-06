# Doctor’s Assistant API – Deployment Guide

A production-ready **FastAPI service** that converts raw patient intake data into **structured clinical summaries** using OpenAI models (GPT-4o, GPT-5, GPT-5.1).
The output is *always valid JSON in Persian*, following strict schema and safety rules.

This API is suitable for:

* Clinical triage assistants
* Doctor support chatbots
* Hospital workflow automation
* Mobile health apps

---

## 📂 Project Structure

```
ChatGPT-API-Doctor-Assistance/
│
├── main.py                  # FastAPI app & endpoints                        :contentReference[oaicite:0]{index=0}
├── bot_client.py            # GPT-5 client with schema enforcement           :contentReference[oaicite:1]{index=1}
├── gpt4o_bot_client.py      # GPT-4o client (lighter alternative)            :contentReference[oaicite:2]{index=2}
├── gpt5_1_bot_client.py     # GPT-5.1 client with advanced parsing           :contentReference[oaicite:3]{index=3}
├── requirements.txt         # Python dependencies                            :contentReference[oaicite:4]{index=4}
├── docker-compose.yml       # Deployment orchestrator
├── Dockerfile               # Build production container
└── README.md                # (this file)
```

---

## 🚀 What This API Does

1. Receives **raw patient JSON**
2. Converts it into a unified **user_slots** text
3. Sends the text to the LLM (GPT-4o, GPT-5, or GPT-5.1)
4. Model returns a **strict structured JSON** containing:

   * clinical_summary
   * differential_dx
   * next_steps
   * suggested_specialist
   * follow_up_questions
   * red_flags
   * when_to_seek_care
   * handoff_notes
   * safety_disclaimer

All formatting rules, schema validation, and JSON repair are handled inside:

* `bot_client.py` (GPT-5) 
* `gpt4o_bot_client.py` (GPT-4o) 
* `gpt5_1_bot_client.py` (GPT-5.1) 

---

## 🔧 Requirements

Install dependencies:

```bash
pip install -r requirements.txt
```

Packages include FastAPI, Uvicorn, Pydantic, and OpenAI (defined in `requirements.txt`).


---

## 🔑 Environment Variables

Before running, configure:

```bash
export OUR_API_KEY="<Your_OpenAI_Key>"
export MODEL="gpt-5.1"     # or: gpt-5 / gpt-4o
export MAX_RETRIES=3
export OPENAI_TIMEOUT=120
```

---

## ▶️ Run the API (Development)

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
```

API will start at:

```
http://localhost:8000
```

Swagger Docs:

```
http://localhost:8000/docs
```

---

## 🐳 Run with Docker (Production)

### Build:

```bash
docker build -t doctor-assistant-api .
```

### Run:

```bash
docker run -d \
  -p 8000:8000 \
  -e OUR_API_KEY="<your_key>" \
  -e MODEL="gpt-5.1" \
  doctor-assistant-api
```

---

## 🧠 API Endpoints

### ✓ Health Check

```
GET /healthz
```

Response:

```json
{"status": "healthy"}
```

---

### ✓ Analyze Patient Data

```
POST /analyze
Content-Type: application/json
```

The request is validated by the `IntakePayload` model in `main.py`.


Example request:

```json
{
  "age": 45,
  "sex": "male",
  "chief_complaint": "chest pain for 2 hours",
  "past_medical_history": "HTN",
  "SpO2": 94,
  "HR": 110
}
```

Example response (from GPT-5.1):

```json
{
  "message": "ok",
  "user_slots": "CC: ...",
  "bot_raw": {
    "clinical_summary": "...",
    "differential_dx": [...],
    "next_steps": [...],
    "suggested_specialist": "کاردیولوژی",
    "follow_up_questions": [...],
    "red_flags": [...],
    "when_to_seek_care": "...",
    "handoff_notes": "...",
    "safety_disclaimer": "..."
  }
}
```

---

## 🧪 Model Options

You can switch models by editing this line in `main.py`:

```python
bot_json = ask_bot_5_1(user_slots)  # GPT-5.1 (current default)
# bot_json = ask_bot(user_slots)    # GPT-5
# bot_json = ask_bot_4o(user_slots) # GPT-4o
```

All 3 model wrappers support:

* Retry logic
* Automatic JSON repair
* Strict schema enforcement
* Persian medical formatting

---

## 📌 Notes for Deployment

* Recommend placing Nginx or Traefik in front of API for rate limiting
* Supports CORS by default
* Error handling shows detailed 50x messages for debugging
* Timezone converted to Iran time using `Asia/Tehran`
  (implemented in `main.py`) 

Just tell me!
