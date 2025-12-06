from typing import Dict, Any, Optional
import os, json, time, re, logging
from openai import OpenAI, APIConnectionError, RateLimitError, APIStatusError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

ENV_API_KEY = os.getenv("OUR_API_KEY")
MODEL = os.getenv("MODEL", "gpt-5.1")

MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
CLIENT_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT", "120")) 


def _try_fix_json(content: str) -> str:
    """Try to repair slightly broken JSON strings."""
    
    content = content[content.find("{"):] if "{" in content else content

    open_braces = content.count("{")
    close_braces = content.count("}")
    if close_braces < open_braces:
        content += "}" * (open_braces - close_braces)

    content = re.sub(r'(?<!\\)"(?![:,}\]])', '"', content)
    return content


def _make_client(api_key: Optional[str] = None) -> OpenAI:
    """Create an OpenAI client with timeout and key resolution."""
    key = api_key or ENV_API_KEY
    if not key:
        raise RuntimeError("OpenAI API key not found. Set OUR_API_KEY or OPENAI_API_KEY.")
    return OpenAI(api_key=key, timeout=CLIENT_TIMEOUT)


def _extract_content(resp):
    """
    Extract text/JSON content from the response, supporting GPT-5.1
    and raw JSON-serialized structures.
    """
    try:
        choice = resp.choices[0]

        if getattr(choice.message, "content", None):
            return choice.message.content.strip()

        if hasattr(choice.message, "parsed") and choice.message.parsed:
            parsed = choice.message.parsed
            if isinstance(parsed, (dict, list)):
                return json.dumps(parsed, ensure_ascii=False)
            return str(parsed).strip()

        raw = resp.model_dump()
        if "choices" in raw and raw["choices"]:
            data = raw["choices"][0].get("message", {})
            if isinstance(data, dict) and "content" in data and data["content"]:
                return data["content"].strip()
            if isinstance(data, dict) and "parsed" in data and data["parsed"]:
                if isinstance(data["parsed"], (dict, list)):
                    return json.dumps(data["parsed"], ensure_ascii=False)
                return str(data["parsed"]).strip()

    except Exception as e:
        logger.warning(f"Failed to extract GPT output: {e}")

    return None


SYSTEM = """
You are GPT-5.1, a consultant-level clinical reasoning engine for physicians.
Generate a concise, evidence-based, EMR-ready JSON summary for clinical use only.

### JSON RULES
- Output = one valid JSON object (parsable by `json.loads()`).
- No markdown, text, or comments. Return JSON only.
- Always include all 9 keys (exact order); use "" or [] if empty.
- Schema fixed:

{
 "clinical_summary": "",
 "differential_dx": [{"name":"", "likelihood": integer (0–100), "rationale":""}],
 "next_steps": [""],
 "suggested_specialist": "",
 "follow_up_questions": [""],
 "red_flags": [""],
 "when_to_seek_care": "",
 "handoff_notes": "",
 "safety_disclaimer": ""
}

### STYLE / LANGUAGE
- Persian (Farsi) output; keep English medical terms/abbreviations (e.g., CXR, CRP).
- Objective, concise, telegraphic (e.g., “SpO₂ 94%, HR 96 → stable”).
- Avoid conversational verbs (“داشتن”، “می‌باشد”) — use neutral clinical tone.
- ≤800 tokens total; self-trim redundant text.

### TOKEN BUDGET (approx.)
summary ≤ 80 | DDX ≤ 200 | next_steps ≤ 200 | others ≤ 320
Trim filler words; no repetition of symptoms or values already in the summary.

### CLINICAL SUMMARY
- Summarize **only** input data (CC, demographics, PMH, meds, allergies, social/FHx, vitals, context).
- No inference, no diagnostic verbs (“suggests,” “محتمل,” etc.).
- 1–2 factual sentences.

### DDX
- 3–5 items; distinct likelihoods (top 70–95 > 50–70 > ≤40…).
- Integers only; descending order.
- Each rationale ≤ 20 words (1 finding + 1 pathophys/epi reason).
- Guideline-aligned; no repetition.

### NEXT STEPS
- ≤ 5 concise evidence-based actions (mix of diagnostics + management).
- ≤ 100 chars each; use formal abbrev (CBC, CXR, ABG, ECG).
- Follow guideline logic (IDSA/ATS/ESC/NICE).

### FOLLOW-UP QUESTIONS
- ≤ 5 questions, ≤ 15 words each.
- Purpose: clarify diagnosis or risk (not education).
- Use short clinical phrasing (e.g., “تماس اخیر با بیمار مبتلا؟”).

### RED FLAGS / WHEN TO SEEK CARE
- ≤ 5 urgent indicators (hypoxia, hypotension, confusion, shock, bleeding, etc.).
- Rank by severity.
- End with “فوراً به اورژانس مراجعه شود”.

### OTHER FIELDS
- `suggested_specialist`: exact subspecialty.
- `handoff_notes`: ≤ 80 chars one-line summary.
- `safety_disclaimer`: ≤ 15 words regulatory caution.

### DETERMINISM + QA CHECK
Verify before output: valid JSON, 9 keys ordered, unique descending DDX, ≤800 tokens. Output JSON only.
"""


