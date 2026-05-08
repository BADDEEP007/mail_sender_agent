"""
Permanent Email Storage Module
- Stores generated emails permanently in a dedicated folder
- Reuses emails for the same contact/role/company combination
- Organizes emails by contact for easy management
"""
import os
import json
import hashlib
from datetime import datetime
from typing import Optional, Dict, List
from config import OUTPUT_DIR
from logger import logger

# Permanent email storage directory
EMAIL_STORE_DIR = os.path.join(os.path.dirname(__file__), "email_store")


def _get_contact_hash(name: str, email: str, company: str, role: str) -> str:
    """Generate a unique hash for a contact."""
    # Create a unique identifier for this contact/role/company combination
    contact_string = f"{name.lower().strip()}|{email.lower().strip()}|{company.lower().strip()}|{role.lower().strip()}"
    return hashlib.md5(contact_string.encode()).hexdigest()[:12]


def _get_email_file_path(name: str, email: str, company: str, role: str) -> str:
    """Get the file path for storing this contact's email."""
    contact_hash = _get_contact_hash(name, email, company, role)
    # Create a readable filename
    safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_company = "".join(c for c in company if c.isalnum() or c in (' ', '-', '_')).strip()
    filename = f"{safe_name}_{safe_company}_{contact_hash}.json"
    return os.path.join(EMAIL_STORE_DIR, filename)


def _ensure_store_directory():
    """Ensure the email store directory exists."""
    os.makedirs(EMAIL_STORE_DIR, exist_ok=True)


def store_email(result: dict) -> str:
    """
    Store a generated email permanently.
    
    Args:
        result: Email result dictionary with name, email, company, role, etc.
        
    Returns:
        str: Path to the stored email file
    """
    _ensure_store_directory()
    
    if not all(key in result for key in ['name', 'email', 'company', 'role']):
        raise ValueError("Result must contain name, email, company, and role")
    
    file_path = _get_email_file_path(
        result['name'], 
        result['email'], 
        result['company'], 
        result['role']
    )
    
    # Add storage metadata
    storage_data = {
        **result,
        'stored_at': datetime.now().isoformat(),
        'contact_hash': _get_contact_hash(result['name'], result['email'], result['company'], result['role'])
    }
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(storage_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Stored email for {result['name']} at {result['company']} -> {file_path}")
    return file_path


def get_stored_email(name: str, email: str, company: str, role: str) -> Optional[dict]:
    """
    Retrieve a stored email for the given contact.
    
    Returns:
        dict: Stored email result if found, None otherwise
    """
    _ensure_store_directory()
    
    file_path = _get_email_file_path(name, email, company, role)
    
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                stored_data = json.load(f)
            
            logger.info(f"Found stored email for {name} ({email}) at {company}")
            return stored_data
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Error reading stored email {file_path}: {e}")
            return None
    
    return None


def is_email_stored(name: str, email: str, company: str, role: str) -> bool:
    """Check if an email is stored for the given contact."""
    return get_stored_email(name, email, company, role) is not None


def update_email_status(name: str, email: str, company: str, role: str, sent: bool) -> bool:
    """
    Update the sent status of a stored email.
    
    Returns:
        bool: True if update was successful, False otherwise
    """
    stored_email = get_stored_email(name, email, company, role)
    if stored_email:
        stored_email['sent'] = sent
        stored_email['last_updated'] = datetime.now().isoformat()
        
        file_path = _get_email_file_path(name, email, company, role)
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(stored_email, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Updated sent status for {name} at {company}: {sent}")
            return True
        except IOError as e:
            logger.error(f"Error updating stored email {file_path}: {e}")
            return False
    
    return False


def list_stored_emails() -> List[dict]:
    """
    List all stored emails with basic information.
    
    Returns:
        List of dicts with email metadata
    """
    _ensure_store_directory()
    
    stored_emails = []
    
    if not os.path.exists(EMAIL_STORE_DIR):
        return stored_emails
    
    for filename in os.listdir(EMAIL_STORE_DIR):
        if filename.endswith('.json'):
            file_path = os.path.join(EMAIL_STORE_DIR, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    email_data = json.load(f)
                
                # Extract key information
                stored_emails.append({
                    'name': email_data.get('name', 'Unknown'),
                    'email': email_data.get('email', 'Unknown'),
                    'company': email_data.get('company', 'Unknown'),
                    'role': email_data.get('role', 'Unknown'),
                    'subject': email_data.get('subject', 'No Subject'),
                    'sent': email_data.get('sent', False),
                    'stored_at': email_data.get('stored_at', 'Unknown'),
                    'file_path': file_path
                })
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Error reading stored email {file_path}: {e}")
    
    # Sort by stored_at date (newest first)
    stored_emails.sort(key=lambda x: x.get('stored_at', ''), reverse=True)
    return stored_emails


def get_storage_stats() -> Dict[str, int]:
    """Get statistics about stored emails."""
    stored_emails = list_stored_emails()
    
    total_stored = len(stored_emails)
    sent_count = sum(1 for email in stored_emails if email.get('sent', False))
    unsent_count = total_stored - sent_count
    
    return {
        'total_stored': total_stored,
        'sent_count': sent_count,
        'unsent_count': unsent_count
    }


def delete_stored_email(name: str, email: str, company: str, role: str) -> bool:
    """
    Delete a stored email.
    
    Returns:
        bool: True if deletion was successful, False otherwise
    """
    file_path = _get_email_file_path(name, email, company, role)
    
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info(f"Deleted stored email for {name} at {company}")
            return True
        except OSError as e:
            logger.error(f"Error deleting stored email {file_path}: {e}")
            return False
    
    return False


def print_storage_summary():
    """Print a summary of stored emails."""
    stats = get_storage_stats()
    stored_emails = list_stored_emails()
    
    print("\n" + "="*70)
    print("📁 PERMANENT EMAIL STORAGE SUMMARY")
    print("="*70)
    print(f"Total stored emails: {stats['total_stored']}")
    print(f"Successfully sent: {stats['sent_count']}")
    print(f"Not yet sent: {stats['unsent_count']}")
    print(f"Storage location: {EMAIL_STORE_DIR}")
    
    if stored_emails:
        print("\nStored emails:")
        for i, email in enumerate(stored_emails[:10], 1):  # Show first 10
            status = "✅ Sent" if email.get('sent') else "📝 Stored"
            stored_date = email.get('stored_at', '')[:10] if email.get('stored_at') else 'Unknown'
            print(f"  [{i:2d}] {status} | {email.get('name', '?'):20} @ {email.get('company', '?'):15} | {stored_date}")
        
        if len(stored_emails) > 10:
            print(f"  ... and {len(stored_emails) - 10} more emails")
    else:
        print("\nNo emails stored yet.")
    
    print("="*70)