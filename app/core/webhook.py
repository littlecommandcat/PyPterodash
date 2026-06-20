import aiohttp
import json
import logging
from io import BytesIO
from .database import config
from discord import Embed, AllowedMentions, Button, Attachment


class DiscordWebhook:
    def __init__(self, url: str = None):
        self.url: str | None = url
        self.session: aiohttp.ClientSession = None
    
    def _init_session(self):
        if not self.session or self.session.closed:
            if not self.url:
                self.url = config.get_config("discord_webhook")
            
            self.session = aiohttp.ClientSession(base_url=self.url if self.url.endswith("/") else f"{self.url}/")
        
        return self.session

    async def close(self):
        try:
            if self.session and not self.session.closed:
                await self.session.close()
                self.session = None
        except Exception as e:
            logging.error(f"Error closing Discord webhook session: {e}")

    async def post(
        self,
        content: str = None,
        *,
        username: str = None,
        avatar_url: str = None,
        tts: bool = False,
        embeds: list[Embed] = None,
        allowed_mentions: AllowedMentions = None,
        buttons: list[Button] = None,
        files: list[Attachment] = None
    ):
        data = {}
        if content:
            data["content"] = content
        if username:
            data["username"] = username
        if avatar_url:
            data["avatar_url"] = avatar_url
        data["tts"] = tts
        if embeds:
            data["embeds"] = [embed.to_dict() for embed in embeds]
        if allowed_mentions:
            data["allowed_mentions"] = allowed_mentions.to_dict()
        if buttons:
            data["components"] = [{
                "type": 1,
                "components": [button.to_dict() for button in buttons]
            }]

        headers = {"Content-Type": "application/json"}

        file_data = []

        self._init_session()
        if files:
            if isinstance(files, (list, tuple)) is False:
                files = [files]

            for idx, file in enumerate(files):
                file_bytes = await file.read()
                file_data.append(
                    (f"files[{idx}]", BytesIO(file_bytes), file.filename, "application/octet-stream")
                )

        if file_data:
            form = aiohttp.FormData()
            form.add_field("payload_json", json.dumps(data))

            for fieldname, fileobj, filename, content_type in file_data:
                form.add_field(fieldname, fileobj, filename=filename, content_type=content_type)

            resp = await self.session.post(self.url, data=form)
            return resp.status, await resp.text()
        else:
            resp = await self.session.post(self.url, json=data, headers=headers)
            return resp.status, await resp.text()

dchook = DiscordWebhook()