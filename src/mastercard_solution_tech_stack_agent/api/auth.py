import logging
import os
import secrets
import string
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from src.mastercard_solution_tech_stack_agent.api.schemas import (
    ConfirmAccountDeletion,
    PaginationMetadata,
    RecoverAccountRequest,
)
from src.mastercard_solution_tech_stack_agent.config.appconfig import env_config
from src.mastercard_solution_tech_stack_agent.config.db_setup import get_db
from src.mastercard_solution_tech_stack_agent.database.schemas import User
from src.mastercard_solution_tech_stack_agent.utilities.email_utils import (
    send_account_deletion_confirmation_email,
    send_account_deletion_verification_email,
    send_confirmation_email,
)

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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
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


# Helper function to retrieve consistent user information
def normalize_input(value: str) -> str:
    """
    Normalize input by converting to lowercase and stripping whitespace.

    Args:
        value (str): Input string to normalize.

    Returns:
        str: Normalized string.
    """
    return value.strip().lower() if value else value


def get_user_info(user):
    """
    Retrieves user information using the compact & not compact logic.

    Args:
    - user (User): The currently authenticated user.

    Returns:
    - Tuple[int, str, str, str, str, bool]: Always returns exactly 6 values.
    """
    try:
        # ✅ Compact Case: If all attributes exist, return them directly
        return (
            user.id,
            user.email,
            user.first_name,
            user.last_name,
            user.username,
            user.is_expert,
        )
    except AttributeError:
        # ❌ Not Compact Case: Handle missing attributes with fallback defaults
        return (
            getattr(user, "id", None),
            getattr(user, "email", "no-email"),
            getattr(user, "first_name", "Unknown"),
            getattr(user, "last_name", "Unknown"),
            getattr(user, "username", "no-username"),
            getattr(user, "is_expert", False),
        )


def generate_random_otp(length: int = 6) -> str:
    """Generates a secure random OTP with a default length of 6 digits."""
    digits = string.digits  # '0123456789'
    return "".join(secrets.choice(digits) for _ in range(length))


