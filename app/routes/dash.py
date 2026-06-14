from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
import json
import logging
from ..core import DiscordAuthService, pterclient, templates, limiter, datamanager, config, get_webhook

router = APIRouter(prefix="/dashboard", tags=["Authentication"], dependencies=[Depends(DiscordAuthService.get_current_user)])



@router.get("/", response_class=HTMLResponse)
@limiter.limit("5/second;20/minute")
async def show_dashboard_page(request: Request):
    user_cookie_str = request.cookies.get("session_user")
    if not user_cookie_str:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    try:
        user_data = json.loads(user_cookie_str)
    except Exception:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

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

@router.get("/servers")
@limiter.limit("10/minute")
async def get_user_servers(request: Request, user: dict = Depends(DiscordAuthService.get_current_user)):
    discord_id = user.get("id") 
    
    if not discord_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "status": "error",
                "message": "Unidentified user identity",
                "detail": "Failed to retrieve user profile"
            }
        )

    try:
        user_servers = datamanager.find_all(query={"discord_id": str(discord_id)})
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "message": "Get user's servers successfully",
                "count": len(user_servers),
                "data": user_servers
            }
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "Failed to get user's servers",
                "detail": str(e)
            }
        )
    
@router.post("/server/create")
@limiter.limit("10/minute")
async def create_server_route(request: Request, user: dict = Depends(DiscordAuthService.get_current_user)):
    try:
        server_data = await request.json()
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "status": "error",
                "message": "Request json error",
                "detail": str(e)
            }
        )

    discord_id = user.get("id")
    discord_name = user.get("name")
    if not discord_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": "Missing user_id"}
        )

    user_profile = datamanager.find_one(query={"discord_id": str(discord_id)})
    if not user_profile:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"status": "error", "message": "User profile not found in database"}
        )

    user_email = user_profile.get("email")
    user_name = user_profile.get("username")
    if not user_email:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": "User profile is missing an email address"}
        )

    limits = server_data.get("limits", {})
    try:
        req_memory = int(limits.get("memory", server_data.get("server_ram", 1024)))
        req_cpu = int(limits.get("cpu", server_data.get("server_cpu", 100)))
        req_disk = int(limits.get("disk", server_data.get("server_disk", 5120)))
        egg_id = int(server_data.get("egg_id", server_data.get("server_egg", 1)))
    except (ValueError, TypeError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": "Invalid resource numerical format"}
        )

    if req_memory <= 0 or req_cpu <= 0 or req_disk <= 0:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": "Resource requests must be greater than zero"}
        )

    current_servers = user_profile.get("servers", [])
    used_memory = sum(s.get("memory", 0) for s in current_servers)
    used_cpu = sum(s.get("cpu", 0) for s in current_servers)
    used_disk = sum(s.get("disk", 0) for s in current_servers)
    if used_memory + req_memory > user_profile.get("max_memory", 0):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, 
            content={
                "status": "error", 
                "message": f"Memory limit exceeded. Available: {user_profile.get('max_memory', 0) - used_memory} MB"
            }
        )
        
    if used_cpu + req_cpu > user_profile.get("max_cpu", 0):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, 
            content={
                "status": "error", 
                "message": f"CPU limit exceeded. Available: {user_profile.get('max_cpu', 0) - used_cpu}%"
            }
        )
        
    if used_disk + req_disk > user_profile.get("max_disk", 0):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, 
            content={
                "status": "error", 
                "message": f"Disk limit exceeded. Available: {user_profile.get('max_disk', 0) - used_disk} MB"
            }
        )

    try:
        existed, panel_id = await pterclient.check_user(str(discord_id), email=user_email)
        if not existed:
            existed, panel_id = await pterclient.check_user(str(discord_id))

        if not existed or panel_id == "0":
            panel_id = await pterclient.create_account(
                discord_id=str(discord_id),
                email=user_email,
                name=user_name
            )
            datamanager.update_one(
                query={"discord_id": str(discord_id)},
                update_data={"$set": {"panel_id": str(panel_id)}}
            )

        server_name_input = server_data.get("name", server_data.get("server_name", f"Server_{discord_id}"))

        result = await pterclient.create_server(
            name=server_name_input,
            user_id=int(panel_id),
            nest_id=int(config.get_config("nest_id")),
            egg_id=egg_id,
            memory_limit=req_memory,
            disk_limit=req_disk,
            cpu_limit=req_cpu,
            swap_limit=int(config.get_config("swap", 0)),
            io_limit=int(config.get_config("io", 500)),
            docker_image=config.get_config("docker_image"),
            startup_cmd=config.get_config("startup_command"),
            environment=config.get_config("environment"),
            location_ids=json.loads(config.get_config("location_ids", "[]")),
            port_range=json.loads(config.get_config("port_range", "[]"))
        )

        server_id = result.get("id")
        identifier = result.get("identifier")

        if server_id and identifier:
            new_server_entry = {
                "server_id": server_id,
                "identifier": identifier,
                "server_name": server_name_input, 
                "nest_id": int(config.get_config("nest_id", 1)),
                "egg_id": egg_id,
                "memory": req_memory,
                "cpu": req_cpu,
                "disk": req_disk
            }

            datamanager.update_one(
                query={"discord_id": str(discord_id)},
                update_data={"$push": {"servers": new_server_entry}}
            )
            
            webhook = get_webhook()
            log_msg = f"{discord_id}\nCreate server(`{server_id}`)\n{pterclient.url}/server/{identifier}"
            if webhook.is_async:
                await webhook.send(log_msg, username="[Dash]")
            else:
                webhook.send(log_msg, username="[Dash]")
                
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": "success",
                    "message": "Create server successfully",
                    "data": {
                        "server_id": server_id,
                        "identifier": identifier,
                        "url": f"{pterclient.url}/server/{identifier}"
                    }
                }
            )

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": "Failed to retrieve server metadata from panel"}
        )

    except Exception as e:
        logging.error(f"Create error: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "Panel rejected request or internal automation failed",
                "detail": str(e)
            }
        )


@router.post("/server/delete")
@limiter.limit("10/minute")
async def delete_server_route(request: Request, user: dict = Depends(DiscordAuthService.get_current_user)):
    try:
        response = await request.json()
        server_id = response.get("server_id")
        force = response.get("force", False)
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "status": "error",
                "message": "Request json error",
                "detail": str(e)
            }
        )

    if not server_id:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "status": "error",
                "message": "Invalid id",
                "detail": "Needs a server id"
            }
        )
    discord_id = user.get("id")
    discord_name = user.get("name")
    try:
        await pterclient.delete_server(server_id=str(server_id), force=force)

        datamanager.update_one(
            query={"servers.server_id": int(server_id)},
            update_data={
                "$pull": {
                    "servers": {"server_id": int(server_id)}
                }
            }
        )

        webhook = get_webhook()
        if webhook.is_async:
            await webhook.send(f"{discord_id}\nDelete server(`{server_id}`)", username="[Dash]")
        else:
            webhook.send(f"{discord_id}\nDelete server(`{server_id}`)", username="[Dash]")
        return {
            "status": "success",
            "message": f"{discord_id}\nDeleted server (id:{server_id}) successfully, records cleared."
        }
    except Exception as e:
        # logging.error(str(e))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "Failed to delete server",
                "detail": str(e)
            }
        )