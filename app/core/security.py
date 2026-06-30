import json
import secrets
import logging
from fastapi import Request, HTTPException, Depends
from itsdangerous import Signer, BadSignature
from .database import config

if config.get_config("app.debug", False):
    SECRET_KEY = config.get_config("app.key", "sfjsdghfdkjdlk")
    # logging.info("Enable default key for debug mode.")
else:
    SECRET_KEY = secrets.token_hex(64)
    # logging.info("Generated secret key.")

signer = Signer(SECRET_KEY)

class AuthClient:

    @staticmethod
    def encrypt_session(user_dict: dict) -> str:
        json_str = json.dumps(user_dict)
        return signer.sign(json_str.encode('utf-8')).decode('utf-8')

    @staticmethod
    def get_current_user(request: Request) -> dict:
        encrypted_cookie = request.cookies.get("session_user")

        if not encrypted_cookie:
            raise HTTPException(status_code=401, detail="Not authenticated")

        try:
            unsigned_bytes = signer.unsign(encrypted_cookie.encode('utf-8'))
            return json.loads(unsigned_bytes.decode('utf-8'))
        except BadSignature:
            raise HTTPException(status_code=401, detail="Invalid token or tampered cookie")

    @staticmethod
    def is_user_admin(current_user: dict = Depends(get_current_user)) -> bool:
        if not current_user.get("admin", False):
            raise HTTPException(status_code=403, detail="Forbidden to control")
        return current_user