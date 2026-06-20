import json
import aiohttp
import logging
from fastapi import HTTPException
from fastapi.requests import Request

class DiscordAuthService:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.token_url = "https://discord.com/api/v10/oauth2/token"
        self.user_url = "https://discord.com/api/v10/users/@me"

    def get_login_url(self) -> str:
        return (
            f"https://discord.com/api/oauth2/authorize"
            f"?client_id={self.client_id}"
            f"&redirect_uri={self.redirect_uri}"
            f"&response_type=code"
            f"&scope=identify%20email"
        )

    async def get_user_data(self, code: str) -> dict:
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        async with aiohttp.ClientSession() as session:
            async with session.post(self.token_url, data=data, headers=headers) as token_resp:
                if token_resp.status != 200:
                    raise Exception("Failed to get token from Discord")
                token_json = await token_resp.json()
                access_token = token_json.get("access_token")
            auth_headers = {"Authorization": f"Bearer {access_token}"}
            
            async with session.get(self.user_url, headers=auth_headers) as user_resp:
                if user_resp.status != 200:
                    raise Exception("Failed to get user data from Discord")
                return await user_resp.json()
    
    @staticmethod
    def get_current_user(request: Request) -> str:
        user_data = request.cookies.get("session_user")

        if not user_data:
            raise HTTPException(
                status_code=307,
                detail="Not authenticated",
                headers={"Location": "/"},
            )

        return json.loads(user_data)