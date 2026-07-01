import logging
import asyncio
import datetime
from discord import Embed
from ..core import datamanager, AuthClient, limiter, pterclient, generate_random_password, dchook
from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/admin", tags=["Admin"], dependencies=[Depends(AuthClient.is_user_admin)])


@router.post("/get_users")
@limiter.limit("2/second;15/minute")
async def get_users(request: Request):
    try:
        users = datamanager.find_all({})
        for user in users:
            if "_id" in user:
                user["_id"] = str(user["_id"])

        return JSONResponse(
            status_code=200,
            content={
                "status": True,
                "data": users
            }
        )

    except Exception as e:
        logging.error(f"Admin get users error: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": False,
                "message": str(e)
            }
        )


@router.patch("/user/{discord_id}")
@limiter.limit("5/second;30/minute")
async def update_user(request: Request, discord_id: str, admin_data: dict = Depends(AuthClient.is_user_admin)):
    try:
        data = await request.json()

        allowed_fields = {
            "max_memory",
            "max_cpu",
            "max_disk",
            "coins"
        }

        update_data = {}
        
        for field, value in data.items():
            if field not in allowed_fields:
                continue

            try:
                value = int(value)
            except:
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": False,
                        "message": f"Invalid value for {field}"
                    }
                )

            if field != "coins" and value <= 0:
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": False,
                        "message": f"{field} must be greater than zero"
                    }
                )

            if field == "coins" and value < 0:
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": False,
                        "message": "Coins cannot be negative"
                    }
                )

            update_data[field] = value


        if not update_data:
            return JSONResponse(
                status_code=400,
                content={
                    "status": False,
                    "message": "No valid update fields"
                }
            )


        user = datamanager.find_one({"discord_id": str(discord_id)})

        if not user:
            return JSONResponse(
                status_code=404,
                content={
                    "status": False,
                    "message": "User not found"
                }
            )


        datamanager.update_one({"discord_id": str(discord_id)}, {"$set": update_data})
        # print(user)
        discord_name = user.get("username")
        user_email = user.get("email")
        embed = Embed(
            title=f"Update User(`{discord_id}`)",
            timestamp=datetime.datetime.now(),
            description=f"""User: <@{discord_id}>({discord_name if discord_name else "Failed to get"})
Email: `{user_email}`
""",
        )
        embed.add_field(
            name="Data",
            value=f"""Admin: <@{admin_data.get('discord_id')}>({admin_data.get('username') if admin_data.get('username') else 'Failed to get'})
```{update_data}```
""",
            inline=False
        )
        await dchook.post(embeds=[embed], username="[Admin-Data]")
        return JSONResponse(
            status_code=200,
            content={
                "status": True,
                "message": "User updated successfully"
            }
        )

    except Exception as e:
        logging.error(f"Admin update user error: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": False,
                "message": str(e)
            }
        )


@router.patch("/user/{discord_id}/password")
@limiter.limit("5/minute")
async def update_user_password(request: Request, discord_id: str, admin_data: dict = Depends(AuthClient.is_user_admin)):
    try:
        data = await request.json()
        password = data.get("password")
        
        if not password:
            return JSONResponse(
                status_code=400,
                content={
                    "status": False,
                    "message": "Missing password"
                }
            )

        if len(password) < 8:
            return JSONResponse(
                status_code=400,
                content={
                    "status": False,
                    "message": "Password must be at least 8 characters"
                }
            )


        user = datamanager.find_one({"discord_id": str(discord_id)})

        if not user:
            return JSONResponse(
                status_code=404,
                content={
                    "status": False,
                    "message": "User not found"
                }
            )


        panel_id = user.get("panel_id")

        if not panel_id:
            return JSONResponse(
                status_code=400,
                content={
                    "status": False,
                    "message": "User has no Pterodactyl account"
                }
            )


        await pterclient.update_password(user_id=int(panel_id), password=password)
        discord_name = user.get("username")
        user_email = user.get("email")
        update_data = {
            "password": "＊" * len(str(password))
        }
        embed = Embed(
            title=f"Update Password(`{discord_id}`)",
            timestamp=datetime.datetime.now(),
            description=f"""User: <@{discord_id}>({discord_name if discord_name else "Failed to get"})
Email: `{user_email}`
""",
        )
        embed.add_field(
            name="Data",
            value=f"""Admin: <@{admin_data.get('discord_id')}>({admin_data.get('username') if admin_data.get('username') else 'Failed to get'})
```{update_data}```
""",
            inline=False
        )
        await dchook.post(embeds=[embed], username="[Admin-Password]")

        return JSONResponse(
            status_code=200,
            content={
                "status": True,
                "message": "Password updated successfully"
            }
        )


    except Exception as e:
        logging.error(f"Admin password update error: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": False,
                "message": str(e)
            }
        )
    
@router.delete("/user/{discord_id}")
@limiter.limit("3/minute")
async def delete_user(request: Request, discord_id: str, admin_data: dict = Depends(AuthClient.is_user_admin)):
    try:

        user = datamanager.find_one({
            "discord_id": str(discord_id)
        })
        
        if not user:
            return JSONResponse(
                status_code=404,
                content={
                    "status": False,
                    "message": "User not found"
                }
            )
        if user.get("admin", False):
            return JSONResponse(
                status_code=403,
                content={
                    "status": False,
                    "message": "Unable to delete admin account"
                }
            )
        
        panel_id = user.get("panel_id")
        servers = user.get("servers", [])
        server_status = [0, 0, 0]
        server_status[0] = len(servers)
        for server in servers:
            try:
                await pterclient.delete_server(server_id=str(server.get("server_id")), force=True)
                server_status[1] += 1
            except:
                server_status[2] += 1

            await asyncio.sleep(1)
        # password = generate_random_password(length=35)
        # await pterclient.update_password(user_id=int(panel_id), password=password)
        
        discord_name = user.get("username")
        user_email = user.get("email")
        update_data = {
            "servers": server_status[0],
            "deleted": server_status[1],
            "failed": server_status[2],
            "lost": server_status[0] - server_status[1] - server_status[2]
        }
        embed = Embed(
            title=f"Delete User(`{discord_id}`)",
            timestamp=datetime.datetime.now(),
            description=f"""User: <@{discord_id}>({discord_name if discord_name else "Failed to get"})
Email: `{user_email}`
""",
        )
        embed.add_field(
            name="Data",
            value=f"""Admin: <@{admin_data.get('discord_id')}>({admin_data.get('username') if admin_data.get('username') else 'Failed to get'})
```{update_data}```
""",
            inline=False
        )
        await dchook.post(embeds=[embed], username="[Admin-DeleteUser]")

        datamanager.delete_one({
            "discord_id": str(discord_id)
        })
        await pterclient.delete_user(user_id=int(panel_id))

        return JSONResponse(
            status_code=200,
            content={
                "status": True,
                "message": "User data deleted successfully"
            }
        )


    except Exception as e:

        logging.error(
            f"Admin delete user error: {e}"
        )

        return JSONResponse(
            status_code=500,
            content={
                "status": False,
                "message": str(e)
            }
        )