import logging
import os

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema

from src.mastercard_solution_tech_stack_agent.config.appconfig import env_config

# Initialize logger
logger = logging.getLogger(__name__)

# Email configuration from environment variables using SendGrid
conf = ConnectionConfig(
    MAIL_USERNAME=env_config.mail_username,  # SendGrid requires 'apikey' as the username
    MAIL_PASSWORD=env_config.sendgrid_api_key,  # Your SendGrid API key
    MAIL_FROM=env_config.email_from,  # Sender email address
    MAIL_FROM_NAME=env_config.email_from_name,  # Sender name
    MAIL_PORT=env_config.mail_port,  # Port 587 for TLS
    MAIL_SERVER=env_config.mail_server,  # SendGrid's SMTP server
    MAIL_STARTTLS=True,  # Enable STARTTLS
    MAIL_SSL_TLS=False,  # No need to use SSL if STARTTLS is enabled
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,  # Set to True to validate certificates in production
)


# Generalized email sender function
async def send_email(subject: str, recipients: list, body: str, subtype: str = "html"):
    """
    Send an email with the specified subject, recipients, and body.

    Args:
        subject (str): The email subject.
        recipients (list): List of recipient email addresses.
        body (str): The email body content.
        subtype (str): The email content type (default: 'html').

    Returns:
        None: Sends the email asynchronously.
    """
    message = MessageSchema(
        subject=subject, recipients=recipients, body=body, subtype=subtype
    )
    fm = FastMail(conf)
    try:
        await fm.send_message(message)
        logger.info(f"Email sent successfully to {recipients}.")
    except Exception as e:
        logger.error(f"Failed to send email to {recipients}: {e}")
        raise


# Helper functions for specific email types
async def send_verification_email(email: str, first_name: str, otp: str):
    verification_url = (
        f"{os.environ.get('SERVER_BASE_ADDRESS')}/users/verify?email={email}&otp={otp}"
    )
    body = f"""
    <p>Dear {first_name},</p>
    <p>Welcome to DataGlobal Hub!</p>
    <p>You can verify your account by clicking <a href="{verification_url}">here</a>.</p>
    <p>Best regards,<br>The DataGlobal Hub Team</p>
    """
    await send_email("Your Verification Code", [email], body)


async def send_confirmation_email(email: str, first_name: str):
    body = f"""
    <p>Dear {first_name},</p>
    <p>Welcome to DataGlobal Hub!</p>
    <p>Congratulations! Your account has been successfully created.</p>
    <p>Best regards,<br>The DataGlobal Hub Team</p>
    """
    await send_email("Account Successfully Created", [email], body)


async def send_password_reset_email(email: str, first_name: str, otp: str):
    reset_link = f"{os.environ.get('SERVER_BASE_ADDRESS')}/users/reset-password-link?email={email}&otp={otp}"
    body = f"""
    <p>Dear {first_name},</p>
    <p>A request has been received to reset your password at DataGlobal Hub.</p>
    <p>Your OTP is <strong>{otp}</strong>.</p>
    <p>You can reset your password by clicking <a href="{reset_link}">here</a>.</p>
    <p>If you did not request this, please ignore this email.</p>
    <p>Best regards,<br>The DataGlobal Hub Team</p>
    """
    await send_email("Password Reset Request", [email], body)


async def send_password_reset_confirmation_email(email: str, first_name: str):
    body = f"""
    <p>Dear {first_name},</p>
    <p>Your password has been successfully reset for your account at DataGlobal Hub.</p>
    <p>If you did not request this change, please contact our support team immediately.</p>
    <p>Best regards,<br>The DataGlobal Hub Team</p>
    """
    await send_email("Password Reset Successful", [email], body)


async def send_account_deletion_verification_email(
    email: str, first_name: str, otp: str
):
    verification_url = f"{os.environ.get('SERVER_BASE_ADDRESS')}/auth/confirm-account-deletion?email={email}&otp={otp}"
    body = f"""
    <p>Dear {first_name},</p>
    <p>You have requested to delete your account at DataGlobal Hub.</p>
    <p>Your OTP is <strong>{otp}</strong>.</p>
    <p>You can confirm the deletion by clicking <a href="{verification_url}">here</a>.</p>
    <p>If you did not request this, please ignore this email.</p>
    <p>Best regards,<br>The DataGlobal Hub Team</p>
    """
    await send_email("Your Account Deletion OTP", [email], body)


async def send_account_deletion_confirmation_email(email: str, first_name: str):
    body = f"""
    <p>Dear {first_name},</p>
    <p>Your account at DataGlobal Hub has been successfully deleted.</p>
    <p>We are sorry to see you go. If this was a mistake, please contact our support team immediately.</p>
    <p>Best regards,<br>The DataGlobal Hub Team</p>
    """
    await send_email("Account Deleted Successfully", [email], body)


async def notify_author_of_deletion(article, deleter_email: str):
    body = f"""
    <p>Dear {article.author_name},</p>
    <p>This is to inform you that your article titled "<strong>{article.title}</strong>"
    has been deleted by an admin.</p>
    <p>If you have any questions or concerns, please reach out to our support team.</p>
    <p>Best regards,<br>The DataGlobal Hub Team</p>
    """
    await send_email("Your Article Has Been Deleted", [article.author.email], body)
