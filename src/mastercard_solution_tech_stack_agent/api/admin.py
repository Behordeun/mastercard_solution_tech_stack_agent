import logging
import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.mastercard_solution_tech_stack_agent.api.auth import (
    create_access_token,
    get_current_admin_or_super_admin,
    get_user_info,
    hash_password,
    verify_password,
)
from src.mastercard_solution_tech_stack_agent.api.schemas import (
    Login,
    TokenResponse,
    UpdateAdminCredentials,
)
from src.mastercard_solution_tech_stack_agent.config.appconfig import env_config
from src.mastercard_solution_tech_stack_agent.database.pd_db import get_db
from src.mastercard_solution_tech_stack_agent.database.schemas import User

# === Log directory setup ===
LOG_DIR = "src/mastercard_solution_tech_stack_agent/logs"
os.makedirs(LOG_DIR, exist_ok=True)  # Ensure the logs directory exists

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


router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    responses={
        200: {"description": "Success - Request was successful."},
        201: {"description": "Created - Resource was successfully created."},
        400: {
            "description": "Bad Request - The request could not be understood or was missing required parameters."
        },
        401: {
            "description": "Unauthorized - Authentication is required and has failed or not yet been provided."
        },
        403: {
            "description": "Forbidden - The request was valid, but you do not have the necessary permissions."
        },
        404: {"description": "Not Found - The requested resource could not be found."},
        409: {
            "description": "Conflict - The request could not be completed due to a conflict with the current state of the resource."
        },
        422: {
            "description": "Unprocessable Entity - The request was well-formed but could not be followed due to validation errors."
        },
        500: {
            "description": "Internal Server Error - An unexpected server error occurred."
        },
    },
)


# Helper Functions
def normalize_input(value: str) -> str:
    """
    Normalize input by converting to lowercase and stripping whitespace.

    Args:
        value (str): Input string to normalize.

    Returns:
        str: Normalized string.
    """
    return value.strip().lower() if value else value


# Admin Login Route
@router.post("/login", response_model=TokenResponse, summary="Admin Login")
async def admin_login(form_data: Login, db: Session = Depends(get_db)):
    """
    Authenticate the admin and generate an access token.

    ### Request Body:
    - `form_data` (Login): The login credentials (email and password).

    ### Response:
    - A JWT access token for the authenticated admin.

    ### Raises:
    - `401 Unauthorized`: If the credentials are incorrect.
    """
    logger.info(f"Admin login attempt for email: {form_data.email}")

    # Normalize email
    normalized_email = normalize_input(form_data.email)

    # Query the admin user using the normalized email
    admin = (
        db.query(User)
        .filter(User.email == normalized_email, User.is_admin == True)
        .first()
    )

    if not admin or not verify_password(form_data.password, admin.hashed_password):
        logger.warning(f"Invalid login attempt for admin email: {form_data.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin credentials"
        )

    # Generate the token with additional information
    access_token = create_access_token(
        data={
            "sub": admin.email,
            "user_name": admin.first_name,
            "user_id": admin.id,
            "is_verified": admin.is_verified,
            "profile_picture": admin.profile_picture,
            "role": "admin",
        }
    )

    logger.info(f"Access token created for admin: {normalized_email}")
    return {"access_token": access_token, "token_type": env_config.token_type}


# Admin Credentials Update Route
@router.put("/update-credentials", summary="Update Admin Credentials")
async def update_admin_credentials(
    credentials: UpdateAdminCredentials,
    current_admin: User = Depends(get_current_admin_or_super_admin),
    db: Session = Depends(get_db),
):
    """
    Update the admin credentials (email or password).

    ### Request Body:
    - `credentials` (UpdateAdminCredentials): The new email or password.

    ### Response:
    - A success message indicating the credentials have been updated.

    ### Raises:
    - `400 Bad Request`: If the email is already taken by another user.
    """
    logger.info(f"Admin {get_user_info(current_admin)} is updating credentials")
    admin_id, _ = get_user_info(current_admin)

    if credentials.email:
        # Normalize email
        normalized_email = normalize_input(credentials.email)

        # Check if the email is already taken by another user
        existing_user = db.query(User).filter(User.email == normalized_email).first()
        if existing_user and existing_user.id != admin_id:
            logger.warning(
                f"Email {credentials.email} is already in use by another user"
            )
            raise HTTPException(status_code=400, detail="Email is already taken")
        current_admin.email = normalized_email
        logger.info(f"Admin email updated to: {normalized_email}")

    if credentials.password:
        current_admin.hashed_password = hash_password(credentials.password)
        logger.info("Admin password updated successfully")

    db.commit()
    return {"message": "Admin credentials updated successfully"}


# Suspend User Account Route
@router.put("/suspend-user/{user_id}", summary="Suspend a user account")
async def suspend_user_account(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_or_super_admin),
):
    admin_id, admin_email, _ = get_user_info(current_admin)
    logger.info(f"Admin {admin_email} is suspending user ID: {user_id}")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.warning(f"User ID {user_id} not found for suspension.")
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    db.commit()
    logger.info(f"User ID {user_id} suspended successfully by admin {admin_email}.")
    return {"message": "User suspended successfully"}


# Reactivate User Account Route
@router.put("/reactivate-user/{user_id}", summary="Reactivate User Account")
async def reactivate_user_account(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_or_super_admin),
):
    """
    Reactivate a suspended user's account by setting `is_active` to True.

    ### Path Parameters:
    - `user_id` (int): The ID of the user to reactivate.

    ### Response:
    - A message confirming the user's account has been reactivated.

    ### Raises:
    - `404 Not Found`: If the user is not found.
    """
    logger.info(
        f"Admin {get_user_info(current_admin)} is reactivating user ID: {user_id}"
    )
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        logger.error(f"User ID {user_id} not found for reactivation")
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_active:
        logger.warning(f"User ID {user_id} account is already active")
        raise HTTPException(status_code=400, detail="User account is already active")

    user.is_active = True  # Set the user's account as active
    db.commit()
    logger.info(f"User ID {user_id} has been reactivated")
    return {"message": f"User {user_id} has been reactivated"}
