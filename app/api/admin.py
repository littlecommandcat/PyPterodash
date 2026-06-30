import logging
from ..core import datamanager, AuthClient, limiter, pterclient
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
async def update_user(request: Request, discord_id: str):
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
async def update_user_password(request: Request, discord_id: str):
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