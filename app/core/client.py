import json
import logging
import pydactyl
import time
import asyncio
from aiohttp import ClientResponse

from .database import config, datamanager
from .utils import generate_random_password


class PterodactylClient:
    def __init__(self):
        self.config = config

        self.url = self.config.get_config("panel_url")
        self.api_key = self.config.get_config("panel_key")
        self.nest_id = self.config.get_config("nest_id")

        self.client = None

        self.request_time = 0
        self.cooldown_time = 2.5
        self.lock = asyncio.Lock()

    def _init_client(self):
        if not self.client:
            self.client = pydactyl.AsyncPterodactylClient(
                self.url,
                self.api_key
            )
        return self.client

    async def close(self):
        try:
            if self.client:
                await self.client.close()
                self.client = None
        except Exception as e:
            logging.error(f"Error closing PterodactylClient session: {e}")

    async def cooldown(self):
        async with self.lock:
            now = time.time()
            cal_time = now - self.request_time

            if cal_time < self.cooldown_time:
                sleep_time = self.cooldown_time - cal_time
                await asyncio.sleep(sleep_time)

            self.request_time = time.time()

    async def check_user(self, discord_id: str, email: str = None) -> tuple[bool, str]:
        try:
            profile = datamanager.find_one(query={"discord_id": str(discord_id)})

            if profile and profile.get("panel_id"):
                return True, str(profile.get("panel_id"))

            if email:
                await self.cooldown()

                params = {"filter[email]": email}
                client = self._init_client()

                response = await client.user.list_users(params=params)

                users_list = (
                    response.get("data")
                    if isinstance(response, dict) and "data" in response
                    else response
                )

                if users_list and len(users_list) > 0:
                    user_data = (
                        users_list[0].get("attributes")
                        if "attributes" in users_list[0]
                        else users_list[0]
                    )
                    panel_id = user_data.get("id")
                    return True, str(panel_id)

            return False, "0"

        except Exception as e:
            logging.error(f"check_user error: {str(e)}")

            profile = datamanager.find_one(query={"discord_id": str(discord_id)})

            if profile and profile.get("panel_id"):
                return True, str(profile.get("panel_id"))

            return False, "0"

    async def get_user_servers(self, panel_id: str) -> list:
        if not panel_id or str(panel_id) == "0":
            return []

        try:
            await self.cooldown()

            client = self._init_client()

            response = await client.user.get_user_info(
                user_id=int(panel_id),
                includes=["servers"]
            )

            if hasattr(response, "json") and callable(getattr(response, "json")):
                raw_data = await response.json()

            elif callable(getattr(response, "read", None)):
                raw_data = json.loads(await response.read())

            else:
                raw_data = response

            data_root = raw_data.get("data", raw_data)
            attributes = data_root.get("attributes", data_root)

            relationships = attributes.get("relationships", {})
            servers_dict = relationships.get("servers", {})

            return servers_dict.get("data", [])

        except Exception as e:
            print(f"[ERROR] get {panel_id} server failed: {e}")
            return []

    async def create_server(
        self,
        name: str,
        user_id: int,
        nest_id: int,
        egg_id: int,
        memory_limit: int,
        disk_limit: int,
        cpu_limit: int = 100,
        swap_limit: int = 0,
        io_limit: int = 500,
        database_limit: int = 0,
        allocation_limit: int = 1,
        backup_limit: int = 0,
        docker_image: str = None,
        startup_cmd: str = None,
        environment: dict = None,
        location_ids: list = None,
        port_range: list = None,
        dedicated_ip: bool = False,
        start_on_completion: bool = True,
        oom_disabled: bool = True,
        default_allocation: int = None,
        additional_allocations: list = None,
        external_id: str = None,
        description: str = None
    ) -> dict:
        try:
            await self.cooldown()

            client = self._init_client()

            response = await client.servers.create_server(
                name=name,
                user_id=user_id,
                nest_id=nest_id,
                egg_id=egg_id,
                memory_limit=memory_limit,
                swap_limit=swap_limit,
                disk_limit=disk_limit,
                cpu_limit=cpu_limit,
                io_limit=io_limit,
                location_ids=location_ids or [],
                port_range=port_range or [],
                environment=environment or {},
                database_limit=database_limit,
                allocation_limit=allocation_limit,
                backup_limit=backup_limit,
                docker_image=docker_image,
                startup_cmd=startup_cmd,
                dedicated_ip=dedicated_ip,
                start_on_completion=start_on_completion,
                oom_disabled=oom_disabled,
                default_allocation=default_allocation,
                additional_allocations=additional_allocations,
                external_id=external_id,
                description=description or "",
            )

            if isinstance(response, dict):
                res_data = response
            elif hasattr(response, "json") and callable(getattr(response, "json")):
                res_data = await response.json()
            else:
                res_data = response

            response = res_data.get("attributes", res_data)

            return {
                "id": response.get("id"),
                "externalId": response.get("external_id"),
                "uuid": response.get("uuid"),
                "identifier": response.get("identifier"),
                "name": response.get("name"),
                "description": response.get("description", ""),
                "suspended": response.get("suspended", False),
                "limits": response.get("limits", {}),
                "featureLimits": response.get("feature_limits", {}),
                "user": response.get("user"),
                "nest": response.get("nest"),
                "egg": response.get("egg"),
                "attributes": {
                    "id": response.get("id"),
                    "identifier": response.get("identifier"),
                    "uuid": response.get("uuid"),
                },
            }

        except Exception as e:
            raise Exception(f"Pydactyl create error: {str(e)}")

    async def delete_server(self, server_id: int, force: bool = True) -> dict:
        client = self._init_client()

        response = await client.servers.delete_server(
            server_id=server_id,
            force=force
        )

        return response if response else {"status": "deleted"}

    async def create_account(
        self,
        discord_id: str,
        email: str,
        name: str = None
    ) -> str | None:
        client = self._init_client()

        response = await client.user.create_user(
            username=name if name else discord_id,
            email=email,
            first_name=discord_id,
            last_name=name if name else discord_id,
            password=generate_random_password(15),
        )

        return str(response.get("id"))


pterclient = PterodactylClient()