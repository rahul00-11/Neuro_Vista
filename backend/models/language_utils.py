from __future__ import annotations
import re

def validate_child_age(age: int) -> tuple:
    if age < 0:   return False, "Age cannot be negative."
    if age > 18:  return False, "This clinic is for children aged 0–18 only. Please visit a general ophthalmologist for patients above 18."
    return True, ""

def detect_language(text: str) -> str:
    t = text.lower()
    if any(s in t for s in ["hindi", "hindi mein", "english nahi"]):
        return "hi"
    if any(s in t for s in ["hinglish", "mix", "dono"]):
        return "hinglish"
    return "en"

# ── Shared tokenizer ─────────────────────────────────────────────────────────
# IMPORTANT: this deliberately does NOT use \w-based regex tokenizing.
# Python's \w excludes Unicode "combining mark" characters (category Mn/Mc) —
# and Devanagari vowel signs/nasalization marks (ा ँ ी ं etc.) are exactly
# that. A \w-based split silently breaks Hindi words apart at every vowel
# sign ("हाँ" -> just "ह"), causing Yes/No and ending-phrase detection to fail
# on any Hindi text. Instead we strip ONLY actual punctuation characters and
# split on whitespace, leaving every language's letters completely untouched.
_PUNCT_RE = re.compile(r"[।,.!?;:\"'`()\[\]{}]+")

def tokenize(text: str) -> set:
    t = _PUNCT_RE.sub(" ", (text or "").strip().lower())
    return set(t.split())

# ── Answer validation for the deterministic module flows ──────────────────
# Small, dependency-free parsers so questions (Yes/No, choices, free text)
# are validated server-side instead of trusting the LLM to enforce them.

_YES_WORDS = {"yes","y","yeah","yep","sure","ok","okay","haan","ha","han",
              "हाँ","हां","theek","thik hai","theek hai"}
_NO_WORDS  = {"no","n","nope","nahi","nahin","नहीं","na"}

def parse_yes_no(text: str):
    """Returns (is_valid, bool_value_or_None)."""
    t = (text or "").strip().lower()
    tokens = tokenize(text)
    if t in _YES_WORDS or tokens & _YES_WORDS:
        return True, True
    if t in _NO_WORDS or tokens & _NO_WORDS:
        return True, False
    return False, None

def parse_choice(text: str, options: dict):
    """options: {normalized_value: [keyword,...]}. Returns (is_valid, normalized_value_or_None)."""
    t = (text or "").strip().lower()
    for value, keywords in options.items():
        if any(kw in t for kw in keywords):
            return True, value
    return False, None

def validate_free_text(text: str, min_len: int = 1):
    """Returns (is_valid, error_message_or_None). Rejects empty/whitespace-only answers."""
    if text is None or len(text.strip()) < min_len:
        return False, "Please share a brief answer so I can record it correctly."
    return True, None