def ask_bot_5_1(user_slots: str) -> Dict[str, Any]:
    
    api_key = ENV_API_KEY
    client = _make_client(api_key=api_key)
    logger.info(user_slots)
    logger.info("Running")

    user_prompt = (
        "خروجی فقط باید JSON دقیقاً مطابق schema باشد و قابل parse در JSON parser باشد. "
        "اعداد likelihood بین 0 تا 100 و نزولی بنویس. "
        "در clinical_summary فقط داده‌های ورودی را بدون تفسیر خلاصه کن. "
        "اگر داده کافی برای تشخیص وجود ندارد، فقط بنویس: "
        '{"bot_raw": "اطلاعات ناکافی برای نتیجه‌گیری."}\n'
        "DATA:\n" + user_slots
    )

    attempt = 0
    last_err = None

    while attempt <= MAX_RETRIES:
        try:
            logger.info(f"Attempt {attempt + 1}/{MAX_RETRIES + 1} — Model: {MODEL}")

            resp = client.chat.completions.parse(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )

            usage = getattr(resp, "usage", None)
            if usage:
                try:
                    prompt_details = getattr(usage, "prompt_tokens_details", None)
                    cached_tokens = getattr(prompt_details, "cached_tokens", None) if prompt_details else None
                except Exception:
                    cached_tokens = None

                logger.info(
                    "Usage — prompt_tokens=%s, completion_tokens=%s, "
                    "total_tokens=%s, cached_prompt_tokens=%s, cache_read_input_tokens=%s",
                    getattr(usage, "prompt_tokens", None),
                    getattr(usage, "completion_tokens", None),
                    getattr(usage, "total_tokens", None),
                    cached_tokens,
                    getattr(usage, "cache_read_input_tokens", None),
                )

            if hasattr(resp, "output_parsed") and resp.output_parsed:
                logger.info("Parsed JSON obtained via .output_parsed.")
                return resp.output_parsed

            content = _extract_content(resp)

            if not content:
                alt = getattr(resp.choices[0].message, "parsed", None)
                if alt:
                    logger.info("Recovered JSON from GPT-5.1 parsed field.")
                    return alt

            try:
                parsed_json = json.loads(content)
                logger.info("JSON successfully parsed from model output.")
                return parsed_json
            except Exception as parse_err:
                logger.warning("Attempting auto-repair for malformed JSON...")
                fixed = _try_fix_json(content)
                try:
                    return json.loads(fixed)
                except Exception:
                    logger.error(f"JSON parse failed again. Output sample: {content[:300]}")
                    raise RuntimeError(f"Invalid JSON: {parse_err}") from parse_err

        except (APIConnectionError, RateLimitError, APIStatusError) as e:
            attempt += 1
            last_err = e
            logger.warning(f"OpenAI API error on attempt {attempt}: {e}")
            time.sleep(3 * (attempt + 1))

        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"OpenAI call failed: {e}") from e

    logger.critical(f"Failed after {MAX_RETRIES} retries. Last error: {last_err}")
    raise RuntimeError(f"OpenAI call failed after retries: {last_err}")
