"""
Orchestration Pipeline
Ties together: company research → profile retrieval → email generation → subject → referral → send → save
Now includes permanent email storage to reuse emails for the same contact/role/company combination.
"""
import os
import csv
from datetime import datetime
from profile_store import get_retriever, retrieve_context
from company_research import search_company
from chains import generate_cold_email, generate_subject_lines, generate_referral
from html_formatter import format_email_body
from sender import send_email, send_batch
from output_writer import save_results
from email_store import get_stored_email, store_email, update_email_status, print_storage_summary
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
    retriever=None,
    profile_path: str = None,
    use_stored: bool = True
) -> dict:
    """
    Full pipeline for one contact.
    Returns a result dict with all generated content.
    
    Args:
        use_stored: If True, check for and reuse permanently stored emails
        profile_path: Path to profile text file (defaults to profile.txt)
    """
    logger.info(f"--- Processing: {name} | {role} @ {company} ---")
    
    # Check permanent storage first if enabled
    if use_stored:
        stored_result = get_stored_email(name, email, company, role)
        if stored_result:
            logger.info(f"Using stored email for {name} ({email}) at {company}")
            # Update send status if needed
            if send and not stored_result.get('sent', False):
                logger.info("Sending stored email...")
                ok = send_email(
                    to=email, 
                    subject=stored_result['subject'], 
                    body=stored_result['html_body'], 
                    resume_path=stored_result.get('resume_path')
                )
                stored_result['sent'] = ok
                # Update the stored file with new send status
                update_email_status(name, email, company, role, ok)
            return stored_result

    # Step 1: Research company (optional)
    if ENABLE_COMPANY_SEARCH:
        logger.info(f"Researching {company}...")
        company_context = search_company(company, role)
    else:
        company_context = f"{company} is a technology company."
        logger.info("Company search disabled")

    # Step 2: Retrieve profile context
    if retriever is None:
        retriever = get_retriever(profile_path=profile_path)
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
        "company_context": company_context,  # Save for debugging
        "profile_path": profile_path or "profile.txt"
    }

    # Step 7: Send (use HTML body)
    if send:
        ok = send_email(to=email, subject=subject, body=html_body, resume_path=resume_path)
        result["sent"] = ok

    # Step 8: Store email permanently for future reuse
    if use_stored:
        store_email(result)

    return result


def run_batch_from_csv(
    csv_path: str,
    resume_path: str | None = None,
    send: bool = True,
    force_rebuild: bool = False,
    profile_path: str = None,
    use_stored: bool = True
) -> list[dict]:
    """
    Run pipeline for all rows in a CSV file.

    CSV columns (required): name, email, company, role
    CSV columns (optional): resume_path, relationship

    Args:
        use_stored: If True, reuse permanently stored emails
        profile_path: Path to profile text file

    Returns list of result dicts.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    logger.info(f"Loading batch from: {csv_path}")
    retriever = get_retriever(profile_path=profile_path, force_rebuild=force_rebuild)

    results = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    logger.info(f"Processing {len(rows)} contacts...")
    
    # Show storage summary if using stored emails
    if use_stored:
        print_storage_summary()

    for row in rows:
        try:
            result = run_single(
                name=row["Name"].strip(),
                email=row["Email"].strip(),
                company=row["Company"].strip(),
                role=row["role"].strip(),
                resume_path=row.get("resume_path", resume_path),
                relationship=row.get("relationship") or None,
                send=send,
                retriever=retriever,
                profile_path=profile_path,
                use_stored=use_stored
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


def generate_and_review_batch(
    csv_path: str,
    resume_path: str | None = None,
    force_rebuild: bool = False,
    profile_path: str = None,
    use_stored: bool = True
) -> list[dict]:
    """
    Generate emails for all CSV entries, save them, and return for review.
    Does NOT send emails - only generates and saves them.
    
    Args:
        use_stored: If True, reuse permanently stored emails
        profile_path: Path to profile text file
        
    Returns list of result dicts with generated emails.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    logger.info(f"Generating emails from: {csv_path}")
    retriever = get_retriever(profile_path=profile_path, force_rebuild=force_rebuild)

    results = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    logger.info(f"Generating emails for {len(rows)} contacts...")
    
    # Show storage summary if using stored emails
    if use_stored:
        print_storage_summary()

    stored_count = 0
    generated_count = 0

    for i, row in enumerate(rows, 1):
        try:
            # Check if email is already stored
            if use_stored and get_stored_email(row["Name"].strip(), row["Email"].strip(), 
                                             row["Company"].strip(), row["role"].strip()):
                logger.info(f"Using stored email {i}/{len(rows)}: {row['Name']} @ {row['Company']}")
                stored_count += 1
            else:
                logger.info(f"Generating email {i}/{len(rows)}: {row['Name']} @ {row['Company']}")
                generated_count += 1
                
            result = run_single(
                name=row["Name"].strip(),
                email=row["Email"].strip(),
                company=row["Company"].strip(),
                role=row["role"].strip(),
                resume_path=row.get("resume_path", resume_path),
                relationship=row.get("relationship") or None,
                send=False,  # Don't send, just generate
                retriever=retriever,
                profile_path=profile_path,
                use_stored=use_stored
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Failed to generate email for {row.get('Email', '?')}: {e}")
            results.append({
                "email": row.get("Email"),
                "company": row.get("Company"),
                "name": row.get("Name"),
                "role": row.get("role"),
                "error": str(e),
                "sent": False
            })

    # Save generated emails
    save_results(results)
    logger.info(f"Email generation complete: {stored_count} from storage, {generated_count} newly generated")
    return results


def send_generated_emails(results: list[dict]) -> dict:
    """
    Send previously generated emails from results list.
    Updates storage with send status.
    
    Args:
        results: List of result dicts with generated emails
        
    Returns:
        Dict with sending statistics: {sent: int, failed: int, total: int}
    """
    logger.info(f"Sending {len(results)} generated emails...")
    
    sent = 0
    failed = 0
    
    for i, result in enumerate(results, 1):
        if result.get("error"):
            logger.warning(f"Skipping {i}/{len(results)} due to generation error: {result.get('email')}")
            failed += 1
            continue
            
        logger.info(f"Sending {i}/{len(results)}: {result['email']}")
        
        success = send_email(
            to=result["email"],
            subject=result["subject"],
            body=result["html_body"],
            resume_path=result.get("resume_path")
        )
        
        result["sent"] = success
        
        # Update storage with send status
        if all(key in result for key in ['name', 'email', 'company', 'role']):
            update_email_status(
                result['name'], 
                result['email'], 
                result['company'], 
                result['role'], 
                success
            )
        
        if success:
            sent += 1
        else:
            failed += 1
    
    # Update saved results with send status
    save_results(results)
    
    stats = {"sent": sent, "failed": failed, "total": len(results)}
    logger.info(f"Batch sending complete: {sent} sent, {failed} failed, {len(results)} total")
    return stats


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
