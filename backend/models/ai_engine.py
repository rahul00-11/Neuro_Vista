from __future__ import annotations
import httpx
from typing import List, Dict
from config import GROQ_API_KEY
from models.language_utils import tokenize

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL    = "llama-3.3-70b-versatile"  # stronger instruction-following than 3.1-8b-instant; only used for Module 6 free-form Q&A now

# ── Agent System Prompts ───────────────────────────────────────────────────────
# Layer 1: Patient Engagement Agents (6 total)
# Based on NeuroVista AI platform — Dr. Trupti Kadam Lambat
# Little Angels Superspecialty Eye Clinic, Nagpur
# PEDIATRIC ONLY — 0 to 18 years

CLINIC_CONTEXT = """
CLINIC: Little Angels Superspecialty Eye Clinic, Nagpur
DOCTOR: Dr. Trupti Kadam Lambat — Pediatric, Neuro, Squint & Comprehensive Ophthalmologist.
  IMPORTANT: She is an EYE DOCTOR (ophthalmologist) who sub-specializes in neuro-ophthalmology
  (eye conditions connected to the nervous system, e.g. squint, nystagmus, optic nerve issues).
  She is NOT a general neurologist / brain doctor. NEVER refer to her as "a neurologist" —
  always describe her as a pediatric/neuro-ophthalmologist or simply "the eye doctor".
PLATFORM: NeuroVista AI — Clinician-Led Digital Health Platform
PATIENTS: Children ONLY, age 0–18 years. You speak with parent/guardian.
"""

AGENTS = {

    # ── Module 1: Registration Agent ──────────────────────────────────────────
    1: {
        "en": f"""{CLINIC_CONTEXT}
You are the REGISTRATION AGENT.
Collect in this order, ONE question at a time:
1. Child's full name
2. Child's age in years (MUST be 0–18. Refuse if >18 — this is a pediatric clinic)
3. Age in months (e.g. "3 months" if child is 1yr 3mo)
4. Date of birth (DD/MM/YYYY)
5. Sex — Male or Female
6. Parent/Guardian's full name and relation (Mother / Father / Grandparent / Other)
7. Mobile number
8. Address (optional — accept 'skip')

RULES:
- Warm, empathetic tone — parents are anxious about their child
- ONE question at a time only
- Age >18: "This clinic is for children aged 0–18 only. Please visit a general ophthalmologist."
- NEVER discuss medical findings, diagnosis, or treatment — that's Dr. Trupti Kadam's job
- After collecting all 8 points say: "Registration complete! Moving to consent form." """,

        "hi": f"""{CLINIC_CONTEXT}
आप REGISTRATION AGENT हैं।
एक-एक करके यह जानकारी लीजिए:
1. बच्चे का पूरा नाम
2. बच्चे की उम्र (0–18 साल — अगर 18+ हो तो विनम्रता से मना करें)
3. महीनों में उम्र
4. जन्मतिथि (DD/MM/YYYY)
5. लिंग — Male या Female
6. माता-पिता/अभिभावक का नाम और संबंध
7. मोबाइल नंबर
8. पता (वैकल्पिक)

नियम: एक बार में एक ही सवाल। विनम्र रहें। कोई medical opinion नहीं।""",

        "hinglish": f"""{CLINIC_CONTEXT}
Aap REGISTRATION AGENT ho.
Ek-ek karke yeh collect karo:
1. Bachche ka poora naam
2. Umar (0–18 saal — 18+ ho to politely refuse karo)
3. Mahino mein umar
4. Date of birth
5. Sex — Male ya Female
6. Parent/Guardian ka naam aur rishta
7. Mobile number
8. Address (optional — skip allowed)

Rules: Ek baar mein ek sawaal. Warm raho. Koi medical opinion nahi."""
    },

    # ── Module 6: Caregiver Education Agent ───────────────────────────────────
    6: {
        "en": f"""{CLINIC_CONTEXT}
You are the CAREGIVER EDUCATION AGENT. Final module.
Provide helpful, simple education to the parent/caregiver:
1. "Before we finish, may I share some helpful information about your child's eye health?"
2. If Yes → Share 3–4 key points relevant to pediatric eye care:
   - Early detection of squint/lazy eye is crucial before age 7
   - Regular eye exams matter even if no obvious problem is seen
   - Screen time should be limited for children under 5
   - Red flags to watch: head tilting, eye rubbing, squinting to see
3. "Do you have any questions about eye care for your child?"
4. Answer questions simply, always ending with "Dr. Trupti Kadam will discuss this in detail."
5. Final message: "Thank you for visiting Little Angels Eye Clinic. We look forward to caring for [child's name]. 🙏"

RULES:
- Educational only — no diagnosis, no treatment advice
- Simple language — parent may not have medical background
- LANGUAGE: if the parent writes in a language or mix different from what's expected here (e.g. Marathi, Bengali, pure English, or a different Hindi/English mix), reply naturally in THAT language/style instead — always prioritize what the parent will actually understand over strictly matching this prompt's language.""",

        "hi": f"""{CLINIC_CONTEXT}
आप CAREGIVER EDUCATION AGENT हैं।
1. "क्या मैं बच्चे की आँखों के बारे में कुछ जानकारी दे सकता हूँ?"
2. अगर हाँ → 4 बातें:
   - 7 साल से पहले भेंगापन का इलाज जरूरी
   - नियमित आँखों की जांच महत्वपूर्ण
   - 5 साल से कम बच्चों में screen time कम रखें
   - Red flags: सिर टेढ़ा करना, आँखें रगड़ना
3. "कोई सवाल है?"
4. अंत में: "धन्यवाद! Little Angels Clinic में आपका स्वागत है। 🙏"

नियम: अगर parent किसी और भाषा में लिखे (जैसे Marathi, Bengali, pure English), तो उसी भाषा में जवाब दें — parent को समझ आना सबसे ज़रूरी है।""",

        "hinglish": f"""{CLINIC_CONTEXT}
Aap CAREGIVER EDUCATION AGENT ho.
1. "Kuch helpful information share karun bachche ki aankhon ke baare mein?"
2. Haan → 4 points:
   - 7 saal se pehle squint ka treatment zaruri hai
   - Regular eye check-up important hai
   - 5 saal se kam baccho mein screen time kam karo
   - Red flags: sir tedha karna, aanch ragadna
3. "Koi sawaal?"
4. Ant mein: "Shukriya! Little Angels Clinic mein aapka swagat hai. 🙏"

Rule: Agar parent kisi aur bhasha mein likhe (jaise Marathi, Bengali, pure English), to usi bhasha mein reply karo — parent ko samajh aana sabse zaruri hai."""
    }
}

