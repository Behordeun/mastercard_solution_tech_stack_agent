import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from authlib.integrations.starlette_client import OAuth
from starlette.requests import Request

from src.mastercard_solution_tech_stack_agent.api.data_model import (
    ConfirmAccountDeletion,
    RecoverAccountRequest,
)
from src.mastercard_solution_tech_stack_agent.config.appconfig import env_config
from src.mastercard_solution_tech_stack_agent.config.db_setup import get_db
from src.mastercard_solution_tech_stack_agent.database.schemas import User
from src.mastercard_solution_tech_stack_agent.error_trace.errorlogger import (
    system_logger,
)
from src.mastercard_solution_tech_stack_agent.utilities.auth_utils import (
    create_access_token,
    create_refresh_token,
    generate_random_otp,
    get_current_admin_or_super_admin,
    get_current_super_admin,
    get_current_user,
    normalize_input,
    verify_password,
)

# from src.mastercard_solution_tech_stack_agent.utilities.email_utils import (
#    send_account_deletion_confirmation_email,
#    send_account_deletion_verification_email,
#    send_confirmation_email,
# )


# === Log directory setup ===
LOG_DIR = "src/mastercard_solution_tech_stack_agent/logs"
os.makedirs(LOG_DIR, exist_ok=True)  # Ensure the logs directory exists

# === Log file paths ===
LOG_FILES = {
    "info": os.path.join(LOG_DIR, "info.log"),
    "warning": os.path.join(LOG_DIR, "warning.log"),
    "error": os.path.join(LOG_DIR, "error.log"),
}


# Initialize OAuth
oauth = OAuth()
oauth.register(
    name='google',
    client_id=env_config.google_client_id,
    client_secret=env_config.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(
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


@router.get("/health", summary="Health Check")
async def health_check():
    """
    ## Health Check Endpoint
    This route is used to verify that the service is running and healthy.

    ### Response:
    - Returns a JSON response indicating the service status.
    """
    system_logger.info("Health check performed.")
    return {"status": "healthy"}


@router.get("/google/login")
async def google_login(request: Request):
    redirect_uri = env_config.google_redirect_uri
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = await oauth.google.parse_id_token(request, token)

        email = normalize_input(user_info.get("email"))
        first_name = user_info.get("given_name")
        last_name = user_info.get("family_name")

        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_verified=True,
                is_admin=False,
                created_at=datetime.now(timezone.utc),
            )
            db.add(user)
            db.commit()

        access_token = create_access_token({
            "sub": email,
            "name": f"{first_name} {last_name}",
            "role": "user",
            "is_verified": True,
        })

        refresh_token = create_refresh_token({"sub": email})

        response = RedirectResponse(url="/docs")  # or a frontend page
        response.set_cookie(key="refresh_token", value=refresh_token, httponly=True)
        response.set_cookie(key="access_token", value=access_token, httponly=True)

        return response

    except Exception as e:
        system_logger.exception("Google login failed")
        raise HTTPException(status_code=400, detail="Google login failed")


# Token route to handle login for super-admin, admin, and user
@router.post("/token", summary="Login and Obtain Access & Refresh Tokens")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    system_logger.info("Login attempt by user: %s", form_data.username)

    normalized_email = normalize_input(form_data.username)

    # Super-admin login
    if (
        normalized_email == normalize_input(env_config.super_admin_email)
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
            max_age=7 * 24 * 60 * 60,
        )
        return response

    # Regular user login
    user = db.query(User).filter(User.email == normalized_email).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        system_logger.error("Invalid login credentials.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_verified:
        system_logger.error("Login attempt on unverified account.")
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
        max_age=7 * 24 * 60 * 60,
    )
    return response


@router.post("/auth/refresh-token", summary="Refresh Access Token")
async def refresh_access_token(response: Response, db: Session = Depends(get_db)):
    """
    Refresh the access token using the refresh token stored in HTTP-only cookies.
    """
    system_logger.info("Refreshing access token...")

    credentials_exception = HTTPException(
        status_code=401,
        detail="Invalid refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Retrieve refresh token from cookies
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise credentials_exception

    try:
        payload = jwt.decode(refresh_token, env_config.secret_key, env_config.algorithm)
        email: str = normalize_input(payload.get("sub"))
        if email is None:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc

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
            "name": f"{user.first_name} {user.last_name}",
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
    system_logger.info("Admin or Super-admin %s is checking admin status", email)
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
    system_logger.info("Admin-protected route accessed by: %s", email)
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
    system_logger.info("Super-admin %s is checking status", email)
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
    system_logger.info(f"Super-admin {email} is accessing a protected route")
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
    system_logger.info("Requesting account deletion")

    # Normalize email
    otp = generate_random_otp()
    current_user.otp = otp
    db.commit()

    # await send_account_deletion_verification_email(
    #    normalized_email, current_user.first_name, otp
    # )
    system_logger.info("OTP sent to user's email")
    return {"message": f"Your OTP is {otp}. Please use it to confirm account deletion."}
    # return {
    #    "message": "OTP sent to your registered email address. Please use it to confirm account deletion."
    # }


@router.post("/confirm-account-deletion", summary="Confirm Account Deletion")
async def confirm_account_deletion(
    payload: ConfirmAccountDeletion, db: Session = Depends(get_db)
):
    system_logger.info("Confirming account deletion")

    # Normalize email
    normalized_email = normalize_input(payload.email)

    # Query the user by normalized email and OTP
    user = (
        db.query(User)
        .filter(User.email == normalized_email, User.otp == payload.otp)
        .first()
    )

    if not user:
        system_logger.error("Invalid OTP or email")
        raise HTTPException(status_code=400, detail="Invalid OTP or email")

    # Soft delete the user account by marking `is_deleted` as True
    user.is_deleted = True
    user.otp = None # Clear the OTP from the DB table
    db.commit()

    # Send confirmation email for account deletion
    # await send_account_deletion_confirmation_email(payload.email, user.first_name)
    system_logger.info("Account deleted successfully")
    return {"message": "Your account has been successfully deleted."}


@router.post("/recover-account", summary="Recover Account")
async def recover_account(
    payload: RecoverAccountRequest, db: Session = Depends(get_db)
):
    system_logger.info("Recovering account")

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
        system_logger.error("Invalid OTP or email")
        raise HTTPException(status_code=400, detail="Invalid OTP or email")

    # Recover the account
    user.is_deleted = False
    user.otp = None  # Clear the OTP after successful recovery
    db.commit()

    # Send a confirmation email
    # await send_confirmation_email(user.email, user.first_name)
    system_logger.info("Account recovered successfully")

    return {"message": "Account successfully recovered"}
