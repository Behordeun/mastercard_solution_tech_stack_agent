# Import libraries
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

settings = Settings()

description = f"""
{settings.API_STR} helps you do awesome stuff. 🚀
"""


# === Log directory setup ===
LOG_DIR = "src/mastercard_solution_tech_stack_agent/logs"
os.makedirs(LOG_DIR, exist_ok=True)  # Ensure the logs directory exists

# === Log file paths ===
LOG_FILES = {
    "info": os.path.join(LOG_DIR, "info.log"),
    "warning": os.path.join(LOG_DIR, "warning.log"),
    "error": os.path.join(LOG_DIR, "error.log"),
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
    description="API documentation for TechStack AI Server",
    openapi_url=f"{settings.API_STR}/openapi.json",
    docs_url=f"{settings.API_STR}/docs",  # SwaggerUI
    redoc_url=f"{settings.API_STR}/redoc",  # ReDoc
    version=settings.VERSION,
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
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
    return templates.TemplateResponse("homepage.html", {"request": request})


# === Global Exception Logging ===
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    system_logger.error(exc, exc_info=True)  # Pass the exception object
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    system_logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
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
        system_logger.error("Error reading log %s", log_type=e, exc_info=True)
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