FALLBACKS = {
    "en":       "Welcome to Little Angels Eye Clinic! I'm NeuroVista AI. Let's begin. What is the child's full name?",
    "hi":       "Little Angels Eye Clinic में स्वागत है! मैं NeuroVista AI हूँ। बच्चे का पूरा नाम बताइए।",
    "hinglish": "Little Angels Eye Clinic mein swagat hai! Main NeuroVista AI hoon. Bachche ka naam batao."
}

# ── Deterministic module flows (Modules 2–5) ────────────────────────────────
# The backend — not the LLM — owns question order and validation. Each step
# writes straight into its proper clinical table. This is what actually fixes
# "illogical questions" and "no validation": the AI is only used for the
# free-form Q&A in Module 6, never for deciding what to ask or whether an
# answer is acceptable.

_NEGATION_TOKENS = {"no","nahi","nahin","nothing","none","nope","न","नहीं"}
_GENERAL_ILLNESS_HINTS = ["tabiyat","tabiyet","tabyiat","tabiat","bimar","sehat","health","fever","bukhar",
                           "weak","kamzori","unwell","sick","तबियत","बीमार","सेहत","बुखार"]
_EYE_HINTS = ["eye","aankh","squint","vision","dikh","dekh","blur","redness","watering",
              "tedha","cross","droop","pupil","glasses","chashma","nazar",
              "आँख","आंख","भेंगा","धुंधला","चश्मा","नज़र"]

