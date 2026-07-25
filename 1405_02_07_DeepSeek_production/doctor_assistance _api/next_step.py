from typing import Optional


def build_next_step_user_slots(
    clinical_summary: str,
    selected_differential_dx: str,
    icd10_code: Optional[str] = None,
    icd10_name: Optional[str] = None,
) -> str:
    """Build a structured user slot string for the next-step DeepSeek request."""

    normalized_summary = clinical_summary.strip() or "نامشخص"
    normalized_diagnosis = selected_differential_dx.strip() or "نامشخص"

    lines = [
        f"Clinical summary: {normalized_summary}",
        f"Selected differential diagnosis: {normalized_diagnosis}",
    ]

    if icd10_code:
        lines.append(f"ICD-10 code: {icd10_code.strip()}")

    if icd10_name:
        lines.append(f"ICD-10 diagnosis name: {icd10_name.strip()}")

    lines.append(
        "Please recommend the next steps and drug suggestions for this patient based on the clinical summary and selected diagnosis."
    )
    lines.append(
        "Answer in HTML format for next_steps and drug_suggestion items."
    )

    return "\n".join(lines)


def make_next_step_system_prompt() -> str:
    """Create the system prompt for next-step recommendations."""
    return """
      You are a clinical reasoning assistant.
      Use the provided clinical summary and final diagnosis selection to recommend safe next steps and medication suggestions.

      --------------------------------------------------
      ### OUTPUT FORMAT (STRICT)

      Return ONLY one valid JSON object:

      {
        "next_steps": ["<div dir='rtl' style='text-align: right;'>...</div>"],
        "drug_suggestion": ["<div dir='rtl' style='text-align: right;'>...</div>"]
      }

      - No markdown
      - No explanations
      - No extra text
      - Must be parsable by json.loads()
      --------------------------------------------------
      ### RULES

      - Provide exactly 3 next step suggestions.
      - Provide exactly 3 drug suggestions.
      - Each next step must be Persian and 10 words or fewer.
      - Each drug suggestion must be Persian and 10 words or fewer.
      - Each array item must be a valid HTML string.
      - Do not return plain text without HTML tags.
      - Favor clinically appropriate, evidence-aligned guidance.
      - Do not invent additional diagnoses or patient details.

      --------------------------------------------------
      ### LANGUAGE

      - Persian (Farsi)
      - Medical abbreviations may remain English.
      - Output should be brief and structured.

      --------------------------------------------------
      ### VALIDATION

      - JSON valid
      - No extra fields
      - No explanatory text outside the JSON object
    """
