from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
import json
import logging
from ..core import DiscordAuthService, pterclient, templates, limiter, datamanager, config, dchook

router = APIRouter(prefix="/dashboard", tags=["Authentication"], dependencies=[Depends(DiscordAuthService.get_current_user)])



@router.get("/", response_class=HTMLResponse)
@limiter.limit("1/2second")
async def show_dashboard_page(request: Request):
    user_cookie_str = request.cookies.get("session_user")
    try:
        user_data = json.loads(user_cookie_str)
    except Exception:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    discord_id = str(user_data.get("id"))
    user_email = user_data.get("email")
    user_name = user_data.get("username")

    user_profile = datamanager.find_one(query={"discord_id": discord_id})
    if not user_profile:
        user_profile = {
            "discord_id": discord_id,
            "username": user_name,
            "email": user_email,
            "panel_id": None,
            "coin": 0,
            "max_memory": 0,
            "max_cpu": 0,
            "max_disk": 0,
            "servers": []
        }

    panel_id = user_profile.get("panel_id")
    synced_servers = user_profile.get("servers", [])

    if user_email:
        try:
            if not panel_id or panel_id == "0":
                existed, fetched_panel_id = await pterclient.check_user(discord_id=discord_id, email=user_email)
                if existed and fetched_panel_id != "0":
                    panel_id = str(fetched_panel_id)
                    user_profile["panel_id"] = panel_id

            if panel_id and panel_id != "0":
                raw_servers = await pterclient.get_user_servers(panel_id=panel_id) or []
                
                fresh_servers = []
                for s in raw_servers:
                    attr = s.get("attributes", s)
                    limits = attr.get("limits", {})
                    
                    fresh_servers.append({
                        "server_id": attr.get("id"),
                        "identifier": attr.get("identifier"),
                        "server_name": attr.get("name"),
                        "nest_id": attr.get("nest"),
                        "egg_id": attr.get("egg"),
                        "memory": int(limits.get("memory") or 0),
                        "cpu": int(limits.get("cpu") or 0),
                        "disk": int(limits.get("disk") or 0)
                    })
                
                synced_servers = fresh_servers
                user_profile["servers"] = synced_servers

            datamanager.update_one(
                query={"discord_id": discord_id},
                update_data={"$set": {
                    "username": user_name,
                    "email": user_email,
                    "panel_id": panel_id,
                    "servers": synced_servers
                }}
            )

        except Exception as ptero_err:
            logging.error(f"Async failed: {ptero_err}")
    return templates.TemplateResponse(
        name="dashboard.html", 
        context={
            "request": request,
            "user": user_profile,                
            "servers": synced_servers
        }
    )
