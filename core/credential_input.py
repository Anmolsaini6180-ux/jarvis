"""Local credential format checks; authentication remains the provider's job."""
import re

class InvalidCredential(ValueError):
    pass

def validate_gemini_key(value):
    # Check the original input before trimming: multiline shell/header pastes
    # must never become a credential after normalization.
    if not isinstance(value, str) or any(c in value for c in '\r\n\x00'):
        raise InvalidCredential('Paste one Gemini API key, without commands, headers or newlines.')
    key = value.strip()
    if not re.fullmatch(r'AIza[A-Za-z0-9_-]{20,124}', key):
        raise InvalidCredential('Paste only the Gemini API key starting with AIza. Commands, JSON and headers are not accepted.')
    from core.redaction import register
    register(key)
    return key

def plausible(value):
    try:
        validate_gemini_key(value)
        return True
    except InvalidCredential:
        return False
