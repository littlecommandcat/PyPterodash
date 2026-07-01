import json
import datetime
from discord import Embed
from fastapi import APIRouter, Request, status, Depends
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from ..core import datamanager, limiter, templates, dchook, config, DiscordAuthService, AuthClient

router = APIRouter(prefix="/api/trade", tags=["Authentication"], dependencies=[Depends(DiscordAuthService.get_current_user)])


@router.post("/buy")
@limiter.limit("15/minute")
async def buy_resources(request: Request):
    try:
        req_data = await request.json()
        item_type = req_data.get("item_type")
        raw_amount = req_data.get("amount", 1)
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": "Request JSON error", "detail": str(e)}
        )

    if not config.get_config(f"price.{item_type}", None):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": "Unknown item type. Please select ram, cpu, or disk."}
        )
        
    try:
        amount = int(raw_amount)
    except (ValueError, TypeError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": "Invalid quantity format. It must be an integer."}
        )

    if amount <= 0:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": "Purchase quantity must be greater than 0."}
        )
    
    try:
        user_data = AuthClient.get_current_user(request)
        discord_id = str(user_data.get("id"))
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"status": "error", "message": "Session corrupted. Please log in again."}
        )

    user_profile = datamanager.find_one(query={"discord_id": discord_id})
    if not user_profile:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"status": "error", "message": "User profile not found."}
        )

    total_cost = config.get_config(f"price.{item_type}") * amount
    current_coins = user_profile.get("coin", 0)

    if current_coins < total_cost:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "status": "error", 
                "message": f"Insufficient coins! This purchase requires {total_cost} coins, but you only have {current_coins}."
            }
        )

    update_fields = {}
    
    if item_type == "ram":
        update_fields = {"max_memory": amount, "coin": -total_cost}
        msg = f"Successfully purchased {amount} MB of RAM!"
        
    elif item_type == "cpu":
        update_fields = {"max_cpu": amount, "coin": -total_cost}
        msg = f"Successfully purchased {amount}% CPU!"
        
    elif item_type == "disk":
        update_fields = {"max_disk": amount, "coin": -total_cost}
        msg = f"Successfully purchased {amount} MB of disk space!"

    if not update_fields:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": "An error occurred while processing your purchase."}
        )

    datamanager.update_one(
        query={"discord_id": discord_id},
        update_data={"$inc": update_fields}
    )
    discord_name = user_profile.get("username")
    user_email = user_profile.get("email")
    embed = Embed(
        title=f"Buy Item(`{item_type}`)",
        timestamp=datetime.datetime.now(),
        description=f"""User: <@{discord_id}>({discord_name if discord_name else "Failed to get"})
Email: `{user_email}`
Amount: `{amount}`
Coins: `{current_coins}`(Cost `{total_cost}`)
""",
    )
    embed.add_field(name="Data", value=f"```{update_fields}```", inline=False)
    await dchook.post(embeds=[embed], username="[Shop]")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "success",
            "message": msg,
            "detail": f"{total_cost} coins deducted. Remaining balance: {current_coins - total_cost} coins."
        }
    )