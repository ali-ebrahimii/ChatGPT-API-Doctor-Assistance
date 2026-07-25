# Doctor Assistance API DeepSeek

A FastAPI service for converting EHR intake data into structured clinical summaries, differential diagnoses, and next-step recommendations using DeepSeek.

## Overview

This API provides two primary endpoints:

- `POST /analyze`: analyze EHR + profile data and return `clinical_summary` and `differential_dx`.
- `POST /next-step`: accept the clinical summary plus selected or custom diagnosis, then return `next_steps` and `drug_suggestion`.

## Requirements

- Python 3.10+
- `pip install -r requirements.txt`
- Environment variable `OUR_API_KEY` with a valid DeepSeek API key

## Run the API

```bash
cd "doctor_assistance _api"
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Environment variables

```bash
export OUR_API_KEY="your_deepseek_api_key"
export MODEL="deepseek-chat"
```

## Endpoints

### POST /analyze

Use this route to send raw EHR and profile data to the DeepSeek analyst.

Request body:

```json
{
  "ehr_data": { "data": { ... } },
  "profile_data": { "data": { ... } }
}
```

Response contains:

- `request_id`
- `user_slots`
- `bot_raw`

The `bot_raw` output includes:

- `clinical_summary`
- `differential_dx`

### POST /next-step

Use this route after the doctor selects or provides a final diagnosis.

Request body:

```json
{
  "clinical_summary": "...",
  "selected_differential_dx": "...",
  "icd10_code": "A00",
  "icd10_name": "Cholera"
}
```

Response contains:

- `request_id`
- `user_slots`
- `bot_raw`

The `bot_raw` output includes:

- `next_steps`
- `drug_suggestion`

## Workflow

1. Call `/analyze` with `ehr_data` and `profile_data`.
2. Display `differential_dx` options to the doctor.
3. Doctor selects one item or enters a new ICD-10 diagnosis.
4. Call `/next-step` with the returned `clinical_summary` and selected diagnosis.

## Important notes

- `/next-step` uses the previous clinical summary and a final diagnosis selection.
- `selected_differential_dx` can be an existing item from the previous output or a custom ICD-10–based label.
- `icd10_code` and `icd10_name` are optional but helpful for clarity.

## Project structure

- `main.py` — FastAPI app and route definitions
- `deepseek_bot_client.py` — DeepSeek request wrapper
- `system_prompt.py` — prompt configuration for `/analyze`
- `next_step.py` — prompt and slot builder for `/next-step`
- `extract_ehr_fields.py` — EHR normalization utilities

## License

This repository is licensed according to your project's internal policies.
