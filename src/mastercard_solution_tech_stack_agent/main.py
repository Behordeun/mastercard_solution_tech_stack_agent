# import libraries
import os
import warnings
import traceback
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.sessions import SessionMiddleware

from src.mastercard_solution_tech_stack_agent.api import (
    admin,
    auth,
    logs_router,
    route,
    super_admin,
    users,
)
from src.mastercard_solution_tech_stack_agent.config import settings
from src.mastercard_solution_tech_stack_agent.config.appconfig import env_config
from src.mastercard_solution_tech_stack_agent.config.settings import Settings
from src.mastercard_solution_tech_stack_agent.error_trace.errorlogger import (
    system_logger,
)
from src.mastercard_solution_tech_stack_agent.utilities.Printer import printer

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)


settings = Settings()

description = f"""
{settings.API_STR} helps you do awesome stuff. 🚀
"""


LOG_FILES = {
    "info": "src/mastercard_solution_tech_stack_agent/logs/info.log",
    "warning": "src/mastercard_solution_tech_stack_agent/logs/warning.log",
    "error": "src/mastercard_solution_tech_stack_agent/logs/error.log",
}


# === Lifespan context ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    system_logger.info("🚀 TSA145 server starting up.")
    printer(" ⚡️🚀 AI Server::Started", "sky_blue")
    yield
    system_logger.info("🛑 TSA145 server shutting down.")
    printer(" ⚡️🚀 AI Server::SHUTDOWN", "red")


# === FastAPI instance ===
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=description,
    openapi_url=f"{settings.API_STR}/openapi.json",
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
    lifespan=lifespan,
)

# === CORS configuration ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Session middleware ===
app.add_middleware(
    SessionMiddleware,
    secret_key=env_config.secret_key,
    session_cookie="session_cookie",
    same_site="lax",  # Important for OAuth
    https_only=True,  # Ensures session only works over HTTPS (e.g., ngrok)
    max_age=3600,  # Optional, session duration in seconds
)

# === Middleware for trusted hosts ===
# app.add_middleware(
#     TrustedHostMiddleware,
#     allowed_hosts=[
#         "localhost",
#         "127.0.0.1",
#         "*.ngrok-free.app",   # ✅ Matches faithful-foal-genuine.ngrok-free.app
#         "faithful-foal-genuine.ngrok-free.app"  # ✅ Explicit if needed
#     ]
# )

# === Enforce HTTPS in production ===
if env_config.env != "development":
    app.add_middleware(HTTPSRedirectMiddleware)

# === Mount static assets ===
app.mount(
    "/static",
    StaticFiles(directory="src/mastercard_solution_tech_stack_agent/static"),
    name="static",
)
templates = Jinja2Templates(
    directory="src/mastercard_solution_tech_stack_agent/templates"
)


# === Serve frontend ===
@app.get("/", response_class=HTMLResponse)
async def serve_ui(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# === Serve Signup ===
@app.get("/signup", response_class=HTMLResponse)
async def serve_signup(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})
# === Serve Chat UI ===
@app.get("/chat", response_class=HTMLResponse)
async def serve_chat(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})

# === Serve Summarization ===
@app.get("/summary", response_class=HTMLResponse)
async def serve_summary(request: Request):
    return templates.TemplateResponse("summarization.html", {"request": request})


# === TechStack Recommendation ===
@app.get("/techstack", response_class=HTMLResponse)
async def serve_techstack(request: Request):
    return templates.TemplateResponse("techstack.html", {"request": request})


# === Global Exception Logging ===
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    system_logger.error(exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    # Log full traceback for internal diagnostics
    error_trace = traceback.format_exc()
    system_logger.warning(
        f"HTTP Exception: {exc.status_code} - {exc.detail}\n"
        f"Path: {request.url.path}\n"
        f"Method: {request.method}\n"
        f"Traceback:\n{error_trace}"
    )
 
    # Return detailed error response (customize based on environment)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": exc.__class__.__name__,
                "message": str(exc.detail),
                "status_code": exc.status_code,
                "path": request.url.path,
                "method": request.method,
            }
        },
    )
 


# === API Info Endpoint ===
@app.get(f"{settings.API_STR}", status_code=status.HTTP_200_OK)
def APIHome():
    return {
        "ApplicationName": app.title,
        "ApplicationOwner": "TechStack AI",
        "ApplicationVersion": "1.0.0",
        "ApplicationEngineer": "Muhammad Abiodun SULAIMAN",
        "ApplicationStatus": "running...",
    }


# === Health check ===
@app.get("/health", status_code=status.HTTP_200_OK)
def APIHealth():
    return "healthy"


# === Log Viewer API ===
@app.get("/view-logs/{log_type}/", response_class=PlainTextResponse)
async def view_logs(log_type: str):
    log_file = LOG_FILES.get(log_type.lower())

    if not log_file:
        raise HTTPException(
            status_code=400,
            detail="Invalid log type. Choose from: info, warning, error.",
        )

    try:
        if not os.path.exists(log_file):
            raise HTTPException(status_code=404, detail=f"Log file not found.")
        with open(log_file, "r", encoding="utf-8") as f:
            return f.read() or "Log file is empty."
    except Exception as e:
        system_logger.error(f"Error reading log '{log_type}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error reading log file.")


# === Include Routers ===
app.include_router(admin.router, prefix=f"{settings.API_STR}/admin", tags=["Admin"])
app.include_router(auth.router, prefix=f"{settings.API_STR}/auth", tags=["Auth"])
app.include_router(logs_router.router, prefix=f"{settings.API_STR}/logs", tags=["Logs"])
app.include_router(route.router, prefix=f"{settings.API_STR}/chat", tags=["Chat"])
app.include_router(
    super_admin.router, prefix=f"{settings.API_STR}/super-admin", tags=["Super Admin"]
)
app.include_router(users.router, prefix=f"{settings.API_STR}/users", tags=["Users"])


# === Start server ===
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
