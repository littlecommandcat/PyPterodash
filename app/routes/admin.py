import logging
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from ..core import AuthClient, datamanager, templates

router = APIRouter(prefix="/admin", tags=["Admin Page"])




@router.get("/", response_class=HTMLResponse)
async def admin_page(
    request: Request,
    admin: dict = Depends(AuthClient.is_user_admin)
):
    try:
        users = datamanager.find_all({})

        for user in users:
            if "_id" in user:
                user["_id"] = str(user["_id"])

            user.pop("password", None)

        return templates.TemplateResponse(
            "admin.html",
            {
                "request": request,
                "admin": admin,
                "users": users
            }
        )

    except Exception as e:
        logging.error(f"Admin page error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )