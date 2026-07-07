from __future__ import annotations
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, field_validator
from typing import Optional
from models.database import (save_patient, save_message, get_history,
                              get_patient, get_all_patients, advance_module,
                              get_progress, set_progress,
                              save_consent_field, save_history_field,
                              save_symptom_field, save_appointment_field,
                              get_consent, get_appointment)
from models.ai_engine import (ask_groq, FLOWS, EDUCATION_POINTS, EDUCATION_INTRO,
                               EDUCATION_PROMPT_QUESTIONS, is_ending_reply, education_closing)
from models.language_utils import (detect_language, validate_child_age,
                                    parse_yes_no, parse_choice, validate_free_text)
from models.pdf_reports import generate_registration_pdf, generate_appointment_pdf

router = APIRouter(prefix="/patients", tags=["Patients"])

_SAVERS = {
    "consent": save_consent_field,
    "clinical_history": save_history_field,
    "symptoms": save_symptom_field,
    "appointments": save_appointment_field,
}

class RegisterChild(BaseModel):
    child_name:        str
    child_age_years:   int
    child_age_months:  Optional[int] = 0
    child_dob:         Optional[str] = None
    child_sex:         Optional[str] = None
    guardian_name:     str
    guardian_relation: Optional[str] = "Parent"
    phone:             str
    address:           Optional[str] = None
    language:          str = "en"

    @field_validator("child_age_years")
    @classmethod
    def age_check(cls, v):
        if not 0 <= v <= 18:
            raise ValueError("Patient must be 0–18 years. This is a pediatric clinic.")
        return v

class ChatMsg(BaseModel):
    patient_id: int
    message:    str
    language:   str = "en"
    module:     int = 1

class DetectLang(BaseModel):
    text: str

class AgeCheck(BaseModel):
    age_years: int

class AdvanceModule(BaseModel):
    patient_id: int
    module:     int

@router.post("/register")
async def register(data: RegisterChild):
    valid, err = validate_child_age(data.child_age_years)
    if not valid:
        raise HTTPException(status_code=400, detail=err)
    try:
        pid = save_patient(
            child_name=data.child_name.strip(),
            child_age_years=data.child_age_years,
            child_age_months=data.child_age_months or 0,
            guardian_name=data.guardian_name.strip(),
            phone=data.phone.strip(),
            child_dob=data.child_dob,
            child_sex=data.child_sex,
            guardian_relation=data.guardian_relation,
            address=None if (data.address or "").lower() in ("skip", "") else data.address,
            language=data.language,
        )
        greeting = await ask_groq(
            [{"role": "user", "content": f"Child registered: {data.child_name}, {data.child_age_years} years."}],
            language=data.language, module=1
        )
        save_message(pid, "assistant", greeting, data.language, module=1)
        return {"patient_id": pid, "greeting": greeting}
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


def _effective_steps(module: int, collected: dict):
    """Steps for this module with any skip_if-conditioned steps filtered out,
    based on data already collected this session."""
    steps = FLOWS[module]["steps"]
    return [s for s in steps if "skip_if" not in s or not s["skip_if"](collected)]


def _collected_so_far(patient_id: int, module: int, step_index: int) -> dict:
    """Rebuild {field: True} for steps already answered — only visit_type
    matters for skip_if logic right now, read straight from DB."""
    from models.database import get_conn
    conn = get_conn(); c = conn.cursor()
    table = FLOWS[module]["table"]
    c.execute(f"SELECT * FROM {table} WHERE patient_id=?", (patient_id,))
    row = c.fetchone(); conn.close()
    return dict(row) if row else {}


