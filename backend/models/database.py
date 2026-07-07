from __future__ import annotations
import sqlite3, hashlib
from typing import Optional, List, Dict
from config import DB_NAME

def get_conn():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn(); c = conn.cursor()

    # Core patient record (Module 1 — Registration Agent)
    c.execute("""CREATE TABLE IF NOT EXISTS patients (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        child_name        TEXT NOT NULL,
        child_age_years   INTEGER NOT NULL CHECK(child_age_years BETWEEN 0 AND 18),
        child_age_months  INTEGER DEFAULT 0,
        child_dob         TEXT,
        child_sex         TEXT,
        guardian_name     TEXT NOT NULL,
        guardian_relation TEXT DEFAULT 'Parent',
        phone             TEXT NOT NULL,
        address           TEXT,
        mr_no             TEXT,
        language          TEXT DEFAULT 'en',
        current_module    INTEGER DEFAULT 1,
        created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # Module 2 — Consent Agent
    c.execute("""CREATE TABLE IF NOT EXISTS consent (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id      INTEGER UNIQUE NOT NULL,
        data_consent    INTEGER DEFAULT 0,
        photo_consent   INTEGER DEFAULT 0,
        research_consent INTEGER DEFAULT 0,
        signed_at       TIMESTAMP,
        FOREIGN KEY(patient_id) REFERENCES patients(id)
    )""")

    # Module 3 — History Collection Agent
    c.execute("""CREATE TABLE IF NOT EXISTS clinical_history (
        id                        INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id                INTEGER UNIQUE NOT NULL,
        chief_complaint           TEXT,
        eye_affected              TEXT,
        since_when                TEXT,
        squint_type               TEXT,
        frequency                 TEXT,
        birth_type                TEXT,
        delivery_type             TEXT,
        birth_weight              TEXT,
        birth_complications       TEXT,
        nicu_admission            TEXT,
        jaundice                  TEXT,
        neck_holding_age          TEXT,
        sitting_age               TEXT,
        walking_age               TEXT,
        talking_age               TEXT,
        milestone_delay           TEXT,
        seizures                  TEXT,
        systemic_disease          TEXT,
        systemic_surgery          TEXT,
        immunisation_status       TEXT,
        maternal_antenatal_history TEXT,
        family_history            TEXT,
        consanguinity              TEXT,
        previous_glasses          TEXT,
        previous_surgery          TEXT,
        FOREIGN KEY(patient_id) REFERENCES patients(id)
    )""")

    # Migration: add any new columns to a pre-existing clinical_history table
    # (CREATE TABLE IF NOT EXISTS above is a no-op if the table already exists,
    # so older databases need these columns added explicitly).
    _new_history_columns = ["frequency", "systemic_disease", "systemic_surgery",
                             "immunisation_status", "maternal_antenatal_history", "consanguinity"]
    for col in _new_history_columns:
        try:
            c.execute(f"ALTER TABLE clinical_history ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists

    # Module 4 — Symptom Checker Agent
    c.execute("""CREATE TABLE IF NOT EXISTS symptoms (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id      INTEGER UNIQUE NOT NULL,
        eye_turn        TEXT,
        eye_rubbing     TEXT,
        headache        TEXT,
        photophobia     TEXT,
        nystagmus       TEXT,
        ptosis          TEXT,
        head_tilt       TEXT,
        double_vision   TEXT,
        symptom_score   INTEGER DEFAULT 0,
        risk_flags      TEXT,
        FOREIGN KEY(patient_id) REFERENCES patients(id)
    )""")

    # Conversations (all modules share this)
    c.execute("""CREATE TABLE IF NOT EXISTS conversations (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id  INTEGER NOT NULL,
        module      INTEGER DEFAULT 1,
        role        TEXT NOT NULL,
        message     TEXT NOT NULL,
        language    TEXT DEFAULT 'en',
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(patient_id) REFERENCES patients(id)
    )""")

    # Files
    c.execute("""CREATE TABLE IF NOT EXISTS patient_files (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id  INTEGER NOT NULL,
        file_name   TEXT NOT NULL,
        file_path   TEXT NOT NULL,
        file_type   TEXT DEFAULT 'general',
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(patient_id) REFERENCES patients(id)
    )""")

    # Module 5 — Appointment Agent
    c.execute("""CREATE TABLE IF NOT EXISTS appointments (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id          INTEGER UNIQUE NOT NULL,
        visit_type          TEXT,
        preferred_datetime  TEXT,
        special_needs       TEXT,
        confirmed_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(patient_id) REFERENCES patients(id)
    )""")

    # Server-side conversation state machine — tracks exactly which question
    # (step) each patient is on, per module, so the AI can never skip,
    # repeat, or re-order questions.
    c.execute("""CREATE TABLE IF NOT EXISTS module_progress (
        patient_id  INTEGER NOT NULL,
        module      INTEGER NOT NULL,
        step        INTEGER DEFAULT 0,
        PRIMARY KEY(patient_id, module),
        FOREIGN KEY(patient_id) REFERENCES patients(id)
    )""")

    conn.commit(); conn.close()
    print("✅ DB initialized — all 6 Layer-1 agent tables ready")

# ── CRUD helpers ──────────────────────────────────────────────────────────────

def save_patient(child_name, child_age_years, guardian_name, phone,
                 child_age_months=0, child_dob=None, child_sex=None,
                 guardian_relation="Parent", address=None, language="en") -> int:
    conn = get_conn(); c = conn.cursor()
    c.execute("""INSERT INTO patients
        (child_name,child_age_years,child_age_months,child_dob,child_sex,
         guardian_name,guardian_relation,phone,address,language)
        VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (child_name,child_age_years,child_age_months,child_dob,child_sex,
         guardian_name,guardian_relation,phone,address,language))
    conn.commit(); pid = c.lastrowid; conn.close()
    return pid

