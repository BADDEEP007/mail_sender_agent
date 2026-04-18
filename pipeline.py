"""
Orchestration Pipeline
Ties together: company research → resume retrieval → email generation → subject → referral → send → save
"""
import os
import csv
from datetime import datetime
from resume_store import get_retriever, retrieve_context
from company_research import search_company
from chains import generate_cold_email, generate_subject_lines, generate_referral
from html_formatter import format_email_body
from sender import send_email, send_batch
from output_writer import save_results
from config import DRY_RUN, ENABLE_COMPANY_SEARCH
from logger import logger


def run_single(
    name: str,
    email: str,
    company: str,
    role: str,
    resume_path: str | None = None,
    relationship: str | None = None,   # stranger | alumni | mutual
    send: bool = True,
    retriever=None
) -> dict:
    """
    Full pipeline for one contact.
    Returns a result dict with all generated content.
    """
    logger.info(f"--- Processing: {name} | {role} @ {company} ---")

    # Step 1: Research company (optional)
    if ENABLE_COMPANY_SEARCH:
        logger.info(f"Researching {company}...")
        company_context = search_company(company, role)
    else:
        company_context = f"{company} is a technology company."
        logger.info("Company search disabled")

    # Step 2: Retrieve resume context
    if retriever is None:
        retriever = get_retriever()
    context = retrieve_context(role, company, retriever)

    # Step 3: Generate cold email body
    body = generate_cold_email(name, role, company, company_context, context)

    # Step 4: Generate subject lines (pick best = first)
    subjects = generate_subject_lines(name, role, company)
    subject = subjects[0] if subjects else f"{role} Applicant | {name}"

    # Step 5: Optionally generate referral message
    referral_msg = None
    if relationship:
        referral_msg = generate_referral(name, role, company, relationship)
    
    # Step 6: Format email body as HTML with signature
    html_body = format_email_body(body)
   
    result = {
        "timestamp": datetime.now().isoformat(),
        "name": name,
        "email": email,
        "company": company,
        "role": role,
        "subject": subject,
        "subject_alternatives": subjects[1:],
        "body": body,  # Keep plain text for output files
        "html_body": html_body,  # HTML version for sending
        "referral": referral_msg,
        "resume_path": resume_path,
        "sent": False,
        "dry_run": DRY_RUN,
        "company_context": company_context  # Save for debugging
    }

    # Step 7: Send (use HTML body)
    if send:
        ok = send_email(to=email, subject=subject, body=html_body, resume_path=resume_path)
        result["sent"] = ok

    return result


def run_batch_from_csv(
    csv_path: str,
    resume_path: str | None = None,
    send: bool = True,
    force_rebuild: bool = False
) -> list[dict]:
    """
    Run pipeline for all rows in a CSV file.

    CSV columns (required): name, email, company, role
    CSV columns (optional): resume_path, relationship

    Returns list of result dicts.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    logger.info(f"Loading batch from: {csv_path}")
    retriever = get_retriever(force_rebuild=force_rebuild)

    results = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    logger.info(f"Processing {len(rows)} contacts...")

    for row in rows:
        try:
            result = run_single(
                name=row["name"].strip(),
                email=row["email"].strip(),
                company=row["company"].strip(),
                role=row["role"].strip(),
                resume_path=row.get("resume_path", resume_path),
                relationship=row.get("relationship") or None,
                send=send,
                retriever=retriever
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Failed for {row.get('email', '?')}: {e}")
            results.append({
                "email": row.get("email"),
                "company": row.get("company"),
                "error": str(e),
                "sent": False
            })

    save_results(results)
    return results


def run_batch_from_list(
    contacts: list[dict],
    resume_path: str | None = None,
    send: bool = True,
    force_rebuild: bool = False
) -> list[dict]:
    """
    Run pipeline for a list of contact dicts.
    Each dict: { name, email, company, role, resume_path?, relationship? }
    """
    retriever = get_retriever(force_rebuild=force_rebuild)
    results = []

    for contact in contacts:
        try:
            result = run_single(
                name=contact["name"],
                email=contact["email"],
                company=contact["company"],
                role=contact["role"],
                resume_path=contact.get("resume_path", resume_path),
                relationship=contact.get("relationship"),
                send=send,
                retriever=retriever
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Failed for {contact.get('email', '?')}: {e}")
            results.append({**contact, "error": str(e), "sent": False})

    save_results(results)
    return results
