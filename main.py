import logging
from contextlib import asynccontextmanager
import aiohttp
import uvicorn
import json
from fastapi import FastAPI, Request, Depends, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from app.routes import auth, dash, shop
from app.core import limiter, templates, pterclient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# app = FastAPI()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # async with aiohttp.ClientSession() as session:
    #     app.state.session = session
    #     yield
    yield
    await pterclient.close()
        # logging.info("[]")

app = FastAPI(title="Discord Auth Dash with aiohttp", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.mount("/static", StaticFiles(directory="static"), name="static")

# @app.middleware("http")
# async def add_session_to_request(request: Request, call_next):
#     request.state.session = app.state.session
#     response = await call_next(request)
#     return response

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

app.include_router(auth.router)
app.include_router(dash.router)
app.include_router(shop.router)

@app.get("/", response_class=HTMLResponse)
@limiter.limit("5/second;20/minute")
async def index(request: Request):
    user_cookie_str = request.cookies.get("session_user")
    if user_cookie_str:
        try:
            json.loads(user_cookie_str)
            return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
        except Exception:
            pass

    return templates.TemplateResponse(
        name="index.html", 
        context={"request": request}
    )


if __name__ == "__main__":
    uvicorn.run("main:app", reload=True, port=8000)