def _no_complaint_reported(data: dict) -> bool:
    """True if the parent's chief_complaint answer doesn't actually describe
    an eye/vision problem — either a plain negative ('No'/'Nahi') or a
    generic non-eye complaint like 'tabiyat kharab rehti hai' (general
    unwellness, no eye mentioned). Used to skip the eye-specific follow-ups
    (which eye, since when, constant or intermittent) that don't make sense
    without an actual eye complaint. If the answer mentions both (e.g. "eye
    pain and fever"), it's treated as a real eye complaint and nothing skips."""
    t = (data.get("chief_complaint") or "").strip().lower()
    if not t:
        return False
    tokens = tokenize(t)
    if t in _NEGATION_TOKENS or (tokens & _NEGATION_TOKENS):
        return True
    mentions_eye = any(h in t for h in _EYE_HINTS)
    mentions_general_illness = any(h in t for h in _GENERAL_ILLNESS_HINTS)
    return mentions_general_illness and not mentions_eye

FLOWS = {
    # Module 2 — Consent
    2: {
        "intro": {
            "en": "Registration is done. I just need to confirm a few consents.",
            "hi": "रजिस्ट्रेशन पूरा हो गया। अब कुछ सहमति चाहिए।",
            "hinglish": "Registration ho gaya. Ab kuch consent chahiye."
        },
        "table": "consent",
        "steps": [
            {"field": "data_consent", "type": "yesno", "q": {
                "en": "We will store your child's medical records securely for clinical use. Do you consent? (Yes/No)",
                "hi": "आपके बच्चे का रिकॉर्ड सुरक्षित रखा जाएगा। आप सहमत हैं? (हाँ/नहीं)",
                "hinglish": "Aapke bachche ka record secure rakha jayega. Consent hai? (Haan/Nahi)"}},
            {"field": "photo_consent", "type": "yesno", "q": {
                "en": "We may photograph your child's eyes for clinical records. Do you consent? (Yes/No)",
                "hi": "आँखों की फोटो ली जा सकती है। सहमति है? (हाँ/नहीं)",
                "hinglish": "Aankhon ki photo li ja sakti hai. Consent? (Haan/Nahi)"}},
            {"field": "research_consent", "type": "yesno", "q": {
                "en": "De-identified data may be used for medical research to help other children. Do you consent? (Yes/No)",
                "hi": "गोपनीय डेटा शोध के लिए उपयोग हो सकता है। सहमति है? (हाँ/नहीं)",
                "hinglish": "Research ke liye data use ho sakta hai. Consent? (Haan/Nahi)"}},
        ],
        "complete": {
            "en": "Thank you. Consent recorded. Proceeding to medical history.",
            "hi": "धन्यवाद। सहमति दर्ज हो गई। अब मेडिकल हिस्ट्री लेते हैं।",
            "hinglish": "Shukriya. Consent record ho gaya. Ab medical history lete hain."
        }
    },

    # Module 3 — History Collection
    3: {
        "intro": {
            "en": "Consent recorded. Now I'll ask about your child's medical history.",
            "hi": "सहमति दर्ज हो गई। अब मेडिकल हिस्ट्री के बारे में पूछूंगा।",
            "hinglish": "Consent record ho gaya. Ab medical history ke baare mein poochunga."
        },
        "table": "clinical_history",
        "steps": [
            {"field": "chief_complaint", "type": "text", "q": {
                "en": "What is the main eye/vision problem you noticed in your child?",
                "hi": "मुख्य समस्या क्या है जो आपने बच्चे में देखी?",
                "hinglish": "Main problem kya hai jo aapne bachche mein dekhi?"}},
            {"field": "eye_affected", "type": "text", "q": {
                "en": "Which eye — Right, Left, or Both?",
                "hi": "कौन सी आँख — Right, Left, या Both?",
                "hinglish": "Kaun si aankh — Right, Left, ya Both?"},
                "skip_if": _no_complaint_reported},
            {"field": "since_when", "type": "text", "q": {
                "en": "Since when have you noticed this?",
                "hi": "यह कब से देखा है?",
                "hinglish": "Yeh kab se dekha hai?"},
                "skip_if": _no_complaint_reported},
            {"field": "squint_type", "type": "text", "q": {
                "en": "Is it always present, or does it come and go?",
                "hi": "यह हमेशा रहता है या कभी-कभी?",
                "hinglish": "Yeh hamesha rehta hai ya kabhi kabhi?"},
                "skip_if": _no_complaint_reported},
            {"field": "frequency", "type": "text", "q": {
                "en": "How often does this happen — occasionally, 3–4 times a day, or all the time? And has the child ever seen double (diplopia)?",
                "hi": "यह कितनी बार होता है — कभी-कभी, दिन में 3-4 बार, या हमेशा? और क्या कभी दोहरा दिखा है?",
                "hinglish": "Yeh kitni baar hota hai — kabhi kabhi, din mein 3-4 baar, ya hamesha? Aur kabhi double dikha hai?"},
                "skip_if": _no_complaint_reported},
            {"field": "birth_type", "type": "text", "q": {
                "en": "Now a few questions about birth and early health — this helps the doctor understand any early risk factors. Was your child born full-term (9 months) or premature?",
                "hi": "अब जन्म और शुरुआती स्वास्थ्य के बारे में कुछ सवाल — यह डॉक्टर को जोखिम समझने में मदद करता है। बच्चा समय पर पैदा हुआ या समय से पहले?",
                "hinglish": "Ab birth aur early health ke baare mein kuch sawaal — yeh doctor ko risk samajhne mein madad karta hai. Bachcha time par paida hua ya pehle?"}},
            {"field": "delivery_type", "type": "text", "q": {
                "en": "Normal delivery or C-section (LSCS)?",
                "hi": "Normal delivery या LSCS?",
                "hinglish": "Normal delivery ya LSCS?"}},
            {"field": "birth_weight", "type": "text", "q": {
                "en": "What was the birth weight? Did the baby have any breathing difficulty, infection, seizures, low blood sugar, or jaundice right after birth?",
                "hi": "जन्म का वजन कितना था? क्या जन्म के बाद सांस लेने में तकलीफ, इन्फेक्शन, दौरे, ब्लड शुगर कम होना, या पीलिया हुआ था?",
                "hinglish": "Birth weight kitna tha? Kya birth ke baad saans lene mein takleef, infection, seizures, blood sugar kam hona, ya jaundice hua tha?"},
                "also_save_as": "birth_complications"},
            {"field": "milestone_delay", "type": "text", "q": {
                "en": "Milestones — neck holding, sitting, walking, talking — any delays?",
                "hi": "विकास के पड़ाव — गर्दन संभालना, बैठना, चलना, बोलना — कोई देरी?",
                "hinglish": "Milestones — neck holding, sitting, walking, talking — koi delay?"}},
            {"field": "seizures", "type": "text", "q": {
                "en": "Has your child ever had seizures or fits?",
                "hi": "क्या बच्चे को कभी दौरे आए हैं?",
                "hinglish": "Kya bachche ko kabhi fits/seizures aaye hain?"}},
            {"field": "systemic_disease", "type": "text", "q": {
                "en": "Does your child have any other medical condition or diagnosed syndrome, apart from the eye problem? (type 'no' if none)",
                "hi": "क्या बच्चे को आँख की समस्या के अलावा कोई और बीमारी या सिंड्रोम है? (कुछ नहीं तो 'no' लिखें)",
                "hinglish": "Kya bachche ko aankh ke alawa koi aur bimari ya syndrome hai? (kuch nahi to 'no' likho)"}},
            {"field": "systemic_surgery", "type": "text", "q": {
                "en": "Has your child had any surgery other than eye surgery? (type 'no' if none)",
                "hi": "क्या बच्चे की आँख के अलावा कोई और सर्जरी हुई है? (नहीं तो 'no' लिखें)",
                "hinglish": "Kya bachche ki aankh ke alawa koi aur surgery hui hai? (nahi to 'no' likho)"}},
            {"field": "previous_glasses", "type": "text", "q": {
                "en": "Has the child worn glasses before, or had any previous eye surgery or laser treatment?",
                "hi": "क्या पहले चश्मा लगा है, या आँख का ऑपरेशन/लेज़र हुआ है?",
                "hinglish": "Kya pehle chashma laga hai, ya aankh ka operation/laser hua hai?"},
                "also_save_as": "previous_surgery"},
            {"field": "immunisation_status", "type": "text", "q": {
                "en": "Is your child's vaccination schedule up to date? Any other health issues you've noticed?",
                "hi": "क्या बच्चे के टीकाकरण पूरे हैं? कोई और स्वास्थ्य समस्या नोटिस की है?",
                "hinglish": "Kya bachche ke vaccination poore hain? Koi aur health issue notice kiya hai?"}},
            {"field": "maternal_antenatal_history", "type": "text", "q": {
                "en": "One last set of questions, about the pregnancy — during pregnancy, did the mother have high blood pressure, diabetes, heart disease, a major fever/illness, or take any medication?",
                "hi": "अब गर्भावस्था के बारे में — क्या माँ को गर्भावस्था के दौरान BP, diabetes, दिल की बीमारी, तेज बुखार, या कोई दवा लेनी पड़ी?",
                "hinglish": "Ab pregnancy ke baare mein — kya maa ko pregnancy ke dauran BP, diabetes, dil ki bimari, tez bukhar, ya koi dawai leni padi?"}},
            {"field": "family_history", "type": "text", "q": {
                "en": "Any family history of eye problems or neurological conditions?",
                "hi": "परिवार में आँख या न्यूरो संबंधी बीमारी?",
                "hinglish": "Family mein aankh ya neuro se related koi bimari?"}},
            {"field": "consanguinity", "type": "text", "q": {
                "en": "Last question — are the child's parents related by blood (e.g. cousins)? This helps us understand genetic risk factors, and is completely confidential.",
                "hi": "आखिरी सवाल — क्या बच्चे के माता-पिता आपस में रक्त संबंधी हैं (जैसे चचेरे भाई-बहन)? यह गोपनीय है और अनुवांशिक जोखिम समझने में मदद करता है।",
                "hinglish": "Aakhri sawaal — kya bachche ke parents aapas mein blood relation mein hain (jaise cousins)? Yeh confidential hai aur genetic risk samajhne mein madad karta hai."}},
        ],
        "complete": {
            "en": "Thank you — that's the full history recorded. Dr. Trupti Kadam will review this before your examination.",
            "hi": "धन्यवाद — पूरी हिस्ट्री दर्ज हो गई। डॉ. तृप्ति कदम जांच से पहले इसे देखेंगी।",
            "hinglish": "Shukriya — puri history record ho gayi. Dr. Trupti Kadam examination se pehle isse dekhengi."
        }
    },

    # Module 4 — Symptom Checker
    4: {
        "intro": {
            "en": "History recorded. Now a few quick symptom questions.",
            "hi": "हिस्ट्री दर्ज हो गई। अब कुछ लक्षणों के सवाल।",
            "hinglish": "History record ho gayi. Ab kuch symptoms ke sawaal."
        },
        "table": "symptoms",
        "steps": [
            {"field": "eye_turn", "type": "text", "q": {
                "en": "Does your child's eye turn inward, outward, upward, or not at all?",
                "hi": "आँख किस तरफ मुड़ती है — अंदर, बाहर, ऊपर, या नहीं?",
                "hinglish": "Aankh kis taraf mudti hai — andar, bahar, upar, ya nahi?"}},
            {"field": "eye_rubbing", "type": "text", "q": {
                "en": "Does your child rub their eyes frequently?",
                "hi": "क्या बच्चा बार-बार आँखें रगड़ता है?",
                "hinglish": "Kya bachcha baar baar aankhein ragadta hai?"}},
            {"field": "headache", "type": "text", "q": {
                "en": "Do they complain of headaches or seem to have head pain?",
                "hi": "क्या सिरदर्द की शिकायत करता है?",
                "hinglish": "Kya sir dard ki shikayat karta hai?"}},
            {"field": "photophobia", "type": "text", "q": {
                "en": "Any sensitivity to bright light?",
                "hi": "तेज रोशनी से परेशानी होती है?",
                "hinglish": "Tej roshni se pareshani hoti hai?"}},
            {"field": "nystagmus", "type": "text", "q": {
                "en": "Have you noticed involuntary eye movements (eyes shaking/moving on their own)?",
                "hi": "क्या आँखें अपने आप कंपती/हिलती हैं?",
                "hinglish": "Kya aankhein apne aap kaampti/hilti hain?"}},
            {"field": "ptosis", "type": "text", "q": {
                "en": "Is there any drooping of the eyelid?",
                "hi": "क्या पलक झुकी हुई है?",
                "hinglish": "Kya palak jhuki hui hai?"}},
            {"field": "head_tilt", "type": "text", "q": {
                "en": "Does the child tilt or turn their head to see better?",
                "hi": "क्या बच्चा देखने के लिए सिर टेढ़ा करता है?",
                "hinglish": "Kya bachcha dekhne ke liye sir tedha karta hai?"}},
            {"field": "double_vision", "type": "text", "q": {
                "en": "Has the child ever mentioned seeing double?",
                "hi": "क्या बच्चे ने कभी दोहरा दिखने की बात कही है?",
                "hinglish": "Kya bachche ne kabhi double dikhne ki baat kahi hai?"}},
        ],
        "complete": {
            "en": "Thank you — your responses have been noted. Dr. Trupti Kadam will examine these in detail.",
            "hi": "धन्यवाद — आपके जवाब नोट हो गए। डॉ. तृप्ति कदम विस्तार से जांच करेंगी।",
            "hinglish": "Shukriya — aapke jawab note ho gaye. Dr. Trupti Kadam detail mein examine karengi."
        }
    },

    # Module 5 — Appointment
    5: {
        "intro": {
            "en": "Your intake is complete. The doctor is ready for your child's examination.",
            "hi": "इंटेक पूरा हुआ। डॉक्टर जांच के लिए तैयार हैं।",
            "hinglish": "Intake complete. Doctor examination ke liye ready hain."
        },
        "table": "appointments",
        "steps": [
            {"field": "visit_type", "type": "choice", "q": {
                "en": "Is this a walk-in visit today, or do you need to schedule a future appointment? (Reply 'walk-in' or 'schedule')",
                "hi": "आज walk-in है या भविष्य के लिए appointment चाहिए? ('walk-in' या 'schedule' लिखें)",
                "hinglish": "Aaj walk-in hai ya future appointment chahiye? ('walk-in' ya 'schedule' likho)"},
                "options": {
                    "walkin": ["walk-in", "walkin", "walk in", "today", "aaj"],
                    "schedule": ["schedule", "future", "book", "appointment", "later"]
                }},
            {"field": "preferred_datetime", "type": "text", "q": {
                "en": "What date and time works best for you? Clinic hours: Mon–Sat, 10am–6pm",
                "hi": "कौन सी तारीख और समय ठीक रहेगा? क्लिनिक समय: सोम–शनि, 10am–6pm",
                "hinglish": "Kaun si date aur time thik rahega? Clinic hours: Mon-Sat, 10am-6pm"},
                "skip_if": lambda data: data.get("visit_type") == "walkin"},
            {"field": "special_needs", "type": "text", "q": {
                "en": "Any special needs or requests before your appointment? (e.g. translator, wheelchair — or type 'none')",
                "hi": "कोई विशेष जरूरत? (जैसे translator, wheelchair — या 'none' लिखें)",
                "hinglish": "Koi special zaroorat? (jaise translator, wheelchair — ya 'none' likho)"}},
        ],
        "complete": {
            "en": "Your appointment is noted. Please arrive 10 minutes early and bring any previous medical records. Moving to caregiver education.",
            "hi": "Appointment नोट हो गई। 10 मिनट पहले आएं और पुराने मेडिकल रिकॉर्ड लाएं।",
            "hinglish": "Appointment note ho gaya. 10 min pehle aao aur purane medical records lao."
        }
    },
}

