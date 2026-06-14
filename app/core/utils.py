from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address
import secrets
import string
import dhooks
import discord

def generate_random_password(length=12):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))

def get_webhook():
    from .database import config
    webhook = dhooks.Webhook(url=config.get_config("webhook"), is_async=True)
    return webhook

limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory="templates")
allowmention = discord.AllowedMentions.none()