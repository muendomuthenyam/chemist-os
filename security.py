import hashlib
import os

SECURITY_SALT = os.getenv("SECURITY_SALT", "ChemistOS_Salt_9918237")

def hash_pin(pin: str) -> str:
    """Hashes a numeric PIN securely using SHA-256 with salt."""
    combined = f"{str(pin).strip()}{SECURITY_SALT}"
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()

def verify_pin(input_pin: str, stored_hash: str) -> bool:
    """Verifies user-entered PIN against stored database hash."""
    return hash_pin(input_pin) == stored_hash

def is_valid_pin(pin: str) -> bool:
    """Validates that PIN is exactly 4 numeric digits."""
    return len(str(pin).strip()) == 4 and str(pin).strip().isdigit()