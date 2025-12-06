from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from bot_client import ask_bot
from gpt4o_bot_client import ask_bot_4o
from gpt5_1_bot_client import ask_bot_5_1
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


app = FastAPI(
    title="Clinical Intake Formatter API",
    description="Accepts raw JSON payload, builds user_slots string, calls bot, and returns bot JSON.",
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
    age: Optional[Any] = Field(None, description="Patient age in years")
    sex: Optional[Any] = Field(None, description="Sex or gender")
    chief_complaint: Optional[Any] = Field(None, description="Chief complaint text")
    duration: Optional[Any] = Field(None, description="Duration value (days/hours) or onset")
    past_medical_history: Optional[Any] = None
    medications: Optional[Any] = None
    allergies: Optional[Any] = None
    social_history: Optional[Any] = None
    family_history: Optional[Any] = None
    temp: Optional[Any] = Field(None, description="Temperature in °C")
    BP_S: Optional[Any] = Field(None, description="Systolic BP")
    BP_D: Optional[Any] = Field(None, description="Diastolic BP")
    HR: Optional[Any] = Field(None, description="Heart rate")
    RR: Optional[Any] = Field(None, description="Respiratory rate")
    SpO2: Optional[Any] = Field(None, description="Pulse oximetry %")
    context: Optional[Any] = Field(None, description="Triggers/exposures/travel/pregnancy…")

    class Config:
        extra = "ignore"


def _nz(value: Optional[str]) -> str:
    """Return text or 'we do not know' if empty."""
    if value is None:
        return "we do not know"
    if isinstance(value, str) and value.strip() == "":
        return "we do not know"
    return str(value)

def _vital(value: Optional[Any]) -> str:
    """Vitals show placeholders when missing."""
    return "__" if value in (None, "", "unknown") else str(value)

def build_user_slots(p: IntakePayload) -> str:
    dur = p.duration
    if dur is None:
        dur = "we do not know"


    age_sex = f"{_nz(p.age)}/{_nz(p.sex)}"
    bp_str = f"{_vital(p.BP_S)}/{_vital(p.BP_D)}"
    hr = _vital(p.HR)
    rr = _vital(p.RR)
    temp = _vital(p.temp)
    spo2 = _vital(p.SpO2)

    iran_tz = ZoneInfo("Asia/Tehran")
    now_Gregorian = datetime.now(iran_tz)
    
    user_slots = (
        f"CC (chief complaint): {_nz(p.chief_complaint)}\n"
        f"Age/Sex: {age_sex}\n"
        f"Duration/Onset: {_nz(dur)}\n"
        f"PMH (past medical history): {_nz(p.past_medical_history)}\n"
        f"Meds (name+dose+freq): {_nz(p.medications)}\n"
        f"Allergies: {_nz(p.allergies)}\n"
        f"Social (tobacco/alcohol/drugs): {_nz(p.social_history)}\n"
        f"FHx (family history): {_nz(p.family_history)}\n"
        f"Vitals: BP {bp_str}, HR {hr}, RR {rr}, Temp {temp}°C, SpO2 {spo2}%\n"
        f"Context/Risk (triggers, exposures, travel, pregnancy): {_nz(p.context)}\n"
        f"Location: Middle East - Iran\n"
        f"Date (Gregorian): {now_Gregorian.strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    return user_slots

@app.post("/analyze")
def analyze(payload: IntakePayload) -> Dict[str, Any]:
    try:
        logger.info("payload")
        logger.info(payload)
        user_slots = build_user_slots(payload)
        bot_json = ask_bot_5_1(user_slots)
        #bot_json = ask_bot(user_slots)
        #bot_json = ask_bot_4o(user_slots)
        return {"message": "ok", "user_slots": user_slots, "bot_raw": bot_json}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")

@app.get("/healthz")
def healthz():
    return {"status": "healthy"}

