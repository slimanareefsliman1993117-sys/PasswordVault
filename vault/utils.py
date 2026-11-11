from cryptography.fernet import Fernet
from django.conf import settings
import logging
import secrets
import string
logger = logging.getLogger(__name__)
#===============================================================================
def generate_password(length=12, use_uppercase=True, use_numbers=True, use_special=True):
    """Generate a random password with customizable options."""
    if length < 8 or length > 32:
        raise ValueError("Password length must be between 8 and 32 characters")

    # Define character sets
    chars = string.ascii_lowercase
    if use_uppercase:
        chars += string.ascii_uppercase
    if use_numbers:
        chars += string.digits
    if use_special:
        chars += string.punctuation

    if not chars:
        raise ValueError("At least one character set must be selected")

    # Ensure at least one character from each selected set
    password = [secrets.choice(string.ascii_lowercase)]
    if use_uppercase:
        password.append(secrets.choice(string.ascii_uppercase))
    if use_numbers:
        password.append(secrets.choice(string.digits))
    if use_special:
        password.append(secrets.choice(string.punctuation))
    password.extend(secrets.choice(chars) for _ in range(length - len(password)))

    # Shuffle the password
    secrets.SystemRandom().shuffle(password)
    return ''.join(password)
#===============================================================================
def check_password_strength(password):
    """Analyze password strength and return strength level and feedback."""
    length = len(password)
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_number = any(c.isdigit() for c in password)
    has_special = any(c in string.punctuation for c in password)

    # Initialize feedback list
    feedback = []

    # Check mandatory requirements
    if not has_upper:
        feedback.append("Add at least one uppercase letter (A-Z).")
    if not has_lower:
        feedback.append("Add at least one lowercase letter (a-z).")
    if not has_number:
        feedback.append("Add at least one number (0-9).")
    if not has_special:
        feedback.append("Add at least one special character (e.g., !@#$%^&*).")
    if length < 8:
        feedback.append("Password must be at least 8 characters long.")

    # Determine strength
    if length < 8 or not (has_upper and has_lower and has_number and has_special):
        strength = "weak"
        if not feedback:
            feedback.append("Password is too short. Use at least 8 characters and include uppercase, lowercase, numbers, and special characters.")
    elif length <= 12:
        strength = "moderate"
        feedback.append("Consider making the password longer (>12 characters) for extra security.")
    else:
        strength = "strong"
        if not feedback:
            feedback.append("Excellent password! It's long and includes all required character types.")

    return strength, " ".join(feedback)
#===============================================================================
def encrypt_password(password):
    return Fernet(settings.ENCRYPTION_KEY.encode()).encrypt(password.encode())


def decrypt_password(encrypted_password):
    return Fernet(settings.ENCRYPTION_KEY.encode()).decrypt(bytes(encrypted_password)).decode()
