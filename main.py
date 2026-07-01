import logging
import uvicorn
import json
import aiohttp
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, status, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.routes import dashboard, shop, admin
from app.core import limiter, templates, pterclient, DiscordAuthService, config, dchook, AuthClient
from app.api import auth, dash, trade, admin as admin_api


logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with aiohttp.ClientSession() as session:
        app.state.session = session
        yield
    await pterclient.close()
    await dchook.close()

app = FastAPI(
    title="PyPterodash Discord Login",
    lifespan=lifespan,
    docs_url=None if not config.get_config("app.docs", True) else "/docs",
    redoc_url=None if not config.get_config("app.docs", True) else "/redoc"
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.middleware("http")
async def add_session_to_request(request: Request, call_next):
    request.state.session = app.state.session
    response = await call_next(request)
    return response

limiter = Limiter(key_func=get_remote_address)
@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "status": "error",
            "message": f"Request too fast, please wait.",
            "detail": exc.detail
        }
    )

@app.exception_handler(401)
async def custom_401_handler(request: Request, exc: HTTPException):
    accept_header = request.headers.get("accept", "")
    
    if "text/html" in accept_header:
        return templates.TemplateResponse(
            name="401.html",
            request=request,
            context={"detail": exc.detail},
            status_code=status.HTTP_401_UNAUTHORIZED
        )
    
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"status": "error", "detail": exc.detail}
    )

app.include_router(dashboard.router)
app.include_router(shop.router)
app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(dash.router)
app.include_router(trade.router)
app.include_router(admin_api.router)

@app.get("/", response_class=HTMLResponse)
@limiter.limit("5/second;20/minute")
async def index(request: Request):
    try:
        user_cookie = AuthClient.get_current_user(request)
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    except Exception:
        pass

    return templates.TemplateResponse(
        name="index.html", 
        request=request
    )

discord_service = DiscordAuthService(
    client_id=config.get_config("discord.client_id"),
    client_secret=config.get_config("client_secret"),
    redirect_uri=config.get_config("discord.callback")
)

@app.get("/login")
@limiter.limit("2/second;10/minute")
async def login(request: Request):
    login_url = discord_service.get_login_url()
    return RedirectResponse(url=login_url)



if __name__ == "__main__":
    uvicorn.run("main:app", reload=config.get_config("app.debug"), host=config.get_config("app.host", "0.0.0.0"), port=config.get_config("app.port"))