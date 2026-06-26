import json
from fastapi import APIRouter, Request, status, Depends
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from ..core import datamanager, limiter, templates, config, DiscordAuthService, AuthClient

router = APIRouter(prefix="/shop", tags=["Shop System"], dependencies=[Depends(DiscordAuthService.get_current_user)])



@router.get("/", response_class=HTMLResponse)
@limiter.limit("3/second")
async def shop(request: Request):
    try:
        user_data = AuthClient.get_current_user(request)
        discord_id = str(user_data.get("id"))
    except Exception:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    user_profile = datamanager.find_one(query={"discord_id": discord_id})
    if not user_profile:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        name="shop.html",
        request=request,
        context={
            "user": user_profile,
            "ram": config.get_config("price.ram"),
            "cpu": config.get_config("price.cpu"),
            "disk": config.get_config("price.disk")
        }
    )