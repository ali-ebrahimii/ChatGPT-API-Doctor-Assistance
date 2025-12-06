from typing import Dict, Any, Optional
import os, json, time, logging, re
from openai import OpenAI, APIConnectionError, RateLimitError, APIStatusError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


ENV_API_KEY = os.getenv("OUR_API_KEY")
MODEL = "gpt-4o"
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))
CLIENT_TIMEOUT = float(60) #seconds


def _try_fix_json(content: str) -> str:
    """
    Try to fix truncated or slightly invalid JSON (e.g., missing closing braces/quotes).
    """
    content = content[content.find("{"):]
    open_braces = content.count("{")
    close_braces = content.count("}")
    if close_braces < open_braces:
        content += "}" * (open_braces - close_braces)
    content = re.sub(r'(?<!\\)"(?![:,}\]])', '"', content)
    return content



def _make_client(api_key: Optional[str] = None) -> OpenAI:
    """Create an OpenAI client with timeout and a resolved API key."""
    key = api_key or ENV_API_KEY
    if not key:
        raise RuntimeError(
            "OpenAI API key not found. Set OUR_API_KEY or OPENAI_API_KEY (env), "
            "or pass api_key=... to ask_bot()."
        )
    return OpenAI(api_key=key, timeout=CLIENT_TIMEOUT)


def _extract_content(resp):
    """Handle all possible response variants."""
    try:
        choice = resp.choices[0]
        if getattr(choice.message, "content", None):
            return choice.message.content
        if hasattr(choice.message, "parsed") and choice.message.parsed:
            return json.dumps(choice.message.parsed)
        if hasattr(choice, "parsed") and choice.parsed:
            return json.dumps(choice.parsed)
    except Exception as e:
        logger.warning(f"Failed to extract content: {e}")
    return None


def ask_bot_4o(user_slots: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    
    client = _make_client(api_key=api_key)
    logger.info('running')
    logger.info(user_slots)
    SYSTEM = """
        You are **GPT-4o**, acting as a clinical information assistant for doctors.
        Your task: produce a concise, structured JSON summary in Persian (Farsi) to help doctors with education, triage, and 3-5 number of differential thinking — **not final diagnosis or prescriptions**.

        ### ROLE
        - Give guidance, identify 3-5 most red flags, suggest 3-5 number of next steps, and recommend which specialist to consult. also the number of follow_up_questions be 3-5.
        - You act as a safety-first educational assistant.
        - If you do not have enough data about patient, say "اطلاعات کافی برای پردازش وجود ندارد، پس توانایی تولید چواب دقیق ندارم."

        ### LANGUAGE
        - All text must be in Persian (Farsi)--> right to left.
        - Use English medical terms **only if precise** (e.g., “MRI”, “Myocardial infarction”).
        - Do **not** use English commentary or metadata outside JSON.

        ### STYLE
        - Concise, neutral, clinically accurate.
        - No reasoning explanations or step-by-step thoughts.
        - 100% safety-oriented.
        - If any life-threatening signs appear, clearly include “فوراً به اورژانس مراجعه شود” in `when_to_seek_care`.

        ### OUTPUT RULES
        Return **only** a single valid JSON object matching the schema below — no extra text, markdown, or comments.
        The output will be 800 tokens in maximum size.

        ```json
        {
          "clinical_summary": "string, خلاصه وضعیت بیمار به فارسی (≤150)",
          "differential_dx": [
            {
              "name": "string, نام بیماری",
              "likelihood": "high|moderate|low",
              "rationale": "string, توضیح کوتاه (≤100)"
            }
          ],
          "next_steps": ["string, گام‌های بعدی (≤100 each)"],
          "suggested_specialist": "string, متخصص مناسب",
          "follow_up_questions": ["string, سوالات تکمیلی (≤100 each)"],
          "red_flags": ["string, علائم هشدار (≤100 each)"],
          "when_to_seek_care": "string, زمان مراجعه",
          "handoff_notes": "string, نکات برای ارجاع (≤80)",
          "safety_disclaimer": "string, هشدار ایمنی (≤80)"
        }
        """

    user_prompt = "فقط JSON مطابق Schema بده.\nDATA:\n" + user_slots

    attempt = 0
    last_err = None

    while attempt <= MAX_RETRIES:
        try:
            logger.info(f"Attempt {attempt+1}/{MAX_RETRIES+1} — Model: {MODEL}")

            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM, "cache_control": {"type": "ephemeral"}},
                    {"role": "user", "content": user_prompt},
                ],
                max_completion_tokens=800,
                response_format={"type": "json_object"},
            )

            choice = resp.choices[0]
            logger.debug(f"Raw choice structure: {choice}")

            content = _extract_content(resp)

            if not content:
                logger.warning("Empty response from structured mode. Retrying without response_format...")
                resp = client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM},
                        {"role": "user", "content": user_prompt + "\n(Only JSON. No prose.)"},
                    ],
                    max_completion_tokens=800,
                )
                content = _extract_content(resp)

            if not content:
                raise RuntimeError("Model returned no output in all modes.")

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
            time.sleep(2 * attempt)
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"OpenAI call failed: {e}") from e

    logger.critical(f"❌ Failed after {MAX_RETRIES} retries. Last error: {last_err}")
    raise RuntimeError(f"OpenAI call failed after retries: {last_err}")

