import logging
import json
import datetime
from discord import Embed
from ..core import DiscordAuthService, config, limiter, datamanager, pterclient, dchook, AuthClient
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi import APIRouter, HTTPException, status, Request

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

discord_service = DiscordAuthService(
    client_id=config.get_config("discord.client_id"),
    client_secret=config.get_config("client_secret"),
    redirect_uri=config.get_config("discord.callback")
)

@router.get("/callback")
@limiter.limit("3/second;20/minute")
async def callback(request: Request, code: str = None):
    if not code:
        raise HTTPException(status_code=400, detail="Missing code")

    try:
        user_data = await discord_service.get_user_data(code)
        discord_id = str(user_data.get("id"))
        user_email = user_data.get("email")
        user_name = user_data.get("username")

        if not user_email:
            raise HTTPException(status_code=400, detail="Failed to get email from Discord")

        existing_user = datamanager.find_one(query={"discord_id": discord_id})
        
        panel_id = None
        synced_servers = []

        try:
            existed, fetched_panel_id = await pterclient.check_user(discord_id=discord_id, email=user_email)
            
            if existed and fetched_panel_id != "0":
                panel_id = str(fetched_panel_id)
                raw_servers = await pterclient.get_user_servers(panel_id=panel_id) or []
                
                for s in raw_servers:
                    attr = s.get("attributes", s)
                    limits = attr.get("limits", {})
                    
                    synced_servers.append({
                        "server_id": attr.get("id"),
                        "identifier": attr.get("identifier"),
                        "server_name": attr.get("name"),
                        "nest_id": attr.get("nest"),
                        "egg_id": attr.get("egg"),
                        "memory": int(limits.get("memory") or 0),
                        "cpu": int(limits.get("cpu") or 0),
                        "disk": int(limits.get("disk") or 0)
                    })
        except Exception as ptero_err:
            logging.error(f"Rate limited: {ptero_err}")
            if existing_user:
                panel_id = existing_user.get("panel_id")
                synced_servers = existing_user.get("servers", [])

        if not existing_user:
            initial_profile = {
                "discord_id": discord_id,
                "username": user_name,
                "email": user_email,
                "admin": False,
                "panel_id": panel_id,
                "coin": 50,
                "max_memory": 2048 if panel_id else 0,
                "max_cpu": 200 if panel_id else 0,
                "max_disk": 10240 if panel_id else 0,
                "servers": synced_servers
            }
            datamanager.insert_one(initial_profile)
        else:
            update_data = {
                "username": user_name,
                "email": user_email,
                "servers": synced_servers
            }
            if panel_id:
                update_data["panel_id"] = panel_id
                
            datamanager.update_one(
                query={"discord_id": discord_id},
                update_data={"$set": update_data}
            )

        embed = Embed(
            title=f"Login",
            timestamp=datetime.datetime.now(),
            description=f"""User: <@{discord_id}>({user_name})
Email: `{user_email}`
""",
        )
        await dchook.post(embeds=[embed], username="[Auth]")
        encrypted = AuthClient.encrypt_session(user_data)
        redirect_response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
        redirect_response.set_cookie(
            key="session_user", 
            value=encrypted, 
            httponly=True,
            samesite="lax",
            max_age=10800
        )
        return redirect_response

    except Exception as e:
        logging.error(f"Callback error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
@router.post("/logout")
@limiter.limit("2/second;15/minute")
async def logout(request: Request):
    response = JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "success", "message": "logout successfully"}
    )
    response.delete_cookie(key="session_user")
    return response