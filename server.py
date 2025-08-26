"""
FastAPI server for email-based NDA tracked changes generation.
"""

import os
import smtplib
import tempfile
import traceback
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import aiofiles
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, EmailStr

from direct_tracked_changes import generate_direct_tracked_changes

app = FastAPI(title="NDA Tracked Changes API", version="1.0.0")

# Configuration from environment variables
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
FROM_ADDR = os.getenv("FROM_ADDR", SMTP_USER)
ALLOWED_DOMAIN = os.getenv("ALLOWED_DOMAIN")  # Optional domain restriction

class EmailRequest(BaseModel):
    sender: EmailStr
    subject: str = "NDA Review Request"

def is_allowed_sender(email: str) -> bool:
    """Check if sender is from allowed domain (if configured)."""
    if not ALLOWED_DOMAIN:
        return True  # No domain restriction
    return email.endswith(ALLOWED_DOMAIN)

def send_email_reply(to_email: str, subject: str, body: str, attachments: list = None):
    """Send email reply with tracked changes document."""
    if not all([SMTP_USER, SMTP_PASS, FROM_ADDR]):
        raise Exception("Email configuration incomplete. Check SMTP_USER, SMTP_PASS, FROM_ADDR in secrets.")
    
    msg = MIMEMultipart()
    msg['From'] = FROM_ADDR
    msg['To'] = to_email
    msg['Subject'] = f"Re: {subject}"
    
    # Add body
    msg.attach(MIMEText(body, 'plain'))
    
    # Add attachments
    if attachments:
        for filename, content in attachments:
            attachment = MIMEApplication(content, _subtype='vnd.openxmlformats-officedocument.wordprocessingml.document')
            attachment.add_header('Content-Disposition', f'attachment; filename={filename}')
            msg.attach(attachment)
    
    # Send email
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "NDA Tracked Changes API is running"}

@app.get("/health")
async def health():
    """Detailed health check."""
    config_status = {
        "smtp_configured": bool(SMTP_USER and SMTP_PASS),
        "from_address": bool(FROM_ADDR),
        "domain_restriction": ALLOWED_DOMAIN or "None"
    }
    return {"status": "healthy", "config": config_status}

@app.post("/webhook/email")
async def email_webhook(
    sender: str = Form(...),
    subject: str = Form(...),
    docx_file: UploadFile = File(...)
):
    """
    Webhook endpoint for processing email attachments.
    Expects form data with sender email, subject, and a DOCX file.
    """
    try:
        # Validate sender
        if not is_allowed_sender(sender):
            raise HTTPException(status_code=403, detail=f"Sender domain not allowed: {sender}")
        
        # Validate file type
        if not docx_file.filename.lower().endswith('.docx'):
            raise HTTPException(status_code=400, detail="Only DOCX files are supported")
        
        # Read file content
        file_content = await docx_file.read()
        
        # Process document
        tracked_docx, clean_docx, results = generate_direct_tracked_changes(file_content)
        
        if not tracked_docx:
            raise HTTPException(status_code=500, detail="Failed to generate tracked changes document")
        
        # Prepare email response
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        tracked_filename = f"NDA_TrackedChanges_{timestamp}.docx"
        clean_filename = f"NDA_CleanEdited_{timestamp}.docx"
        
        # Create email body
        body = f"""Hello,

Your NDA has been processed through our automated compliance review system.

Analysis Results:
- High Priority Issues: {results['high_priority']}
- Medium Priority Issues: {results['medium_priority']}
- Low Priority Issues: {results['low_priority']}
- Total Issues Found: {results['total_issues']}

{results['message']}

Attached Documents:
1. {tracked_filename} - Shows all suggested changes with track changes enabled
2. {clean_filename} - Clean version with all changes applied

Best regards,
AI Compliance Review System
Processed on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S')}"""
        
        # Send reply email
        attachments = [
            (tracked_filename, tracked_docx),
            (clean_filename, clean_docx)
        ]
        
        send_email_reply(sender, subject, body, attachments)
        
        return {
            "status": "success",
            "message": f"Processed NDA and sent reply to {sender}",
            "results": results
        }
        
    except Exception as e:
        error_msg = f"Error processing request: {str(e)}"
        print(f"Error: {error_msg}")
        print(traceback.format_exc())
        
        # Try to send error notification
        try:
            error_body = f"""Hello,

There was an error processing your NDA document:

{error_msg}

Please ensure:
1. The attachment is a valid DOCX file
2. The file is not corrupted or password protected
3. The file contains readable text content

Feel free to try again or contact support if the issue persists.

Best regards,
AI Compliance Review System"""
            
            send_email_reply(sender, subject, error_body)
        except:
            pass  # Don't fail the webhook if we can't send error email
        
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/test")
async def test_upload(
    file: UploadFile = File(...),
    email: Optional[str] = Form(None)
):
    """
    Test endpoint for local testing with curl.
    Upload a DOCX file and get the tracked changes response.
    """
    try:
        # Validate file type
        if not file.filename.lower().endswith('.docx'):
            raise HTTPException(status_code=400, detail="Only DOCX files are supported")
        
        # Read file content
        file_content = await file.read()
        
        # Process document
        tracked_docx, clean_docx, results = generate_direct_tracked_changes(file_content)
        
        if not tracked_docx:
            raise HTTPException(status_code=500, detail="Failed to generate tracked changes document")
        
        # For testing, save files to temp directory and return info
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        tracked_filename = f"test_tracked_{timestamp}.docx"
        clean_filename = f"test_clean_{timestamp}.docx"
        
        # Save files temporarily
        with open(f"/tmp/{tracked_filename}", "wb") as f:
            f.write(tracked_docx)
        with open(f"/tmp/{clean_filename}", "wb") as f:
            f.write(clean_docx)
        
        response = {
            "status": "success",
            "message": "Document processed successfully",
            "results": results,
            "files_saved": {
                "tracked_changes": f"/tmp/{tracked_filename}",
                "clean_edited": f"/tmp/{clean_filename}"
            }
        }
        
        if email:
            response["note"] = f"In production, this would be emailed to {email}"
        
        return response
        
    except Exception as e:
        error_msg = f"Error processing document: {str(e)}"
        print(f"Error: {error_msg}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_msg)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)