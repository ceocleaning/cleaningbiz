from leadsAutomation.utils import send_email

def send_welcome_email_task(email, first_name, username):
    subject = "Welcome to CleaningBiz AI - Your Video Tutorial Inside!"
    from_email = "CleaningBiz AI <support@cleaningbizai.com>"
    to_email = [email]
    
    name = first_name if first_name else username
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #4361ee;">Welcome to CleaningBiz AI!</h2>
        <p>Hi {{name}},</p>
        <p>We're thrilled to have you onboard.</p>
        <p>To help you get started and ensure your success with our platform, we've prepared a comprehensive guided demo video.</p>
        
        <p>This video tutorial will walk you through setting up CleaningBiz AI for your business operations:</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="https://vimeo.com/1120738531?share=copy&fl=sv&fe=ci" style="background-color: #4361ee; color: white; padding: 12px 24px; text-decoration: none; border-radius: 50px; font-weight: bold; display: inline-block;">Watch the Setup Tutorial</a>
        </div>
        
        <p>If you have any questions along the way, simply reply to this email. We're here to help!</p>
        
        <p>Best regards,<br><strong>The CleaningBiz AI Team</strong></p>
    </div>
    """
    
    try:
        send_email(
            from_email=from_email,
            to_email=to_email,
            subject=subject,
            html_content=html_content
        )
    except Exception as e:
        print(f"Error sending welcome email to {{email}}: {{str(e)}}")
