from typing import Dict, Any, Optional
import os, json, time, re, logging
from openai import OpenAI, APIConnectionError, RateLimitError, APIStatusError
import random
from system_prompt import make_system_prompt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

ENV_API_KEY = os.getenv("OUR_API_KEY")
MODEL = os.getenv("MODEL", "deepseek-chat")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
CLIENT_TIMEOUT = float(os.getenv("DeepSeek_TIMEOUT", "60")) 


def _try_fix_json(content: str) -> str:
    """Try to repair slightly broken JSON strings."""
    
    content = content[content.find("{"):] if "{" in content else content

    open_braces = content.count("{")
    close_braces = content.count("}")
    if close_braces < open_braces:
        content += "}" * (open_braces - close_braces)

    content = re.sub(r'(?<!\\)"(?![:,}\]])', '"', content)
    return content


def _extract_content(resp):
    """
    Extract text/JSON content from the response, supporting DeepSeek
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


def make_client(api_key: Optional[str] = None) -> OpenAI:
    """Create an OpenAI client with timeout and key resolution."""
    key = api_key or ENV_API_KEY
    if not key:
        raise RuntimeError("DeepSeek API key not found. Set OUR_API_KEY or DeepSeek_API_KEY.")
    return OpenAI(base_url= "https://api.deepseek.com/v1", api_key=key, timeout=CLIENT_TIMEOUT)


def ask_bot_deepseek(
    user_slots: str,
    client: OpenAI,
    request_id: str,
    system_prompt: Optional[str] = None,
) -> Dict[str, Any]:

    logger.info(f"[{request_id}] Running")
    logger.info(f"[{request_id}] user_slots: {user_slots[:200]}")

    user_prompt = f"""
        Extract and format strictly.

        DATA (structured clinical input):
        ------------------
        {user_slots}
        ------------------

        Follow SYSTEM rules exactly.
    """

    attempt = 0
    last_err = None
    SYSTEM = system_prompt or make_system_prompt()

    while attempt <= MAX_RETRIES:
        try:
            logger.info(f"Attempt {attempt + 1}/{MAX_RETRIES + 1} — Model: {MODEL}")

            resp = client.chat.completions.create(
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
                    logger.info("Recovered JSON from DeepSeek parsed field.")
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
            logger.warning(f"DeepSeek API error on attempt {attempt}: {e}")
            time.sleep((2 ** attempt) + random.uniform(0, 1))

        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"DeepSeek call failed: {e}") from e

    logger.critical(f"Failed after {MAX_RETRIES} retries. Last error: {last_err}")
    raise RuntimeError(f"DeepSeek call failed after retries: {last_err}")
