import secrets
import string
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address
from discord import AllowedMentions

def generate_random_password(length=20):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))

limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory="templates")
allowmention = AllowedMentions.none()