@router.post("/advance-module")
async def advance(data: AdvanceModule):
    patient = get_patient(data.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    lang = patient.get("language", "en")
    advance_module(data.patient_id, data.module)
    set_progress(data.patient_id, data.module, 0)

    if data.module in FLOWS:
        flow = FLOWS[data.module]
        first_q = flow["steps"][0]["q"].get(lang, flow["steps"][0]["q"]["en"])
        if data.module == 2:
            # First flow module — no preceding "complete" message to build on, so keep the intro.
            intro = flow["intro"].get(lang, flow["intro"]["en"])
            greeting = f"{intro}\n\n{first_q}"
        else:
            # Modules 3/4/5 always follow a previous module's "complete" message,
            # which already announced the transition — showing the intro again
            # here just repeats it. Ask the first question directly instead.
            greeting = first_q
    elif data.module == 6:
        points = EDUCATION_POINTS.get(lang, EDUCATION_POINTS["en"])
        bullet_text = "\n".join(f"• {p}" for p in points)
        intro = EDUCATION_INTRO.get(lang, EDUCATION_INTRO["en"])
        q = EDUCATION_PROMPT_QUESTIONS.get(lang, EDUCATION_PROMPT_QUESTIONS["en"])
        greeting = f"{intro}\n\n{bullet_text}\n\n{q}"
    else:
        greeting = await ask_groq(
            [{"role": "user", "content": "Starting this module now."}],
            language=lang, module=data.module
        )

    save_message(data.patient_id, "assistant", greeting, lang, module=data.module)
    return {"module": data.module, "greeting": greeting, "completed": False}


@router.post("/chat")
async def chat(data: ChatMsg):
    patient = get_patient(data.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    lang = patient.get("language") or data.language or "en"
    module = data.module
    save_message(data.patient_id, "user", data.message, lang, module=module)

    # ── Modules 2–5: deterministic, validated, backend-driven flow ─────────
    if module in FLOWS:
        flow = FLOWS[module]
        step_idx = get_progress(data.patient_id, module)
        collected = _collected_so_far(data.patient_id, module, step_idx)
        steps = _effective_steps(module, collected)

        if step_idx >= len(steps):
            # Shouldn't normally happen — module already complete
            reply = flow["complete"].get(lang, flow["complete"]["en"])
            save_message(data.patient_id, "assistant", reply, lang, module=module)
            return {"reply": reply, "completed": True}

        step = steps[step_idx]

        # Validate the answer server-side, based on step type
        if step["type"] == "yesno":
            ok, value = parse_yes_no(data.message)
            if not ok:
                err = {"en": "Please answer Yes or No.", "hi": "कृपया हाँ या नहीं में जवाब दें।",
                       "hinglish": "Please Haan ya Nahi mein jawab do."}
                reply = f"{err.get(lang, err['en'])}\n\n{step['q'].get(lang, step['q']['en'])}"
                save_message(data.patient_id, "assistant", reply, lang, module=module)
                return {"reply": reply, "completed": False}
            stored_value = value

        elif step["type"] == "choice":
            ok, value = parse_choice(data.message, step["options"])
            if not ok:
                err = {"en": "Sorry, I didn't understand. Please choose one of the given options.",
                       "hi": "माफ़ कीजिए, समझ नहीं आया। कृपया दिए गए विकल्पों में से चुनें।",
                       "hinglish": "Sorry, samajh nahi aaya. Diye gaye options mein se choose karo."}
                reply = f"{err.get(lang, err['en'])}\n\n{step['q'].get(lang, step['q']['en'])}"
                save_message(data.patient_id, "assistant", reply, lang, module=module)
                return {"reply": reply, "completed": False}
            stored_value = value

        else:  # free text
            ok, err_msg = validate_free_text(data.message)
            if not ok:
                reply = f"{err_msg}\n\n{step['q'].get(lang, step['q']['en'])}"
                save_message(data.patient_id, "assistant", reply, lang, module=module)
                return {"reply": reply, "completed": False}
            stored_value = data.message.strip()

        # Persist into the correct structured table
        saver = _SAVERS[flow["table"]]
        saver(data.patient_id, step["field"], stored_value)
        if "also_save_as" in step:
            saver(data.patient_id, step["also_save_as"], stored_value)

        # Recompute effective steps now that this answer may affect skip_if logic
        collected = _collected_so_far(data.patient_id, module, step_idx)
        steps = _effective_steps(module, collected)
        next_idx = step_idx + 1
        set_progress(data.patient_id, module, next_idx)

        if next_idx < len(steps):
            reply = steps[next_idx]["q"].get(lang, steps[next_idx]["q"]["en"])
            save_message(data.patient_id, "assistant", reply, lang, module=module)
            return {"reply": reply, "completed": False}
        else:
            reply = flow["complete"].get(lang, flow["complete"]["en"])
            save_message(data.patient_id, "assistant", reply, lang, module=module)
            return {"reply": reply, "completed": True}

    # ── Module 6: fixed education content already sent by advance-module;
    #    this endpoint only handles the free-form Q&A that follows ─────────
    if module == 6:
        if is_ending_reply(data.message):
            reply = education_closing(patient.get("child_name"), lang)
            save_message(data.patient_id, "assistant", reply, lang, module=module)
            return {"reply": reply, "completed": True}

        history = get_history(data.patient_id, module=module)
        reply = await ask_groq(history, language=lang, module=module)
        save_message(data.patient_id, "assistant", reply, lang, module=module)
        return {"reply": reply, "completed": False}

    # ── Fallback (module 1 shouldn't normally hit /chat — handled client-side) ─
    history = get_history(data.patient_id, module=module)
    reply = await ask_groq(history, language=lang, module=module)
    save_message(data.patient_id, "assistant", reply, lang, module=module)
    return {"reply": reply, "completed": False}


@router.post("/validate-age")
async def validate_age(data: AgeCheck):
    valid, msg = validate_child_age(data.age_years)
    return {"valid": valid, "message": msg}

@router.post("/detect-language")
async def detect_lang(data: DetectLang):
    return {"language": detect_language(data.text)}

@router.get("/list")
async def list_patients():
    return get_all_patients()

@router.get("/{patient_id}")
async def get_patient_detail(patient_id: int):
    p = get_patient(patient_id)
    if not p: raise HTTPException(status_code=404, detail="Patient not found")
    return p

@router.get("/{patient_id}/history")
async def conversation_history(patient_id: int, module: Optional[int] = None):
    return get_history(patient_id, module=module)

@router.get("/{patient_id}/report/registration")
async def registration_report(patient_id: int):
    patient = get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    consent = get_consent(patient_id)
    pdf_bytes = generate_registration_pdf(patient, consent)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="registration_{patient_id}.pdf"'}
    )

@router.get("/{patient_id}/report/appointment")
async def appointment_report(patient_id: int):
    patient = get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    appointment = get_appointment(patient_id)
    pdf_bytes = generate_appointment_pdf(patient, appointment)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="appointment_{patient_id}.pdf"'}
    )
