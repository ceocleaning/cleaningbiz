import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def test_email_connection():
    """Test email connection with detailed debugging"""
    
    # Use direct input for testing
    sender_email = "8bpcoins4u@gmail.com"  # Replace with your actual email
    sender_password = "xori gjys nikt qoyo"  # Replace with your actual password
    recipient_email = sender_email  # Send to yourself for testing
    
    print(f"Using email: {sender_email}")
    print(f"Password length: {len(sender_password)} characters")
    
    # Create a simple message
    msg = MIMEMultipart()
    msg['Subject'] = 'Test Email Connection'
    msg['From'] = sender_email
    msg['To'] = recipient_email
    
    body = """
    <html>
    <body>
        <h2>Test Email</h2>
        <p>This is a test email to verify SMTP connection.</p>
    </body>
    </html>
    """
    
    msg.attach(MIMEText(body, 'html'))
    
    try:
        print("Connecting to SMTP server...")
        smtp_server = smtplib.SMTP('smtp.gmail.com', 587)
        smtp_server.set_debuglevel(1)  # Enable verbose debug output
        
        print("Starting TLS...")
        smtp_server.starttls()
        
        print("Attempting login...")
        smtp_server.login(sender_email, sender_password)
        
        print("Sending email...")
        smtp_server.send_message(msg)
        
        print("Closing connection...")
        smtp_server.quit()
        
        print("Email sent successfully!")
        return True
    except Exception as e:
        print(f"Error: {e}")
        
        if "Username and Password not accepted" in str(e):
            print("\nGmail authentication failed. Please check:")
            print("1. Make sure you're using an App Password if 2-Step Verification is enabled")
            print("   - Go to your Google Account > Security > App passwords")
            print("   - Select 'Mail' as the app and 'Other' as the device")
            print("   - Generate and use the 16-character password")
            print("2. Verify the email and password in your .env file are correct")
            print("3. If you're not using 2-Step Verification:")
            print("   - Enable 'Less secure app access' in your Google Account")
            print("   - Note: Google is phasing this out, so App Passwords are recommended")
        
        return False

if __name__ == "__main__":
    test_email_connection()
