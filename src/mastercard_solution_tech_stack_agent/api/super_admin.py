import logging
import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from src.mastercard_solution_tech_stack_agent.api.auth import (
    create_access_token,
    normalize_input,
    verify_password,
    verify_super_admin_or_admin,
)
from src.mastercard_solution_tech_stack_agent.api.schemas import (
    PaginatedResponse,
    UserProfileResponse,
)
from src.mastercard_solution_tech_stack_agent.config.appconfig import env_config
from src.mastercard_solution_tech_stack_agent.config.db_setup import get_db
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


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

router = APIRouter(
    prefix="/super-admin",
    tags=["super-admin"],
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


# Super-admin login route
@router.post("/login", summary="Super Admin Login")
async def super_admin_login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    """
    Super Admin Login with email and password.

    ### Request:
    - `username` (str): Super Admin email.
    - `password` (str): Super Admin password.

    ### Response:
    - Access token if the login is successful.

    ### Raises:
    - `401 Unauthorized`: If the credentials are incorrect.
    """
    # Normalize email
    normalized_email = normalize_input(form_data.username)

    # Check if the Super Admin user exists in the database
    super_admin = db.query(User).filter(User.email == normalized_email).first()

    if not super_admin:
        logger.error("Super Admin account not found. Please check initialization.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Super Admin account is not initialized. Contact the system administrator.",
        )

    # Verify the provided credentials
    if not verify_password(form_data.password, super_admin.hashed_password):
        logger.warning(f"Failed login attempt for {normalized_email}.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    # Generate token
    access_token = create_access_token(
        data={
            "sub": super_admin.email,
            "user_name": super_admin.first_name,
            "user_id": super_admin.id,
            "is_verified": super_admin.is_verified,
            "profile_picture": None,
            "role": "super-admin",
        }
    )

    logger.info(f"Super Admin {normalized_email} logged in successfully.")
    return {"access_token": access_token, "token_type": env_config.token_type}


# Assign Admin Access to a User (Super Admin only)
@router.post("/assign-admin/{username}", summary="Assign Admin Access to a User")
async def assign_admin_access(
    username: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_super_admin_or_admin),
):
    """
    Assign admin access to a user by their username.

    ### Path Parameters:
    - `username` (str): The username of the user to promote to admin.

    ### Response:
    - A JSON object containing details about the user after admin access is granted.

    ### Raises:
    - `403 Forbidden`: If the current user is not a super-admin.
    - `404 Not Found`: If the user is not found.
    - `400 Bad Request`: If the user is already an admin.
    """
    logger.info(f"Attempting to assign admin access to username: {username}")

    # Normalize and log the username
    normalized_username = normalize_input(username)
    logger.debug(f"Normalized username: {normalized_username}")

    # Query user
    user = db.query(User).filter(User.username.ilike(normalized_username)).first()

    # Check if user exists
    if not user:
        logger.error(f"User with username '{normalized_username}' not found.")
        raise HTTPException(status_code=404, detail="User not found.")

    # Check if user is already an admin
    if user.is_admin:
        logger.info(
            f"User '{normalized_username}' is already an admin. No changes made."
        )
        return {
            "message": f"User '{username}' is already an admin.",
            "user_id": user.id,
            "username": user.username,
            "is_admin": user.is_admin,
        }

    # Assign admin rights
    try:
        user.is_admin = True
        db.commit()
        db.refresh(user)
        logger.info(f"Admin rights successfully assigned to '{normalized_username}'.")

        return {
            "message": f"Admin access granted to user '{username}'.",
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "is_admin": user.is_admin,
            "is_verified": user.is_verified,
            "is_active": user.is_active,
        }

    except Exception as e:
        logger.error(f"Failed to assign admin access: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Internal server error during admin assignment."
        )


@router.post("/revoke-admin/{username}", summary="Revoke Admin Access from a User")
async def revoke_admin_access(
    username: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_super_admin_or_admin),
):
    """
    Revoke admin access from a user by their username.

    ### Path Parameters:
    - `username` (str): The username of the user to revoke admin access from.

    ### Response:
    - A message confirming admin access has been revoked.

    ### Raises:
    - `404 Not Found`: If the user is not found.
    - `400 Bad Request`: If the user is not an admin.
    """
    logger.info(f"Revoking admin access for user with username: {username}")

    # Normalize username
    normalized_username = normalize_input(username)

    # Query the user by username
    user = db.query(User).filter(User.username.ilike(normalized_username)).first()

    if not user:
        logger.error(f"User with username '{normalized_username}' not found.")
        raise HTTPException(status_code=404, detail="User not found")

    if not user.is_admin:
        logger.warning(f"User '{normalized_username}' is not an admin.")
        raise HTTPException(status_code=400, detail="User is not an admin")

    # Revoke admin access
    user.is_admin = False
    db.commit()

    logger.info(f"Admin access revoked for user '{normalized_username}'.")
    return {
        "message": f"Admin access revoked for user '{username}'.",
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "is_admin": user.is_admin,
        "is_verified": user.is_verified,
        "is_active": user.is_active,
    }


# Endpoint to list all admins
@router.get(
    "/list-admins",
    response_model=PaginatedResponse[UserProfileResponse],
    summary="List All Admins",
)
async def list_admins(
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_super_admin_or_admin),
):
    """
    List all users with admin access.

    ### Response:
    - A paginated list of users who have admin access.

    ### Raises:
    - None
    """
    logger.info("Listing all users with admin access.")

    # Query for admin users
    admins_query = db.query(User).filter(User.is_admin == True)

    # Generate pagination metadata
    metadata = generate_pagination_metadata(admins_query, limit, offset)

    # Fetch paginated results
    admins = admins_query.offset(metadata.offset).limit(metadata.limit).all()

    # Transform the results into the response model
    results = [UserProfileResponse.from_orm(admin) for admin in admins]

    return PaginatedResponse(metadata=metadata.dict(), results=results)


# Super-admin inherits the admin permissions (through dependency injection)
admin_router = APIRouter(
    prefix="/admin", tags=["admin"], dependencies=[Depends(verify_super_admin_or_admin)]
)


# Suspend User Account Route
@admin_router.put("/suspend-user/{user_id}", summary="Suspend User Account")
async def suspend_user_account(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(verify_super_admin_or_admin),
):
    """
    Suspend a user's account by setting `is_active` to False.

    ### Path Parameters:
    - `user_id` (int): The ID of the user to suspend.

    ### Response:
    - A message confirming the user's account has been suspended.

    ### Raises:
    - `404 Not Found`: If the user is not found.
    """
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        logger.error(f"User with ID {user_id} not found for suspension.")
        raise HTTPException(status_code=404, detail="User not found")

    if not user.is_active:
        logger.warning(f"User with ID {user_id} account is already suspended.")
        raise HTTPException(status_code=400, detail="User account is already suspended")

    user.is_active = False  # Set the user's account as inactive (suspended)
    db.commit()
    logging.info("User account suspended successfully.")
    return {"message": f"User {user_id} has been suspended"}


# Reactivate User Account Route
@admin_router.put("/reactivate-user/{user_id}", summary="Reactivate User Account")
async def reactivate_user_account(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(verify_super_admin_or_admin),
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
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        logger.error(f"User with ID {user_id} not found for reactivation.")
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_active:
        logger.warning(f"User with ID {user_id} account is already active.")
        raise HTTPException(status_code=400, detail="User account is already active")

    user.is_active = True  # Set the user's account as active
    db.commit()
    logging.info("User account reactivated successfully.")
    return {"message": f"User {user_id} has been reactivated"}
