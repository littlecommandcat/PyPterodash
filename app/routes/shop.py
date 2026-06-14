import json
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from ..core import datamanager, limiter, templates, get_webhook

router = APIRouter(prefix="/shop", tags=["Shop System"])


PRICES = {
    "ram": 10,
    "cpu": 15,
    "disk": 5
}

@router.get("/", response_class=HTMLResponse)
@limiter.limit("3/second")
async def shop(request: Request):
    user_cookie_str = request.cookies.get("session_user")
    if not user_cookie_str:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)
        
    try:
        user_data = json.loads(user_cookie_str)
        discord_id = str(user_data.get("id"))
    except Exception:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    user_profile = datamanager.find_one(query={"discord_id": discord_id})
    if not user_profile:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        name="shop.html", 
        context={
            "request": request,
            "user": user_profile
        }
    )


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

    if item_type not in PRICES:
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

    user_cookie_str = request.cookies.get("session_user")
    if not user_cookie_str:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"status": "error", "message": "Unauthorized. Please log in to access the shop."}
        )
        
    try:
        user_data = json.loads(user_cookie_str)
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

    total_cost = PRICES[item_type] * amount
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
    
    webhook = get_webhook()
    log_content = f"{discord_id}\n```{update_fields}```\n{msg}"
    if webhook.is_async:
        await webhook.send(log_content, username="[Shop]")
    else:
        webhook.send(log_content, username="[Shop]")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "success",
            "message": msg,
            "detail": f"{total_cost} coins deducted. Remaining balance: {current_coins - total_cost} coins."
        }
    )