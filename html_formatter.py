"""
HTML Email Formatter
Converts plain text email body to styled HTML with signature
"""
import re
from config import EMAIL_USER


def format_signature() -> str:
    """Professional HTML signature with contact details."""
    return """
<br>
<p style="margin:0;color:#222;">Warm regards,</p>
<p style="margin:4px 0 0 0;"><strong>Pradeep Argal</strong></p>
<p style="margin:2px 0;font-size:13px;color:#555;">
  +91 8962093654 &nbsp;|&nbsp;
  <a href="mailto:pradeepargal22@gmail.com" style="color:#1a73e8;">pradeepargal22@gmail.com</a>
</p>
<p style="margin:2px 0;font-size:13px;">
  <a href="https://linkedin.com/in/pradeep-argal" style="color:#1a73e8;">linkedin.com/in/pradeep-argal</a>
  &nbsp;|&nbsp;
  <a href="https://github.com/BADDEEP007" style="color:#1a73e8;">github.com/BADDEEP007</a>
</p>
"""


def wrap_html(body: str) -> str:
    """
    Wrap email body in clean HTML template with styling.
    
    Args:
        body: Plain text or lightly formatted email body
    
    Returns:
        Full HTML email with styling and signature
    """
    # Convert plain text paragraphs to <p> tags if not already HTML
    if not body.strip().startswith('<'):
        # Split by double newlines (paragraphs)
        paragraphs = body.split('\n\n')
        formatted_paragraphs = []
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # Check if it's a list (lines starting with - or *)
            if para.startswith('-') or para.startswith('*'):
                items = [line.strip().lstrip('-*').strip() for line in para.split('\n') if line.strip()]
                list_html = '<ul style="margin:8px 0;padding-left:20px;">'
                for item in items:
                    list_html += f'<li style="margin:4px 0;">{item}</li>'
                list_html += '</ul>'
                formatted_paragraphs.append(list_html)
            else:
                # Regular paragraph - preserve single line breaks within it
                para_html = para.replace('\n', '<br>')
                formatted_paragraphs.append(f'<p style="margin:8px 0;">{para_html}</p>')
        
        body_html = '\n'.join(formatted_paragraphs)
    else:
        # Already HTML, use as-is
        body_html = body
    
    # Add signature
    full_body = body_html + format_signature()
    
    # Wrap in HTML template
    return f"""
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.6;max-width:1000px;margin:0 auto;padding:20px;background-color:#ffffff;">
{full_body}
</body>
</html>
"""


def format_email_body(plain_body: str) -> str:
    """
    Main function to convert plain text email to HTML.
    Handles both plain text and already-formatted text.
    
    Args:
        plain_body: Email body from LLM (plain text or light formatting)
    
    Returns:
        HTML-formatted email ready to send
    """
    return wrap_html(plain_body)


def format_referral_body(plain_referral: str) -> str:
    """
    Format referral message as HTML (simpler, no signature).
    
    Args:
        plain_referral: Referral message text
    
    Returns:
        HTML-formatted referral message
    """
    if not plain_referral.strip().startswith('<'):
        paragraphs = plain_referral.split('\n\n')
        formatted = []
        for para in paragraphs:
            para = para.strip()
            if para:
                para_html = para.replace('\n', '<br>')
                formatted.append(f'<p style="margin:8px 0;">{para_html}</p>')
        body_html = '\n'.join(formatted)
    else:
        body_html = plain_referral
    
    return f"""
<html>
<body style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.6;max-width:800px;margin:0 auto;padding:20px;">
{body_html}
</body>
</html>
"""