def save_message(patient_id, role, message, language="en", module=1):
    conn = get_conn(); c = conn.cursor()
    c.execute("INSERT INTO conversations(patient_id,module,role,message,language) VALUES(?,?,?,?,?)",
              (patient_id, module, role, message, language))
    conn.commit(); conn.close()

def get_history(patient_id, module=None) -> List[Dict]:
    conn = get_conn(); c = conn.cursor()
    if module:
        c.execute("SELECT role,message FROM conversations WHERE patient_id=? AND module=? ORDER BY id ASC",
                  (patient_id, module))
    else:
        c.execute("SELECT role,message FROM conversations WHERE patient_id=? ORDER BY id ASC", (patient_id,))
    rows = c.fetchall(); conn.close()
    return [{"role": r["role"], "content": r["message"]} for r in rows]

def get_patient(pid) -> Optional[Dict]:
    conn = get_conn(); c = conn.cursor()
    c.execute("SELECT * FROM patients WHERE id=?", (pid,))
    row = c.fetchone(); conn.close()
    return dict(row) if row else None

def get_all_patients() -> List[Dict]:
    conn = get_conn(); c = conn.cursor()
    c.execute("""SELECT id,child_name,child_age_years,child_age_months,child_sex,
                 guardian_name,phone,language,current_module,created_at
                 FROM patients ORDER BY id DESC""")
    rows = c.fetchall(); conn.close()
    return [dict(r) for r in rows]

def get_consent(patient_id) -> Optional[Dict]:
    conn = get_conn(); c = conn.cursor()
    c.execute("SELECT * FROM consent WHERE patient_id=?", (patient_id,))
    row = c.fetchone(); conn.close()
    return dict(row) if row else None

def get_appointment(patient_id) -> Optional[Dict]:
    conn = get_conn(); c = conn.cursor()
    c.execute("SELECT * FROM appointments WHERE patient_id=?", (patient_id,))
    row = c.fetchone(); conn.close()
    return dict(row) if row else None

def advance_module(patient_id, module):
    conn = get_conn(); c = conn.cursor()
    c.execute("UPDATE patients SET current_module=? WHERE id=?", (module, patient_id))
    conn.commit(); conn.close()