EDUCATION_POINTS = {
    "en": [
        "Early detection of squint/lazy eye is crucial before age 7.",
        "Regular eye exams matter even if no obvious problem is seen.",
        "Screen time should be limited for children under 5.",
        "Red flags to watch: head tilting, eye rubbing, squinting to see."
    ],
    "hi": [
        "7 साल से पहले भेंगापन/lazy eye का इलाज जरूरी है।",
        "नियमित आँखों की जांच महत्वपूर्ण है, भले ही कोई समस्या न दिखे।",
        "5 साल से कम बच्चों में screen time कम रखें।",
        "Red flags: सिर टेढ़ा करना, आँखें रगड़ना, देखने के लिए आँखें सिकोड़ना।"
    ],
    "hinglish": [
        "7 saal se pehle squint/lazy eye ka treatment zaruri hai.",
        "Regular eye check-up important hai, chahe koi problem na dikhe.",
        "5 saal se kam baccho mein screen time kam rakho.",
        "Red flags: sir tedha karna, aankh ragadna, dekhne ke liye aankhein sikodna."
    ],
}

EDUCATION_INTRO = {
    "en": "Appointment confirmed! Before we finish, here's some helpful information about your child's eye health:",
    "hi": "Appointment confirm हो गई! खत्म करने से पहले, कुछ जरूरी जानकारी:",
    "hinglish": "Appointment confirm ho gaya! Khatam karne se pehle, kuch zaroori jaankari:"
}

