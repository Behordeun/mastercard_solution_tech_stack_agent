import os
import re
from datetime import datetime, timedelta, timezone

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

# from jose import jwt
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.mastercard_solution_tech_stack_agent.api.data_model import (
    PasswordResetConfirmation,
    PasswordUpdateSchema,
    TokenResponse,
    UserCreate,
    UserProfileResponse,
)
from src.mastercard_solution_tech_stack_agent.config.appconfig import env_config
from src.mastercard_solution_tech_stack_agent.config.db_setup import get_db
from src.mastercard_solution_tech_stack_agent.database.schemas import User, UserProfile
from src.mastercard_solution_tech_stack_agent.error_trace.errorlogger import (
    system_logger,
)
from src.mastercard_solution_tech_stack_agent.utilities.auth_utils import (
    create_access_token,
    create_refresh_token,
    generate_random_otp,
    get_current_user,
    hash_password,
    normalize_input,
    verify_password,
)

# from src.mastercard_solution_tech_stack_agent.utilities.email_utils import (
#    send_confirmation_email,
#    send_password_reset_confirmation_email,
#    send_password_reset_email,
#    send_verification_email,
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


oauth = OAuth()

oauth.register(
    name="google",
    client_id=env_config.google_client_id,
    client_secret=env_config.google_client_secret,
    authorize_url=env_config.google_auth_authorize_url,
    authorize_params=None,
    access_token_url=env_config.google_access_token_url,
    access_token_params=None,
    refresh_token_url=None,
    redirect_uri=env_config.google_redirect_uri,
    client_kwargs={"scope": "openid email profile"},
    state=None,
)


# Password validation function
def validate_password_strength(password: str):
    """
    Validates the strength of a password.

    Password requirements:
    - Must be at least eight (8) characters long.
    - Must contain at least one uppercase letter.
    - Must contain at least one lowercase letter.
    - Must contain at least one digit.
    - Must contain at least one special character, including underscores.

    Raises:
        HTTPException: If the password does not meet the criteria.
    """
    if len(password) < 8:
        raise HTTPException(
            status_code=400, detail="Password must be at least 8 characters long."
        )
    if not re.search(r"[A-Z]", password):
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least one uppercase letter.",
        )
    if not re.search(r"[a-z]", password):
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least one lowercase letter.",
        )
    if not re.search(r"\d", password):
        raise HTTPException(
            status_code=400, detail="Password must contain at least one digit."
        )
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>_]", password):  # Allow underscores
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least one special character, including underscores.",
        )


