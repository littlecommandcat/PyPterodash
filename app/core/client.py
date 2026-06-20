import json
import logging
import time
import asyncio
import aiohttp

from .database import config, datamanager
from .utils import generate_random_password


class PterodactylClient:
    def __init__(self):
        self.config = config
        self.base_url = self.config.get_config("panel_url").rstrip('/')
        self.application_url = self.base_url + '/api/application'
        self.api_key = self.config.get_config("panel_key")
        self.nest_id = self.config.get_config("nest_id")

        self.session = None

        self.request_time = 0
        self.cooldown_time = 2.5
        self.lock = asyncio.Lock()

    def _init_session(self):
        if not self.session or self.session.closed:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Accept-Encoding": "gzip, deflate"
            }
            self.session = aiohttp.ClientSession(headers=headers)
        return self.session

    async def close(self):
        try:
            if self.session and not self.session.closed:
                await self.session.close()
                self.session = None
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

    async def _send_request(self, method: str, endpoint: str, params: dict = None, data: dict = None):
        url = f"{self.application_url}/{endpoint}"
        self._init_session()
        
        async with self.session.request(method, url, params=params, json=data) as response:
            if response.status == 204:
                return {"status": "deleted"}
                
            res_json = await response.json()
            if response.status not in [200, 201]:
                raise Exception(f"API Error ({response.status}): {res_json}")
            return res_json

    async def check_user(self, discord_id: str, email: str = None) -> tuple[bool, str]:
        try:
            profile = datamanager.find_one(query={"discord_id": str(discord_id)})

            if profile and profile.get("panel_id"):
                return True, str(profile.get("panel_id"))

            if email:
                await self.cooldown()
                
                params = {"filter[email]": email}
                response = await self._send_request("GET", "users", params=params)

                users_list = response.get("data", [])

                if users_list and len(users_list) > 0:
                    user_data = users_list[0].get("attributes", users_list[0])
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
            params = {"include": "servers"}
            raw_data = await self._send_request("GET", f"users/{panel_id}", params=params)

            data_root = raw_data.get("data", raw_data)
            attributes = data_root.get("attributes", data_root)

            relationships = attributes.get("relationships", {})
            servers_dict = relationships.get("servers", {})

            return servers_dict.get("data", [])

        except Exception as e:
            logging.error(f"Error get {panel_id} server failed: {e}")
            return []

    async def create_server(
        self,
        name: str,
        user_id: int,
        nest_id: int,
        egg_id: int,
        memory_limit: int,
        disk_limit: int,
        swap_limit: int = 0,
        location_ids: list = None,
        port_range: list = None,
        environment: dict = None,
        cpu_limit: int = 0,
        io_limit: int = 500,
        database_limit: int = 0,
        allocation_limit: int = 0,
        backup_limit: int = 0,
        docker_image: str = None,
        startup_cmd: str = None,
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

            if default_allocation is None and not location_ids:
                raise Exception('Must specify either default_allocation or location_ids')

            egg_endpoint = f"nests/{nest_id}/eggs/{egg_id}"
            egg_info_response = await self._send_request("GET", egg_endpoint, params={'include': 'variables'})
            
            egg_info = egg_info_response.get('attributes', egg_info_response)
            egg_vars = egg_info.get('relationships', {}).get('variables', {}).get('data', [])

            env_with_defaults = {}
            for var in egg_vars:
                var_attr = var.get('attributes', var)
                var_name = var_attr.get('env_variable')
                
                if environment and var_name in environment:
                    env_with_defaults[var_name] = environment[var_name]
                else:
                    env_with_defaults[var_name] = var_attr.get('default_value')

            if not docker_image:
                docker_image = egg_info.get('docker_image')
            if not startup_cmd:
                startup_cmd = egg_info.get('startup')

            payload = {
                'name': name,
                'user': user_id,
                'external_id': external_id,
                'nest': nest_id,
                'egg': egg_id,
                'docker_image': docker_image,
                'startup': startup_cmd,
                'oom_disabled': oom_disabled,
                'limits': {
                    'memory': memory_limit,
                    'swap': swap_limit,
                    'disk': disk_limit,
                    'io': io_limit,
                    'cpu': cpu_limit,
                },
                'feature_limits': {
                    'databases': database_limit,
                    'allocations': allocation_limit,
                    'backups': backup_limit
                },
                'environment': env_with_defaults,
                'start_on_completion': start_on_completion,
                'description': description or "",
            }

            if default_allocation is not None:
                payload['allocation'] = {
                    'default': default_allocation,
                    'additional': additional_allocations or []
                }
            elif location_ids:
                payload['deploy'] = {
                    'locations': location_ids,
                    'dedicated_ip': dedicated_ip,
                    'port_range': port_range or []
                }

            res_data = await self._send_request("POST", "servers", data=payload)
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
            raise Exception(f"Direct API create error: {str(e)}")

    async def delete_server(self, server_id: int, force: bool = True) -> dict:
        endpoint = f"servers/{server_id}/force" if force else f"servers/{server_id}"
        return await self._send_request("DELETE", endpoint)

    async def create_account(
        self,
        discord_id: str,
        email: str,
        name: str = None
    ) -> str | None:
        payload = {
            "username": name if name else discord_id,
            "email": email,
            "first_name": discord_id,
            "last_name": name if name else discord_id,
            "password": generate_random_password(15),
        }
        
        response = await self._send_request("POST", "users", data=payload)
        user_data = response.get("attributes", response)
        return str(user_data.get("id"))


pterclient = PterodactylClient()