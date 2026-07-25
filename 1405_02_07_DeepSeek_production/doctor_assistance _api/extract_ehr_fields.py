from typing import Dict, Any
from datetime import datetime


def extract_ehr_fields(
    ehr_payload: Dict[str, Any],
    profile_payload: Dict[str, Any]
) -> Dict[str, Any]:

    ehr_data = ehr_payload.get("data", {})
    profile_data = profile_payload.get("data", {})

    general = ehr_data.get("generalRecord", {})
    visit = ehr_data.get("visitRecord", {})

    assistant = visit.get("assistant_visit_record") or {}
    doctor = visit.get("doctor_visit_record") or {}

    demographic = profile_data.get("demographic_profile") or {}
    general_profile = profile_data.get("general_profile") or {}

    # -----------------------------------
    # Helpers
    # -----------------------------------

    def safe_list(x):
        return x if isinstance(x, list) else []

    def clean(x):
        if x in [None, "", "null"]:
            return None
        return str(x).strip()

    def unique(values):
        seen = set()
        result = []

        for v in values:
            if v and v not in seen:
                seen.add(v)
                result.append(v)

        return result

    # -----------------------------------
    # Demographics
    # -----------------------------------

    first_name = clean(general_profile.get("first_name"))
    last_name = clean(general_profile.get("last_name"))

    full_name = " ".join(
        [x for x in [first_name, last_name] if x]
    ) or None

    gender_raw = clean(demographic.get("gender"))

    gender_map = {
        "MALE": "مرد",
        "FEMALE": "زن"
    }

    gender = gender_map.get(gender_raw, "نامشخص")

    birth_date = demographic.get("birth_date")

    age = None

    if birth_date:
        try:
            birth_year = datetime.fromisoformat(
                birth_date.replace("Z", "+00:00")
            ).year

            current_year = datetime.now().year
            age = current_year - birth_year

        except Exception:
            age = None

    # -----------------------------------
    # Chief Complaint
    # -----------------------------------

    chief_complaint = unique(
        safe_list(visit.get("patient_chief_complaint")) +
        ([assistant.get("assistant_chief_complaint")]
         if assistant.get("assistant_chief_complaint") else [])
    )

    # -----------------------------------
    # PMH
    # -----------------------------------

    pmh = []

    for c in safe_list(general.get("underlying_conditions")):

        disease = c.get("disease", {})

        name = clean(disease.get("fa_name"))
        severity = clean(c.get("severity"))
        status = clean(c.get("status"))

        if name:

            extra = []

            if severity:
                extra.append(severity)

            if status:
                extra.append(status)

            if extra:
                pmh.append(f"{name} ({', '.join(extra)})")
            else:
                pmh.append(name)

    pmh = unique(pmh)

    # -----------------------------------
    # Medications
    # -----------------------------------

    medications = []

    for m in safe_list(general.get("ehr_prescription")):

        drug = clean(m.get("drug"))
        usage = clean(m.get("usage"))

        if drug:

            if usage:
                medications.append(f"{drug} — {usage}")
            else:
                medications.append(drug)

    # -----------------------------------
    # Allergies
    # -----------------------------------

    allergies = []

    for a in safe_list(general.get("allergies")):

        substance = clean(a.get("substance"))
        severity = clean(a.get("severity"))
        allergy_type = clean(a.get("type"))

        if substance:

            extra = []

            if allergy_type:
                extra.append(allergy_type)

            if severity:
                extra.append(severity)

            if extra:
                allergies.append(
                    f"{substance} ({' - '.join(extra)})"
                )
            else:
                allergies.append(substance)

    # -----------------------------------
    # Family History
    # -----------------------------------

    family_history = []

    for f in safe_list(general.get("family_records")):

        relation = clean(f.get("relation"))

        disease = clean(
            f.get("disease", {}).get("fa_name")
        )

        if relation and disease:
            family_history.append(
                f"{relation}: {disease}"
            )

    family_history = unique(family_history)

    # -----------------------------------
    # Hospitalizations
    # -----------------------------------

    hospitalizations = []

    for h in safe_list(general.get("hospitalizations")):

        desc = clean(h.get("description"))
        duration = clean(h.get("duration"))

        if desc:

            if duration:
                hospitalizations.append(
                    f"{desc} ({duration} روز)"
                )
            else:
                hospitalizations.append(desc)

    # -----------------------------------
    # Surgeries
    # -----------------------------------

    surgeries = []

    for s in safe_list(general.get("surgical_histories")):

        surgery_type = clean(s.get("type"))
        do_date = clean(s.get("do_date"))

        if surgery_type:

            if do_date:
                surgeries.append(
                    f"{surgery_type} ({do_date[:10]})"
                )
            else:
                surgeries.append(surgery_type)

    # -----------------------------------
    # Lab Tests
    # -----------------------------------

    lab_tests = []

    for l in safe_list(visit.get("lab_test_records")):

        desc = clean(l.get("description"))
        do_date = clean(l.get("do_date"))

        if desc:

            if do_date:
                lab_tests.append(
                    f"{desc} ({do_date[:10]})"
                )
            else:
                lab_tests.append(desc)

    # -----------------------------------
    # Vitals
    # -----------------------------------

    height = clean(
        assistant.get("height")
        or demographic.get("height")
    )

    weight = clean(
        assistant.get("weight")
        or demographic.get("weight")
    )

    bmi = clean(assistant.get("bmi"))

    # -----------------------------------
    # Notes
    # -----------------------------------

    assistant_notes = clean(
        assistant.get("assitant_notes")
    )

    doctor_notes = clean(
        doctor.get("present_illness")
    )

    patient_notes = clean(
        visit.get("patient_notes")
    )

    # -----------------------------------
    # Final normalized structure
    # -----------------------------------

    return {

        "full_name": full_name,

        "gender": gender,

        "age": age,

        "chief_complaint": chief_complaint,

        "pmh": pmh,

        "medications": medications,

        "allergies": allergies,

        "family_history": family_history,

        "hospitalizations": hospitalizations,

        "surgeries": surgeries,

        "lab_tests": lab_tests,

        "height": height,

        "weight": weight,

        "bmi": bmi,

        "assistant_notes": assistant_notes,

        "doctor_notes": doctor_notes,

        "patient_notes": patient_notes,
    }