# User Registration with JWT
@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="User Registration with JWT",
)
async def user_registration(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Handles user registration by creating entries in both the `users` and `user_profiles` tables.

    Args:
        user_data (UserCreate): The user registration data.
        db (Session): The database session.

    Returns:
        TokenResponse: The JWT access token for the registered user.
    """
    try:
        # Normalize email
        normalized_email = user_data.email.lower()

        # Check if email is already registered
        existing_user = (
            db.query(User).filter(User.email.ilike(normalized_email)).first()
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered.",
            )

        # Validate password strength
        validate_password_strength(user_data.password)

        # Hash the password
        hashed_password = hash_password(user_data.password)

        # Generate OTP for email verification
        otp = generate_random_otp()

        # Use a nested transaction to ensure ACID compliance
        with db.begin_nested():
            # Create a new user in the `users` table
            new_user = User(
                email=normalized_email,
                hashed_password=hashed_password,
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                is_active=True,
                is_verified=False,
                is_admin=False,
                is_super_admin=False,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(new_user)
            db.flush()  # Flush to get the new user's ID

            # Create a corresponding user profile in the `user_profiles` table
            new_user_profile = UserProfile(
                user_id=new_user.id,
                profile_picture=user_data.profile_picture,
                otp=otp,
                otp_created_at=datetime.now(timezone.utc),
            )
            db.add(new_user_profile)

        # Explicitly commit the transaction
        db.commit()

        # Send verification email
        # await send_verification_email(normalized_email, user_data.first_name, otp)

        # Generate JWT access token
        access_token = create_access_token(
            data={
                "sub": new_user.email,
                "user_name": new_user.first_name,
                "user_id": new_user.id,
                "is_verified": new_user.is_verified,
                "role": "user",
            }
        )

        return TokenResponse(
            access_token=access_token, token_type=env_config.token_type
        )

    except SQLAlchemyError as e:
        system_logger.error("Database error during registration: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user due to a server error.",
        ) from e
    except Exception as e:
        system_logger.error("Unexpected error during registration: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during registration.",
        ) from e


@router.get(
    "/verify",
    summary="Verify User Email with OTP via Link",
    response_model=dict,
)
async def user_verification_via_link(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Verifies a user's email using the link sent to their email with the OTP.

    ### Response:
    - A success message confirming user verification.
    - A message notifying if the user is already verified.

    ### Raises:
    - `404 Not Found`: If the user is not found.
    - `400 Bad Request`: If the OTP is invalid or expired.
    """
    # Extract email and OTP from query parameters
    email = request.query_params.get("email")
    otp = request.query_params.get("otp")

    if not email or not otp:
        raise HTTPException(
            status_code=400,
            detail="Email and OTP are required for verification.",
        )

    # Normalize email
    normalized_email = email.lower().strip()

    # Fetch the user by email
    user = db.query(User).filter(User.email == normalized_email).first()

    if not user:
        system_logger.error(
            "Verification attempt for non-existent email: %s", normalized_email
        )
        raise HTTPException(status_code=404, detail="User not found")

    # Fetch the user's profile to get the OTP and OTP creation time
    user_profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()

    if not user_profile:
        system_logger.error(
            "Verification attempt for user without a profile: %s", normalized_email
        )
        raise HTTPException(status_code=404, detail="User profile not found")

    # Check if the user is already verified
    if user.is_verified:
        system_logger.info("User %s is already verified.", normalized_email)
        return {"message": "This account is already verified."}

    # Check if OTP is valid
    if user_profile.otp != otp:
        system_logger.error()("Invalid OTP attempt for email: %s", normalized_email)
        raise HTTPException(status_code=400, detail="Invalid OTP")

    # Check if OTP is expired
    if user_profile.otp_created_at:
        time_since_otp = datetime.now(timezone.utc) - user_profile.otp_created_at
        if time_since_otp.total_seconds() > 86400:  # 24 hours
            system_logger.error("Expired OTP attempt for email: %s", normalized_email)
            raise HTTPException(
                status_code=400,
                detail="OTP has expired. Please request a new verification email.",
            )

    # Mark user as verified
    user.is_verified = True
    user_profile.otp = None
    user_profile.otp_created_at = (
        None  # Clear the OTP timestamp after successful verification
    )
    db.commit()

    # Optionally send a confirmation email
    # try:
    #    await send_confirmation_email(user.email, user.first_name)
    #    system_logger.info(f"User {normalized_email} verified successfully")
    # except Exception as email_error:
    #    system_logger.error(
    #        f"Failed to send confirmation email to {normalized_email}: {email_error}"
    #    )

    return {"message": "User verified successfully"}


THROTTLE_DURATION_SECONDS = 300  # Configurable throttle duration


@router.post(
    "/resend-verification-email",
    summary="Resends the verification email to ease account verification at the user's convenience",
    response_model=dict,
)
async def resend_verification_email(
    email: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    """
    Resends the verification email to the user's email address.

    ### Parameters:
    - `email` (str): The email address of the user requesting a new verification email.

    ### Response:
    - A success message confirming the resend of the verification email.
    - A message notifying if the user is already verified.

    ### Raises:
    - `404 Not Found`: If no user is found with the provided email.
    - `400 Bad Request`: If the user is already verified.
    - `429 Too Many Requests`: If the user attempts to resend emails too frequently.
    """
    normalized_email = normalize_input(email)

    # Fetch user by email
    user = db.query(User).filter(User.email == normalized_email).first()
    if not user:
        system_logger.error(
            "Resend verification attempt for non-existent email: %s", email
        )
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_verified:
        system_logger.info("User %s is already verified.", email)
        return {"message": f"The account associated with {email} is already verified."}

    # Enforce throttle limit
    if user.otp_created_at:
        time_since_last_otp = datetime.now(timezone.utc) - user.otp_created_at
        if time_since_last_otp.total_seconds() < THROTTLE_DURATION_SECONDS:
            next_allowed_request = user.otp_created_at + timedelta(
                seconds=THROTTLE_DURATION_SECONDS
            )
            system_logger.error(
                "Verification email resend throttled for email= %s", email
            )
            return JSONResponse(
                status_code=429,
                content={
                    "message": "Please wait before requesting another verification email.",
                    "next_allowed_request": next_allowed_request.isoformat(),
                },
            )

    # Generate a new OTP and update the user record
    otp = generate_random_otp()
    user.otp = otp
    user.otp_created_at = datetime.now(timezone.utc)
    db.commit()

    # Send the verification email
    # try:
    # await send_verification_email(user.email, user.first_name, otp)
    #    system_logger.info(f"Verification email resent to email={email}")
    # except Exception as email_error:
    #    system_logger.error(
    #        f"Failed to send verification email to email={email}: {email_error}"
    #    )
    #    raise HTTPException(
    #        status_code=500,
    #        detail="Failed to send verification email. Please try again later.",
    #    )

    return {"message": f"Verification email has been resent to {email}."}


@router.post("/login", summary="Login via  Email")
async def user_login(
    email: str = Body(..., embed=True, description="Email"),
    password: str = Body(..., embed=True, description="User password"),
    db: Session = Depends(get_db),
):
    """
    Allows users to log in using their email.

    Args:
        email (str): The email of the user.
        password (str): The user's password.
        db (Session): The database session.

    Returns:
        JSONResponse: Access token, refresh token, and user details.
    """
    system_logger.info("Login attempt by user", additional_info={"email": email})

    # Normalize input to lowercase
    normalized_email = normalize_input(email)

    # Identify user by email
    db_user = db.query(User).filter((User.email == normalized_email)).first()

    # Fetch the user's profile from the UserProfile table
    user_profile = (
        db.query(UserProfile).filter(UserProfile.user_id == db_user.id).first()
    )

    if not db_user or not verify_password(password, db_user.hashed_password):
        system_logger.error("Invalid login credentials.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The provided credentials are incorrect",
        )

    if db_user.is_deleted:
        system_logger.error("Login attempt on deleted account: %s", db_user.email)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account has been deleted. Contact support for recovery.",
        )

    # Determine the role based on boolean fields
    role = (
        "super_admin"
        if db_user.is_super_admin
        else "admin" if db_user.is_admin else "user"
    )

    # 🔥 Generate Access Token (Valid for 24 Hours)
    access_token = create_access_token(
        data={
            "sub": db_user.email,
            "user_name": db_user.first_name,
            "user_id": db_user.id,
            "is_verified": db_user.is_verified,
            "profile_picture": user_profile.profile_picture,
            "role": role,
        }
    )

    # 🔥 Generate Refresh Token (Valid for 7 Days)
    refresh_token = create_refresh_token({"sub": db_user.email})

    # Response with Access Token + Secure Refresh Token in Cookie
    response = JSONResponse(
        {
            "access_token": access_token,
            "token_type": env_config.token_type,
            "user": {
                "id": db_user.id,
                "name": db_user.first_name,
                "role": role,
                "email": db_user.email,
                "is_verified": db_user.is_verified,
                "profile_picture": user_profile.profile_picture,
            },
        }
    )

    # Set the Refresh Token in Secure HTTP-Only Cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,  # Prevents JavaScript access (mitigates XSS attacks)
        samesite="Strict",
        max_age=7 * 24 * 60 * 60,  # 7 Days Expiry
    )

    system_logger.info(
        "User logged in successfully.",
        additional_info={"email": db_user.email},
    )
    return response


