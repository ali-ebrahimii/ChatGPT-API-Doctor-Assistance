from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from deepseek_bot_client import ask_bot_deepseek, make_client, ENV_API_KEY
from extract_ehr_fields import extract_ehr_fields
from next_step import build_next_step_user_slots, make_next_step_system_prompt
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
import asyncio
from asyncio import Semaphore
import uuid

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

client = None

app = FastAPI(
    title="Clinical Intake Formatter API",
    description="Accepts raw JSON payload, builds user_slots string, calls bot, and returns bot JSON. Two routes: analyze, next-step ",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class IntakePayload(BaseModel):
    ehr_data: Dict[str, Any]
    profile_data: Dict[str, Any]

    class Config:
        extra = "ignore"


class NextStepPayload(BaseModel):
    clinical_summary: str
    selected_differential_dx: str
    icd10_code: Optional[str] = None
    icd10_name: Optional[str] = None

    class Config:
        extra = "ignore"


def build_user_slots_from_ehr(payload: IntakePayload) -> str:
    f = extract_ehr_fields(payload.ehr_data, payload.profile_data)

    iran_tz = ZoneInfo("Asia/Tehran")
    now_Gregorian = datetime.now(iran_tz)

    def join_or_unknown(lst):
        return ", ".join([str(x) for x in lst if x]) if lst else "we do not know"

    user_slots = (
        f"CC (chief complaint): {join_or_unknown(f['chief_complaint'])}\n"
        f"Age: {f['age']}\n"
        f"Gender: {f['gender']}\n"
        f"PMH: {join_or_unknown(f['pmh'])}\n"
        f"Meds: {join_or_unknown(f['medications'])}\n"
        f"Allergies: {join_or_unknown(f['allergies'])}\n"
        f"Family History: {join_or_unknown(f['family_history'])}\n"
        f"Hospitalizations: {join_or_unknown(f['hospitalizations'])}\n"
        f"Surgical History: {join_or_unknown(f['surgeries'])}\n"
        f"Vitals: Height {f['height']}, Weight {f['weight']}, BMI {f['bmi']}\n"
        f"Doctor Notes: {f['doctor_notes'] or 'we do not know'}\n"
        f"Assistant Notes: {f['assistant_notes'] or 'we do not know'}\n"
        f"Location: Middle East\n"
        f"Date: {now_Gregorian.strftime('%Y-%m-%d %H:%M:%S')}\n"
    )

    return user_slots


@app.on_event("startup")
def startup_event():
    global client
    client = make_client(api_key=ENV_API_KEY)
    logger.info("DeepSeek client initialized")


# Limit concurrent DeepSeek calls
MAX_CONCURRENT_REQUESTS = 10
semaphore = Semaphore(MAX_CONCURRENT_REQUESTS)

@app.post("/analyze")
async def analyze(payload: IntakePayload) -> Dict[str, Any]:
    request_id = str(uuid.uuid4())
    try:
        logger.info(f"[{request_id}] Incoming request")
        logger.debug(payload.dict())
        
        if client is None:
            raise HTTPException(status_code=503, detail="Model client not initialized")

        user_slots = build_user_slots_from_ehr(payload)

        async with semaphore:
            bot_json = await asyncio.wait_for(
                asyncio.to_thread(
                    ask_bot_deepseek,
                    user_slots,
                    client,
                    request_id
                ),
                timeout=40
            )

        return {
            "request_id": request_id,
            "message": "ok",
            "user_slots": user_slots,
            "bot_raw": bot_json
        }
    
    except asyncio.TimeoutError:
        logger.error(f"[{request_id}] Timeout")
        raise HTTPException(status_code=504, detail="Model timeout")

    except RuntimeError as e:
        logger.error(f"[{request_id}] Error: {e}")
        raise HTTPException(status_code=502, detail=str(e))

    except Exception as e:
        logger.error(f"[{request_id}] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@app.post("/next-step")
async def next_step(payload: NextStepPayload) -> Dict[str, Any]:
    request_id = str(uuid.uuid4())
    try:
        logger.info(f"[{request_id}] Incoming next-step request")
        logger.debug(payload.dict())

        if client is None:
            raise HTTPException(status_code=503, detail="Model client not initialized")

        user_slots = build_next_step_user_slots(
            clinical_summary=payload.clinical_summary,
            selected_differential_dx=payload.selected_differential_dx,
            icd10_code=payload.icd10_code,
            icd10_name=payload.icd10_name,
        )

        async with semaphore:
            bot_json = await asyncio.wait_for(
                asyncio.to_thread(
                    ask_bot_deepseek,
                    user_slots,
                    client,
                    request_id,
                    system_prompt=make_next_step_system_prompt(),
                ),
                timeout=40
            )

        return {
            "request_id": request_id,
            "message": "ok",
            "user_slots": user_slots,
            "bot_raw": bot_json
        }

    except asyncio.TimeoutError:
        logger.error(f"[{request_id}] Timeout")
        raise HTTPException(status_code=504, detail="Model timeout")

    except RuntimeError as e:
        logger.error(f"[{request_id}] Error: {e}")
        raise HTTPException(status_code=502, detail=str(e))

    except Exception as e:
        logger.error(f"[{request_id}] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@app.get("/healthz")
def healthz():
    return {"status": "healthy"}