EDUCATION_PROMPT_QUESTIONS = {
    "en": "Do you have any questions about eye care for your child? (Type your question, or 'no' if none)",
    "hi": "क्या आपके कोई सवाल हैं? (सवाल लिखें, या कोई सवाल नहीं तो 'no' लिखें)",
    "hinglish": "Koi sawaal hai? (sawaal likho, ya 'no' likho agar koi sawaal nahi)"
}

_END_TOKENS  = {"no","nope","nothing","none","nahi","नहीं","skip","done","thanks"}
_END_PHRASES = ["no questions", "thank you"]

def is_ending_reply(text: str) -> bool:
    t = (text or "").strip().lower()
    if t in _END_TOKENS or any(p in t for p in _END_PHRASES):
        return True
    tokens = tokenize(t)
    return bool(tokens & _END_TOKENS)

def education_closing(child_name: str, lang: str) -> str:
    name = child_name or "your child"
    return {
        "en": f"Thank you for visiting Little Angels Eye Clinic. We look forward to caring for {name}. 🙏",
        "hi": f"धन्यवाद! Little Angels Clinic में आपका स्वागत है। हम {name} की देखभाल के लिए तैयार हैं। 🙏",
        "hinglish": f"Shukriya! Little Angels Clinic mein aapka swagat hai. Hum {name} ki dekhbhaal ke liye ready hain. 🙏",
    }.get(lang, f"Thank you for visiting Little Angels Eye Clinic. We look forward to caring for {name}. 🙏")

