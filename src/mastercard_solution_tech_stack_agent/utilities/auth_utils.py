import secrets
import string
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from src.mastercard_solution_tech_stack_agent.config.appconfig import env_config
from src.mastercard_solution_tech_stack_agent.database.pd_db import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


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
            user.is_expert,
        )
    except AttributeError:
        # ❌ Not Compact Case: Handle missing attributes with fallback defaults
        return (
            getattr(user, "id", None),
            getattr(user, "email", "no-email"),
            getattr(user, "first_name", "Unknown"),
            getattr(user, "last_name", "Unknown"),
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
    except JWTError as exc:
        raise credentials_exception from exc

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
    except JWTError as exc:
        raise credentials_exception from exc

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
    system_logger.info("Hashing password")
    hashed_password = pwd_context.hash(password)
    system_logger.info("Password hashed successfully")
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
    system_logger.info("Verifying password")
    is_valid = pwd_context.verify(plain_password, hashed_password)
    if is_valid:
        system_logger.info("Password verified successfully")
    else:
        system_logger.warning("Password verification failed")
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
    system_logger.info("Creating access token with 24-hour expiry")

    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta

    # Add expiration to token payload
    to_encode.update({"exp": expire})

    # Encode the JWT token
    encoded_jwt = jwt.encode(
        to_encode, env_config.secret_key, algorithm=env_config.algorithm
    )
    system_logger.info("Access token created successfully")
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
    system_logger.info("Creating refresh token with 7-day expiry")

    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode, env_config.secret_key, algorithm=env_config.algorithm
    )
    system_logger.info("Refresh token created successfully")
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

    system_logger.info("Checking admin or super-admin privileges for user: %s", email)
    if role not in ["admin", "super-admin"]:
        system_logger.error(
            "User %s does not have admin or super-admin privileges", email
        )
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

    system_logger.info("Checking super-admin privileges for user: %s", email)
    if role != "super-admin":
        system_logger.error("User %s does not have super-admin privileges", email)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
    return current_use
