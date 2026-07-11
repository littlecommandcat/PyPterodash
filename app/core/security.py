import datetime
import logging
import secrets
from datetime import timezone, timedelta

from fastapi import Depends, HTTPException, Request
from pymongo import MongoClient

from .database import config, datamanager

SESSION_COOKIE_NAME = "session_user"
SESSION_TTL_SECONDS = 60 * 60 * 3


class _SessionStore:
    def __init__(self):
        uri = config.get_config("mongo_uri")
        db_name = config.get_config("database.db")
        self.client = MongoClient(uri)
        self.collection = self.client[db_name]["sessions"]
        try:
            self.collection.create_index("session_id", unique=True)
            self.collection.create_index("expires_at", expireAfterSeconds=0)
        except Exception as exc:
            logging.warning(f"Session index setup skipped: {exc}")

    def create(self, user_dict: dict) -> str:
        session_id = secrets.token_urlsafe(32)
        now = datetime.datetime.now(timezone.utc)
        payload = {
            "session_id": session_id,
            "user": {
                "id": str(user_dict.get("id")),
                "username": user_dict.get("username"),
                "email": user_dict.get("email"),
                "avatar": user_dict.get("avatar"),
                "global_name": user_dict.get("global_name"),
            },
            "created_at": now,
            "expires_at": now + timedelta(seconds=SESSION_TTL_SECONDS),
        }
        self.collection.insert_one(payload)
        return session_id

    def get(self, session_id: str) -> dict | None:
        session = self.collection.find_one({"session_id": session_id})
        if not session:
            return None

        expires_at = session.get("expires_at")
        if expires_at and expires_at < datetime.datetime.now(timezone.utc):
            self.collection.delete_one({"session_id": session_id})
            return None

        user = session.get("user") or {}
        if not user.get("id"):
            return None
        return user

    def delete(self, session_id: str) -> None:
        self.collection.delete_one({"session_id": session_id})


_session_store = _SessionStore()


class AuthClient:
    @staticmethod
    def create_session(user_dict: dict) -> str:
        return _session_store.create(user_dict)

    @staticmethod
    def get_current_user(request: Request) -> dict:
        session_id = request.cookies.get(SESSION_COOKIE_NAME)

        if not session_id:
            raise HTTPException(status_code=401, detail="Not authenticated")

        user = _session_store.get(session_id)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid or expired session")

        return user

    @staticmethod
    def delete_session(request: Request) -> None:
        session_id = request.cookies.get(SESSION_COOKIE_NAME)
        if session_id:
            _session_store.delete(session_id)

    @staticmethod
    async def is_user_admin(
        current_user: dict = Depends(AuthClient.get_current_user)
    ) -> dict | None:
        user = datamanager.find_one({"discord_id": current_user.get("id")})
        if not user or not user.get("admin", False):
            raise HTTPException(
                status_code=403,
                detail="Forbidden to control"
            )

        return user