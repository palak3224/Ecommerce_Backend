import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app, render_template_string

def send_email(to_email, subject, template_str, context):
    """
    Send an email using SMTP.
    
    Args:
        to_email (str): Recipient email address
        subject (str): Email subject
        template_str (str): Email template as a string
        context (dict): Variables to render in the template
    
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        current_app.logger.info(f"Attempting to send email to {to_email}")
        
        # Ensure context is a dictionary
        if not isinstance(context, dict):
            context = dict(context)
        
        # Render the template with the provided context
        html_content = render_template_string(template_str, **context)
        
        # Create message
        message = MIMEMultipart('alternative')
        message['Subject'] = subject
        
        # Handle MAIL_DEFAULT_SENDER properly (might be tuple or string)
        sender = current_app.config['MAIL_DEFAULT_SENDER']
        if isinstance(sender, tuple):
            sender_name, sender_email = sender
            message['From'] = f"{sender_name} <{sender_email}>"
            sender_address = sender_email  # Use just the email for SMTP sendmail
        else:
            message['From'] = sender
            sender_address = sender  # Use the full string for SMTP sendmail
            
        message['To'] = to_email
        
        # Add HTML content
        message.attach(MIMEText(html_content, 'html', 'utf-8'))
        
        # Log SMTP configuration
        current_app.logger.info(f"SMTP Configuration: Server={current_app.config['MAIL_SERVER']}, Port={current_app.config['MAIL_PORT']}, TLS={current_app.config['MAIL_USE_TLS']}")
        
        # Connect to SMTP server
        with smtplib.SMTP(current_app.config['MAIL_SERVER'], current_app.config['MAIL_PORT']) as server:
            # Use TLS if configured
            if current_app.config['MAIL_USE_TLS']:
                current_app.logger.info("Starting TLS connection")
                server.starttls()
            
            # Login if credentials are provided
            if current_app.config['MAIL_USERNAME'] and current_app.config['MAIL_PASSWORD']:
                current_app.logger.info(f"Logging in with username: {current_app.config['MAIL_USERNAME']}")
                server.login(current_app.config['MAIL_USERNAME'], current_app.config['MAIL_PASSWORD'])
            
            # Send email
            current_app.logger.info("Sending email...")
            server.sendmail(
                sender_address,  # Use the properly formatted sender address
                to_email,
                message.as_string()
            )
            current_app.logger.info("Email sent successfully")
        
        return True
    
    except Exception as e:
        current_app.logger.error(f"Failed to send email: {str(e)}")
        return False


def send_verification_email(user, token):
    """
    Send email verification email.
    
    Args:
        user (User): User object
        token (str): Verification token
    
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    # Generate verification link
    verification_link = f"{current_app.config['FRONTEND_URL']}/verify-email/{token}"
    
    # Email template
    template = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background-color: #f8f8f8; padding: 20px; text-align: center; }
            .content { padding: 20px; }
            .button { display: inline-block; background-color: #4CAF50; color: white; padding: 10px 20px; 
                      text-decoration: none; border-radius: 5px; }
            .footer { font-size: 12px; color: #777; text-align: center; margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Email Verification</h2>
            </div>
            <div class="content">
                <p>Hello {{ name }},</p>
                <p>Thank you for registering with us. Please click the button below to verify your email address:</p>
                <p style="text-align: center;">
                    <a href="{{ verification_link }}" class="button">Verify Email</a>
                </p>
                <p>Or copy and paste this link in your browser:</p>
                <p>{{ verification_link }}</p>
                <p>This link will expire in 24 hours.</p>
                <p>If you did not register for an account, please ignore this email.</p>
                <p>Best regards,<br>The Team</p>
            </div>
            <div class="footer">
                This is an automated message, please do not reply to this email.
            </div>
        </div>
    </body>
    </html>
    """
    
    # Context for template rendering
    context = {
        'name': f"{user.first_name} {user.last_name}",
        'verification_link': verification_link
    }
    
    return send_email(
        user.email,
        "Verify Your Email Address",
        template,
        context
    )


def send_password_reset_email(user, token):
    """
    Send password reset email.
    
    Args:
        user (User): User object
        token (str): Password reset token
    
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    # Generate reset link with token
    reset_link = f"{current_app.config['FRONTEND_URL']}/password/reset?token={token}"
    
    # Email template
    template = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                line-height: 1.6; 
                color: #333;
                margin: 0;
                padding: 0;
                background-color: #f5f5f5;
            }
            .container { 
                max-width: 600px; 
                margin: 20px auto; 
                padding: 20px;
                background-color: #ffffff;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .header { 
                background-color: #4CAF50;
                padding: 20px; 
                text-align: center;
                border-radius: 8px 8px 0 0;
                color: white;
            }
            .content { 
                padding: 20px;
                color: #333;
            }
            .button { 
                display: inline-block; 
                background-color: #4CAF50; 
                color: white; 
                padding: 12px 24px; 
                text-decoration: none; 
                border-radius: 5px;
                font-weight: bold;
                margin: 20px 0;
            }
            .button:hover {
                background-color: #45a049;
            }
            .footer { 
                font-size: 12px; 
                color: #777; 
                text-align: center; 
                margin-top: 20px;
                padding-top: 20px;
                border-top: 1px solid #eee;
            }
            .link {
                word-break: break-all;
                color: #4CAF50;
                text-decoration: none;
            }
            .link:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Password Reset Request</h2>
            </div>
            <div class="content">
                <p>Hello {{ name }},</p>
                <p>We received a request to reset your password. Click the button below to create a new password:</p>
                <p style="text-align: center;">
                    <a href="{{ reset_link }}" class="button">Reset Password</a>
                </p>
                <p>Or copy and paste this link in your browser:</p>
                <p><a href="{{ reset_link }}" class="link">{{ reset_link }}</a></p>
                <p><strong>Important:</strong> This link will expire in 1 hour.</p>
                <p>If you did not request a password reset, please ignore this email.</p>
                <p>Best regards,<br>The Team</p>
            </div>
            <div class="footer">
                This is an automated message, please do not reply to this email.
            </div>
        </div>
    </body>
    </html>
    """
    
    # Context for template rendering
    context = {
        'name': f"{user.first_name} {user.last_name}",
        'reset_link': reset_link
    }
    
    return send_email(
        user.email,
        "Reset Your Password",
        template,
        context
    )