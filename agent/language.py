"""Telling Spanish from English, for the fixed replies that skip the model.

The model already answers in the user's language; this is only for texts
written in code, such as the off-topic refusal.
"""

import re

SPANISH_CHARACTERS = re.compile(r"[¿¡ñáéíóú]", re.IGNORECASE)
SPANISH_WORDS = re.compile(
    r"\b(qué|que|cómo|como|cuál|cual|dónde|donde|cuándo|cuando|hola|gracias|por|favor"
    r"|el|la|los|las|un|una|es|son|de|del|en|para|con|hace|hoy|dime|cuéntame|cuentame"
    r"|tiempo|quién|quien|ganó|gano|mi|me|llamo|puedes|sobre)\b",
    re.IGNORECASE,
)


def is_spanish(text: str) -> bool:
    """Spanish punctuation/accents, or at least two common Spanish words."""
    if SPANISH_CHARACTERS.search(text):
        return True
    return len(set(word.lower() for word in SPANISH_WORDS.findall(text))) >= 2