# Generate pagination metadata
def generate_pagination_metadata(query, limit: int = 10, offset: int = 0):
    """
    Generate pagination metadata for a query.

    Args:
        query: SQLAlchemy query object.
        limit: Number of results per page (default: 10).
        offset: Starting offset (default: 0).

    Returns:
        dict: Metadata with total count, current page, and limits.
    """
    total_count = query.count()
    current_page = (offset // limit) + 1
    total_pages = (total_count // limit) + (1 if total_count % limit else 0)

    return PaginationMetadata(
        total=total_count,
        limit=limit,
        offset=offset,
        current_page=current_page,
        total_pages=total_pages,
    )


# Verify super-admin and admin roles
def verify_super_admin_or_admin(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    """
    Verify if the current user is the super-admin or admin.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, env_config.secret_key, env_config.algorithm)
        email: str = normalize_input(payload.get("sub"))
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Check if the user is the super-admin
    if email == normalize_input(env_config.super_admin_email):
        return {"email": email, "role": "super-admin"}

    # Otherwise, check if the user is an admin
    user = db.query(User).filter(User.email == email).first()
    if user and user.is_admin:
        return {"email": email, "role": "admin"}

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have the necessary permissions.",
    )


def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, env_config.secret_key, env_config.algorithm)
        user_email = normalize_input(payload.get("sub"))
        if user_email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == user_email).first()
    if user is None:
        raise credentials_exception

    # Check if the user is verified
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not verified. Please verify your account first.",
        )

    return user


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using bcrypt.

    ### Parameters:
    - `password` (str): The plaintext password to hash.

    ### Returns:
    - `str`: The hashed password.
    """
    logger.info("Hashing password")
    hashed_password = pwd_context.hash(password)
    logger.info("Password hashed successfully")
    return hashed_password


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a hashed password.

    ### Parameters:
    - `plain_password` (str): The user's entered plaintext password.
    - `hashed_password` (str): The stored hashed password from the database.

    ### Returns:
    - `bool`: True if the password matches, False otherwise.
    """
    logger.info("Verifying password")
    is_valid = pwd_context.verify(plain_password, hashed_password)
    if is_valid:
        logger.info("Password verified successfully")
    else:
        logger.warning("Password verification failed")
    return is_valid


# Generate a JWT access token with email and role
def create_access_token(data: dict, expires_delta: timedelta = timedelta(hours=24)):
    """
    Create a JWT access token with a default expiry of 24 hours.

    ### Parameters:
    - `data` (dict): The claims to include in the token.
    - `expires_delta` (timedelta): The expiration duration.

    ### Returns:
    - `str`: The encoded JWT token.
    """
    logger.info("Creating access token with 24-hour expiry")

    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta

    # Add expiration to token payload
    to_encode.update({"exp": expire})

    # Encode the JWT token
    encoded_jwt = jwt.encode(
        to_encode, env_config.secret_key, algorithm=env_config.algorithm
    )
    logger.info("Access token created successfully")
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: timedelta = timedelta(days=7)):
    """
    Create a JWT refresh token with a default expiry of 7 days.

    ### Parameters:
    - `data` (dict): The claims to include in the token.
    - `expires_delta` (timedelta): The expiration duration.

    ### Returns:
    - `str`: The encoded JWT refresh token.
    """
    logger.info("Creating refresh token with 7-day expiry")

    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode, env_config.secret_key, algorithm=env_config.algorithm
    )
    logger.info("Refresh token created successfully")
    return encoded_jwt


# Verify that the user has at least admin rights (either admin or super-admin)
def get_current_admin_or_super_admin(current_user: dict = Depends(get_current_user)):
    """
    Verify that the current user has either admin or super-admin privileges.

    Returns:
        dict or User: User info if they have admin or super-admin rights.

    Raises:
        HTTPException: If the user is neither an admin nor a super-admin.
    """
    # Use .get() if current_user is a dict, else access attributes directly
    email = (
        current_user.get("email")
        if isinstance(current_user, dict)
        else current_user.email
    )
    role = (
        current_user.get("role")
        if isinstance(current_user, dict)
        else ("admin" if current_user.is_admin else "user")
    )

    logger.info(f"Checking admin or super-admin privileges for user: {email}")
    if role not in ["admin", "super-admin"]:
        logger.warning(f"User {email} does not have admin or super-admin privileges")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
    return current_user


# Restrict access strictly to super-admin users
def get_current_super_admin(current_user: dict = Depends(get_current_user)):
    """
    Verify that the current user has super admin privileges.

    Returns:
        dict or User: User info if they have super-admin rights.

    Raises:
        HTTPException: If the user is not a super-admin.
    """
    # Use .get() if current_user is a dict, else access attributes directly
    email = (
        current_user.get("email")
        if isinstance(current_user, dict)
        else current_user.email
    )
    role = current_user.get("role") if isinstance(current_user, dict) else "user"

    logger.info(f"Checking super-admin privileges for user: {email}")
    if role != "super-admin":
        logger.warning(f"User {email} does not have super-admin privileges")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
    return current_user


@router.get("/health", summary="Health Check")
async def health_check():
    """
    ## Health Check Endpoint
    This route is used to verify that the service is running and healthy.

    ### Response:
    - Returns a JSON response indicating the service status.
    """
    logger.info("Health check performed.")
    return {"status": "healthy"}


# Token route to handle login for super-admin, admin, and user
@router.post("/token", summary="Login and Obtain Access & Refresh Tokens")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    logger.info(f"Login attempt by user: {form_data.username}")

    # Normalize email or username
    normalized_identifier = normalize_input(form_data.username)

    # Super-admin login
    if (
        normalized_identifier == normalize_input(env_config.super_admin_email)
        and form_data.password == env_config.super_admin_password
    ):
        access_token = create_access_token(
            data={
                "sub": env_config.super_admin_email,
                "role": "super-admin",
                "name": "Super Admin",
                "is_verified": True,
            }
        )
        refresh_token = create_refresh_token({"sub": env_config.super_admin_email})

        response = JSONResponse({"access_token": access_token, "token_type": "bearer"})
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            samesite="Strict",
            max_age=7 * 24 * 60 * 60,  # 7 days
        )

        logger.info("Super-admin login successful.")
        return response

    # Regular user login
    user = db.query(User).filter(User.email == normalized_identifier).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning("Invalid login credentials.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username, email, or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_verified:
        logger.warning("Login attempt on unverified account.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Account is not verified"
        )

    role = "admin" if user.is_admin else "user"
    access_token = create_access_token(
        data={
            "sub": user.email,
            "role": role,
            "name": f"{user.first_name} {user.last_name}",
            "is_verified": user.is_verified,
        }
    )
    refresh_token = create_refresh_token({"sub": user.email})

    response = JSONResponse({"access_token": access_token, "token_type": "bearer"})
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="Strict",
        max_age=7 * 24 * 60 * 60,  # 7 days
    )

    logger.info(f"User {user.email} logged in successfully.")
    return response


@router.post("/auth/refresh-token", summary="Refresh Access Token")
async def refresh_access_token(response: Response, db: Session = Depends(get_db)):
    """
    Refresh the access token using the refresh token stored in HTTP-only cookies.
    """
    logger.info("Refreshing access token...")

    credentials_exception = HTTPException(
        status_code=401,
        detail="Invalid refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Retrieve refresh token from cookies
    refresh_token = response.cookies.get("refresh_token")
    if not refresh_token:
        raise credentials_exception

    try:
        payload = jwt.decode(refresh_token, env_config.secret_key, env_config.algorithm)
        email: str = normalize_input(payload.get("sub"))
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Fetch user
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise credentials_exception

    # Generate a new access token
    role = "admin" if user.is_admin else "user"
    new_access_token = create_access_token(
        data={
            "sub": user.email,
            "role": role,
            "name": user.name,
            "is_verified": user.is_verified,
        }
    )

    return {"access_token": new_access_token, "token_type": "bearer"}


# Admin check
@router.get("/admin/status")
async def check_admin_status(
    current_admin: dict = Depends(get_current_admin_or_super_admin),
):
    """
    Check Admin Status endpoint for admins and super-admins.

    Returns:
        dict: Confirmation message for admin access.
    """
    # Use .get() if current_admin is a dict, else access attributes directly
    email = (
        current_admin.get("email")
        if isinstance(current_admin, dict)
        else current_admin.email
    )
    logger.info(f"Admin or Super-admin {email} is checking admin status")
    return {"message": "You have admin access!"}


# Token creation for login
@router.get("/admin-protected")
async def admin_protected_route(
    current_admin: dict = Depends(get_current_admin_or_super_admin),
):
    """
    Admin-only protected route, accessible by admins and super-admins.

    Returns:
        dict: Welcome message for the admin-protected route.
    """
    email = (
        current_admin.get("email")
        if isinstance(current_admin, dict)
        else current_admin.email
    )
    logger.info(f"Admin-protected route accessed by: {email}")
    return {"message": "Welcome to the admin-protected route!"}


# Super-admin check
@router.get("/super-admin/status")
async def check_super_admin_status(
    current_super_admin: dict = Depends(get_current_super_admin),
):
    """
    Check Super Admin Status endpoint for super-admins.

    Returns:
        dict: Confirmation message for super-admin access.
    """
    email = (
        current_super_admin.get("email")
        if isinstance(current_super_admin, dict)
        else current_super_admin.email
    )
    logger.info(f"Super-admin {email} is checking status")
    return {"message": "You are a super-admin!"}


@router.get("/super-admin-protected")
async def super_admin_protected_route(
    current_super_admin: dict = Depends(get_current_super_admin),
):
    """
    Super Admin-only protected route.

    Returns:
        dict: Welcome message for the super-admin-protected route.
    """
    email = (
        current_super_admin.get("email")
        if isinstance(current_super_admin, dict)
        else current_super_admin.email
    )
    logger.info(f"Super-admin {email} is accessing a protected route")
    return {"message": "Welcome, super-admin!"}


@router.post("/request-account-deletion", summary="Request Account Deletion")
async def request_account_deletion(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    ## Request Account Deletion
    Allows a logged-in user to request deletion of their account. An OTP is sent to the user's email for confirmation.

    ### Response:
    - A message confirming that an OTP has been sent to the user's email.
    """
    logging.info("Requesting account deletion")

    # Normalize email
    normalized_email = normalize_input(current_user.email)
    otp = generate_random_otp()
    current_user.otp = otp
    db.commit()

    await send_account_deletion_verification_email(
        normalized_email, current_user.first_name, otp
    )
    logging.info("OTP sent to user's email")
    return {
        "message": "OTP sent to your registered email address. Please use it to confirm account deletion."
    }


@router.post("/confirm-account-deletion", summary="Confirm Account Deletion")
async def confirm_account_deletion(
    payload: ConfirmAccountDeletion, db: Session = Depends(get_db)
):
    logging.info("Confirming account deletion")

    # Normalize email
    normalized_email = normalize_input(payload.email)

    # Query the user by normalized email and OTP
    user = (
        db.query(User)
        .filter(User.email == normalized_email, User.otp == payload.otp)
        .first()
    )

    if not user:
        logging.warning("Invalid OTP or email")
        raise HTTPException(status_code=400, detail="Invalid OTP or email")

    # Soft delete the user account by marking `is_deleted` as True
    user.is_deleted = True
    user.otp = None  # Clear the OTP after confirmation
    db.commit()

    # Send confirmation email for account deletion
    await send_account_deletion_confirmation_email(payload.email, user.first_name)
    logging.info("Account deleted successfully")
    return {"message": "Your account has been successfully deleted."}


@router.post("/recover-account", summary="Recover Account")
async def recover_account(
    payload: RecoverAccountRequest, db: Session = Depends(get_db)
):
    logging.info("Recovering account")

    # Find the user based on the email and OTP, and check if the account is soft-deleted
    user = (
        db.query(User)
        .filter(
            User.email == payload.email,
            User.otp == payload.otp,
            User.is_deleted == True,
        )
        .first()
    )

    if not user:
        logging.warning("Invalid OTP or email")
        raise HTTPException(status_code=400, detail="Invalid OTP or email")

    # Recover the account
    user.is_deleted = False
    user.otp = None  # Clear the OTP after successful recovery
    db.commit()

    # Send a confirmation email
    await send_confirmation_email(user.email, user.first_name)
    logging.info("Account recovered successfully")

    return {"message": "Account successfully recovered"}
