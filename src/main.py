# import libraries
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware

from src.api.route import chat_router
from src.config import settings
from src.config.appconfig import env_config
from src.config.settings import Settings
from src.error_trace.errorlogger import system_logger
from src.utilities.Printer import printer

# === Log directory setup ===
LOG_DIR = "src/logs"
os.makedirs(LOG_DIR, exist_ok=True)

# === Log file paths ===
LOG_FILES = {
    "info": os.path.join(LOG_DIR, "info.log"),
    "warning": os.path.join(LOG_DIR, "warning.log"),
    "error": os.path.join(LOG_DIR, "error.log"),
}

# === Logging format ===
log_format = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")

# === Set up handlers per log level ===
info_handler = logging.FileHandler(LOG_FILES["info"])
info_handler.setLevel(logging.INFO)
info_handler.setFormatter(log_format)

warning_handler = logging.FileHandler(LOG_FILES["warning"])
warning_handler.setLevel(logging.WARNING)
warning_handler.setFormatter(log_format)

error_handler = logging.FileHandler(LOG_FILES["error"])
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(log_format)

# === Attach handlers to root logger ===
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.handlers = []  # Remove default handlers

root_logger.addHandler(info_handler)
root_logger.addHandler(warning_handler)
root_logger.addHandler(error_handler)
root_logger.addHandler(logging.StreamHandler())  # Also log to console

# === Module-level logger ===
logger = logging.getLogger(__name__)
settings = Settings()

description = f"""
{settings.API_STR} helps you do awesome stuff. 🚀
"""


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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Enforce HTTPS in production ===
if env_config.env != "development":
    app.add_middleware(HTTPSRedirectMiddleware)

# === Mount static assets ===
app.mount("/static", StaticFiles(directory="src/static"), name="static")
templates = Jinja2Templates(directory="src/templates")


# === Serve frontend ===
@app.get("/", response_class=HTMLResponse)
async def serve_ui(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# === Global Exception Logging ===
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled Exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logger.warning(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
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
            raise HTTPException(status_code=404, detail="Log file not found.")
        with open(log_file, "r", encoding="utf-8") as f:
            return f.read() or "Log file is empty."
    except Exception as e:
        logger.error(f"Error reading log '{log_type}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error reading log file.") from e


# === Main chat router ===
app.include_router(chat_router, prefix=settings.API_STR)

# === Start server ===
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