@router.post("/forgot-password", summary="Request Password Reset")
async def forgot_password(
    response: Response,  # Added Response for setting cookies
    email: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    """
    Allows a user to request a password reset by generating a reset link and sending it to their email.

    - **Stores OTP in an HTTP-only cookie** to prevent abuse.
    - **Prevents multiple resets within a cooldown period**.
    - **Ensures OTP expires after 24 hours**.

    ### Request:
    - `email` (str): The user's email address.

    ### Response:
    - A message confirming that a password reset link has been sent to the user's email.

    ### Raises:
    - `404 Not Found`: If the user is not found.
    - `400 Bad Request`: If an OTP was requested too recently.
    """
    # Normalize email
    normalized_email = normalize_input(email)

    # Retrieve user by email
    user = db.query(User).filter(User.email == normalized_email).first()

    if not user:
        system_logger.error(
            "Password reset requested for non-existent email: %s", normalized_email
        )
        raise HTTPException(status_code=404, detail="User not found")

    # Check if OTP already exists and is still valid
    current_time = datetime.now(timezone.utc)
    if user.otp and user.otp_created_at:
        time_since_last_request = (current_time - user.otp_created_at).total_seconds()

        # If OTP is still valid (within 24 hours), resend the same OTP
        if time_since_last_request < 86400:  # 24 hours
            system_logger.info(
                "Resending existing OTP for %s (Still valid).", normalized_email
            )
            otp = user.otp
        else:
            # OTP expired - generate a new one
            otp = generate_random_otp()
            user.otp = otp
            user.otp_created_at = current_time  # Store OTP creation time
            db.commit()
    else:
        # No OTP exists - generate a new one
        otp = generate_random_otp()
        user.otp = otp
        user.otp_created_at = current_time  # Store OTP creation time
        db.commit()

    # Set an HTTP-only cookie to prevent abuse
    response.set_cookie(
        key="password_reset_token",
        value=otp,
        httponly=True,  # Prevent JavaScript access
        secure=True,  # Enforce HTTPS
        max_age=86400,  # 24 hours expiration
        samesite="Lax",
    )

    # Send OTP via email
    # await send_password_reset_email(normalized_email, user.first_name, otp)
    system_logger.info("Password reset link sent to %s", normalized_email)

    return {"message": "Password reset link sent to your email address."}


@router.post("/request-password-reset", summary="Request Password Reset")
async def request_password_reset(
    response: Response,  # Added Response for setting cookies
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Allows a logged-in user to request a password reset by generating and sending a password reset link.

    - **Stores OTP in an HTTP-only cookie** to prevent abuse.
    - **Prevents multiple resets by setting a cooldown period**.
    - **Sends an email with the reset link**.

    ### Response:
    - A message confirming that a password reset link has been sent to the user's email.
    """
    system_logger.info("Password reset request for %s", current_user.email)

    # Generate a secure OTP
    otp = generate_random_otp()
    current_user.otp = otp
    current_user.otp_created_at = datetime.now(timezone.utc)  # Track OTP creation time
    db.commit()

    # Set an HTTP-only cookie to prevent abuse
    response.set_cookie(
        key="password_reset_token",
        value=otp,
        httponly=True,  # Prevent JavaScript access
        secure=True,  # Enforce HTTPS
        max_age=86400,  # 24 hours
        samesite="Lax",
    )

    # Send password reset OTP via email
    # await send_password_reset_email(current_user.email, current_user.first_name, otp)
    system_logger.info("Password reset link sent to %s", current_user.email)

    return {"message": "Password reset link sent to your email address."}


@router.post("/confirm-password-reset", summary="Confirm Password Reset with OTP")
async def confirm_password_reset(
    payload: PasswordResetConfirmation,
    db: Session = Depends(get_db),
):
    """
    Allows users to reset their password using an OTP, without being signed in.

    ### Request Body (JSON):
    - `email` (str): The user's email address.
    - `otp` (str): The OTP sent to the user's email.
    - `new_password` (str): The new password for the user.
    - `confirm_new_password` (str): Confirmation of the new password.

    ### Response:
    - A message confirming the successful password reset.

    ### Raises:
    - `400 Bad Request`: If the OTP is invalid, the passwords do not match, or the email is not provided.
    """
    # Validate the email and fetch the user
    user = (
        db.query(User)
        .filter(User.email == payload.email, User.otp == payload.otp)
        .first()
    )

    if not user:
        system_logger.error(
            f"""
            Password reset failed for email {
                payload.email} due to invalid OTP or email.
            """
        )
        raise HTTPException(status_code=400, detail="Invalid email or OTP")

    # Validate the OTP
    if user.otp != payload.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    # Validate if the new passwords match
    if payload.new_password != payload.confirm_new_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    # Validate password strength
    validate_password_strength(payload.new_password)

    # Update the user's password
    user.hashed_password = hash_password(payload.new_password)
    user.otp = None  # Clear OTP after successful reset
    db.commit()

    # Send confirmation email
    # try:
    # await send_password_reset_confirmation_email(user.email, user.first_name)
    # except Exception as email_error:
    #    system_logger.error(f"Failed to send password reset confirmation email: {email_error}")
    #    raise HTTPException(
    #        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #        detail="Failed to send password reset confirmation email.",
    #    ) from email_error

    system_logger.info("Password reset successfully for email: %s", payload.email)
    return {
        "message": "Password successfully reset. You can now log in with your new password."
    }


@router.get("/reset-password-link", summary="Redirect Reset Link to Frontend")
async def redirect_reset_link(
    request: Request, response: Response, db: Session = Depends(get_db)
):
    """
    Redirects the user to the frontend reset password page.

    - **Requires email and OTP in query parameters.**
    - **Stores OTP in an HTTP-only cookie to prevent abuse.**
    - **Frontend should extract these values and call `/submit-reset-password`.**
    """

    # Extract email and OTP from query parameters
    email = request.query_params.get("email")
    otp = request.query_params.get("otp")

    if not email or not otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and OTP are required in the reset link.",
        )

    # Retrieve user from DB
    user = db.query(User).filter(User.email == email, User.otp == otp).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid email or OTP."
        )

    # Check if OTP has expired
    if user.otp_created_at:
        otp_expiration_time = user.otp_created_at + timedelta(hours=24)
        if datetime.now(timezone.utc) > otp_expiration_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This password reset link has expired. Please request a new reset link.",
            )

    # ✅ Store OTP in an HTTP-only cookie for security
    response.set_cookie(
        key="password_reset_token",
        value=otp,
        httponly=True,  # Prevent JavaScript access
        secure=True,  # Enforce HTTPS
        max_age=86400,  # 24 hours expiration
        samesite="Lax",
    )

    # ✅ Redirect to frontend reset page
    # frontend_reset_url = (
    #     f"{settings.FRONTEND_BASE_ADDRESS}/reset-password?email={email}"
    # )
    # return RedirectResponse(url=frontend_reset_url)


@router.post("/submit-reset-password", summary="Submit New Password")
async def submit_reset_password(
    request: Request,
    payload: PasswordUpdateSchema,  # Replace with a validated schema
    db: Session = Depends(get_db),
):
    """
    Submits a new password after the user is redirected to the frontend.

    - **Ensures OTP cookie is present and matches stored OTP.**
    - **Updates password only if OTP is valid and unexpired.**
    """

    # Extract email from query parameters
    email = request.query_params.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required in the reset request.",
        )

    # Retrieve OTP from HTTP-only cookie
    otp_from_cookie = request.cookies.get("password_reset_token")
    if not otp_from_cookie:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized request. Missing OTP cookie.",
        )

    # Retrieve user from DB
    user = (
        db.query(User).filter(User.email == email, User.otp == otp_from_cookie).first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid email or OTP."
        )

    # Check if OTP has expired
    if user.otp_created_at:
        otp_expiration_time = user.otp_created_at + timedelta(hours=24)
        if datetime.now(timezone.utc) > otp_expiration_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This password reset link has expired. Please request a new reset link.",
            )

    # ✅ Update the user's password
    user.hashed_password = hash_password(payload.new_password)
    user.otp = None  # Clear OTP after successful reset
    user.otp_created_at = None
    db.commit()

    # Send confirmation email
    # await send_password_reset_confirmation_email(user.email, user.first_name)

    return {
        "message": "Password successfully reset. You can now log in with your new password."
    }


# User login route
@router.get(
    "/profile",
    response_model=UserProfileResponse,
    summary="Get User Profile Information",
)
async def get_user_profile(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Retrieve the profile information of the currently logged-in user.

    Combines data from the User model and the UserProfile model.
    """
    system_logger.info("Profile request for user: %s", current_user.email)

    # Fetch the user's profile from the UserProfile table
    user_profile = (
        db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    )
    system_logger.info("User profile found: %s", user_profile)

    if not user_profile:
        system_logger.error("User profile not found for user: %s", current_user.email)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found.",
        )

    # Construct the response using both User and UserProfile data
    user_data = UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        is_admin=current_user.is_admin,
        is_super_admin=current_user.is_super_admin,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        # Fields from UserProfile
        profile_picture=user_profile.profile_picture,
    )

    return user_data