MODULE6_FALLBACK = {
    "en": "That's a great question — Dr. Trupti Kadam will discuss this with you in detail during the examination. Do you have any other questions? (or type 'no' to finish)",
    "hi": "यह अच्छा सवाल है — डॉ. तृप्ति कदम जांच के दौरान इस पर विस्तार से बात करेंगी। कोई और सवाल है? (या खत्म करने के लिए 'no' लिखें)",
    "hinglish": "Yeh accha sawaal hai — Dr. Trupti Kadam examination ke dauran isse detail mein discuss karengi. Koi aur sawaal hai? (ya 'no' likho finish karne ke liye)"
}

async def ask_groq(messages: List[Dict], language: str = "en", module: int = 1) -> str:
    fallback = MODULE6_FALLBACK if module == 6 else FALLBACKS
    if not GROQ_API_KEY or GROQ_API_KEY.strip() in ("", "your_groq_api_key_here"):
        return fallback.get(language, fallback["en"])

    agent = AGENTS.get(module, AGENTS[1])
    system = agent.get(language, agent["en"])

    payload = {
        "model": MODEL,
        "messages": [{"role": "system", "content": system}, *messages],
        "temperature": 0.4,
        "max_tokens": 400,
    }
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=25) as client:
            r = await client.post(GROQ_URL, json=payload, headers=headers)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as e:
        print(f"❌ Groq {e.response.status_code}: {e.response.text[:200]}")
        return fallback.get(language, fallback["en"])
    except Exception as e:
        print(f"❌ Groq error: {e}")
        return fallback.get(language, fallback["en"])
