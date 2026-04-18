"""
Email Sender Module
- SMTP with Gmail
- Attaches resume PDF
- Retry logic + rate limiting
- Dry-run support
"""
import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from config import EMAIL_USER, EMAIL_PASSWORD, SMTP_SERVER, SMTP_PORT, DRY_RUN, EMAIL_RATE_LIMIT, EMAIL_MAX_RETRY
from logger import logger


def _build_message(to: str, subject: str, body: str, resume_path: str | None) -> MIMEMultipart:
    msg = MIMEMultipart()
    msg["From"] = EMAIL_USER
    msg["To"] = to
    msg["Subject"] = subject
    
    # Attach body as HTML (not plain text)
    msg.attach(MIMEText(body, "html"))

    if resume_path and os.path.exists(resume_path):
        with open(resume_path, "rb") as f:
            part = MIMEBase("application", "pdf")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            filename = os.path.basename(resume_path)
            part.add_header("Content-Disposition", f"attachment; filename={filename}")
            msg.attach(part)
        logger.info(f"Attached resume: {filename}")
    elif resume_path:
        logger.warning(f"Resume not found, skipping attachment: {resume_path}")

    return msg


def send_email(to: str, subject: str, body: str, resume_path: str | None = None) -> bool:
    """Send a single email. Returns True on success."""
    if DRY_RUN:
        logger.info(f"[DRY RUN] Would send to: {to} | Subject: {subject}")
        logger.info(f"[DRY RUN] Body preview: {body[:120]}...")
        return True

    msg = _build_message(to, subject, body, resume_path)

    for attempt in range(1, EMAIL_MAX_RETRY + 1):
        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(EMAIL_USER, EMAIL_PASSWORD)
                server.sendmail(EMAIL_USER, to, msg.as_string())
            logger.info(f"Email sent to {to}")
            return True
        except Exception as e:
            logger.warning(f"Attempt {attempt}/{EMAIL_MAX_RETRY} failed for {to}: {e}")
            if attempt < EMAIL_MAX_RETRY:
                time.sleep(2 ** attempt)  # exponential backoff

    logger.error(f"All {EMAIL_MAX_RETRY} attempts failed for {to}")
    return False


def send_batch(records: list[dict]) -> dict:
    """
    Send emails for a list of records.
    Each record: { to, subject, body, resume_path (optional) }
    Returns { sent: int, failed: int, results: list }
    """
    results = []
    sent = failed = 0

    for i, rec in enumerate(records):
        logger.info(f"Sending {i+1}/{len(records)}: {rec['to']}")
        ok = send_email(
            to=rec["to"],
            subject=rec["subject"],
            body=rec["body"],
            resume_path=rec.get("resume_path")
        )
        results.append({"to": rec["to"], "success": ok})
        if ok:
            sent += 1
        else:
            failed += 1

        if i < len(records) - 1:
            time.sleep(EMAIL_RATE_LIMIT)

    logger.info(f"Batch complete — sent: {sent}, failed: {failed}")
    return {"sent": sent, "failed": failed, "results": results}