def save_file(patient_id, file_name, file_path, file_type="general"):
    conn = get_conn(); c = conn.cursor()
    c.execute("INSERT INTO patient_files(patient_id,file_name,file_path,file_type) VALUES(?,?,?,?)",
              (patient_id, file_name, file_path, file_type))
    conn.commit(); conn.close()

# ── Module progress state machine ──────────────────────────────────────────
# Guarantees the AI can never skip, repeat, or reorder questions: the backend
# — not the LLM — always knows exactly which step a patient is on.

def get_progress(patient_id, module) -> int:
    conn = get_conn(); c = conn.cursor()
    c.execute("SELECT step FROM module_progress WHERE patient_id=? AND module=?", (patient_id, module))
    row = c.fetchone()
    if row is not None:
        conn.close()
        return row["step"]
    c.execute("INSERT INTO module_progress(patient_id,module,step) VALUES(?,?,0)", (patient_id, module))
    conn.commit(); conn.close()
    return 0

def set_progress(patient_id, module, step):
    conn = get_conn(); c = conn.cursor()
    c.execute("""INSERT INTO module_progress(patient_id,module,step) VALUES(?,?,?)
                 ON CONFLICT(patient_id,module) DO UPDATE SET step=excluded.step""",
              (patient_id, module, step))
    conn.commit(); conn.close()

# ── Structured data writers ─────────────────────────────────────────────────
# `field` is always a hardcoded constant from ai_engine.FLOWS (never raw user
# input), so building the column name into SQL here is safe.

_ALLOWED_CONSENT_FIELDS = {"data_consent", "photo_consent", "research_consent"}
_ALLOWED_HISTORY_FIELDS = {
    "chief_complaint","eye_affected","since_when","squint_type","frequency","birth_type",
    "delivery_type","birth_weight","birth_complications","milestone_delay",
    "seizures","systemic_disease","systemic_surgery","immunisation_status",
    "maternal_antenatal_history","family_history","consanguinity",
    "previous_glasses","previous_surgery"
}
_ALLOWED_SYMPTOM_FIELDS = {
    "eye_turn","eye_rubbing","headache","photophobia","nystagmus",
    "ptosis","head_tilt","double_vision"
}
_ALLOWED_APPOINTMENT_FIELDS = {"visit_type","preferred_datetime","special_needs"}

def save_consent_field(patient_id, field, value):
    if field not in _ALLOWED_CONSENT_FIELDS: raise ValueError(f"Bad consent field {field}")
    conn = get_conn(); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO consent(patient_id) VALUES(?)", (patient_id,))
    c.execute(f"UPDATE consent SET {field}=?, signed_at=CURRENT_TIMESTAMP WHERE patient_id=?",
              (1 if value else 0, patient_id))
    conn.commit(); conn.close()

def save_history_field(patient_id, field, value):
    if field not in _ALLOWED_HISTORY_FIELDS: raise ValueError(f"Bad history field {field}")
    conn = get_conn(); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO clinical_history(patient_id) VALUES(?)", (patient_id,))
    c.execute(f"UPDATE clinical_history SET {field}=? WHERE patient_id=?", (value, patient_id))
    conn.commit(); conn.close()

def save_symptom_field(patient_id, field, value):
    if field not in _ALLOWED_SYMPTOM_FIELDS: raise ValueError(f"Bad symptom field {field}")
    conn = get_conn(); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO symptoms(patient_id) VALUES(?)", (patient_id,))
    c.execute(f"UPDATE symptoms SET {field}=? WHERE patient_id=?", (value, patient_id))
    conn.commit(); conn.close()

def save_appointment_field(patient_id, field, value):
    if field not in _ALLOWED_APPOINTMENT_FIELDS: raise ValueError(f"Bad appointment field {field}")
    conn = get_conn(); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO appointments(patient_id) VALUES(?)", (patient_id,))
    c.execute(f"UPDATE appointments SET {field}=? WHERE patient_id=?", (value, patient_id))
    conn.commit(); conn.close()
