"""
Session Email Cache Module
- Stores and retrieves emails generated in the current session only
- Reuses emails generated today but not sent yet
- Does not persist cache across different days
- Uses in-memory storage for current session
"""
import os
import json
import glob
from datetime import datetime, date
from typing import Optional, Dict, List
from config import OUTPUT_DIR
from logger import logger

# In-memory cache for current session
_session_cache: Dict[str, dict] = {}
_current_session_date = None


def _get_cache_key(name: str, email: str, company: str, role: str) -> str:
    """Generate a unique cache key for a contact."""
    # Normalize inputs to avoid case sensitivity issues
    return f"{name.lower().strip()}|{email.lower().strip()}|{company.lower().strip()}|{role.lower().strip()}"


def _is_today(timestamp_str: str) -> bool:
    """Check if a timestamp is from today."""
    try:
        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return timestamp.date() == date.today()
    except (ValueError, AttributeError):
        return False


def _load_todays_results() -> Dict[str, dict]:
    """Load only today's generated emails from output files."""
    cache = {}
    
    if not os.path.exists(OUTPUT_DIR):
        return cache
    
    # Find all JSON result files from today
    today_str = date.today().strftime("%Y%m%d")
    json_pattern = os.path.join(OUTPUT_DIR, f"run_{today_str}_*.json")
    json_files = glob.glob(json_pattern)
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
            
            if isinstance(results, list):
                for result in results:
                    if all(key in result for key in ['name', 'email', 'company', 'role']):
                        # Only include results from today
                        if _is_today(result.get('timestamp', '')):
                            cache_key = _get_cache_key(
                                result['name'], 
                                result['email'], 
                                result['company'], 
                                result['role']
                            )
                            # Store the most recent result for each key
                            if cache_key not in cache or result.get('timestamp', '') > cache.get(cache_key, {}).get('timestamp', ''):
                                cache[cache_key] = result
                            
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Error loading today's results from {json_file}: {e}")
    
    if json_files:
        logger.info(f"Loaded {len(cache)} emails from today's {len(json_files)} result files")
    
    return cache


def _initialize_session_cache():
    """Initialize session cache with today's results."""
    global _session_cache, _current_session_date
    
    current_date = date.today()
    
    # Reset cache if it's a new day
    if _current_session_date != current_date:
        _session_cache.clear()
        _current_session_date = current_date
        logger.info("Starting new session cache for today")
    
    # Load today's existing results into session cache
    todays_results = _load_todays_results()
    _session_cache.update(todays_results)


def get_cached_email(name: str, email: str, company: str, role: str) -> Optional[dict]:
    """
    Retrieve an email generated today for the given contact.
    
    Returns:
        dict: Today's email result if found, None otherwise
    """
    _initialize_session_cache()
    
    cache_key = _get_cache_key(name, email, company, role)
    
    cached_result = _session_cache.get(cache_key)
    if cached_result:
        logger.info(f"Found today's email for {name} ({email}) at {company}")
        return cached_result
    
    return None


def add_to_session_cache(result: dict):
    """Add a newly generated email to the session cache."""
    _initialize_session_cache()
    
    if all(key in result for key in ['name', 'email', 'company', 'role']):
        cache_key = _get_cache_key(
            result['name'], 
            result['email'], 
            result['company'], 
            result['role']
        )
        _session_cache[cache_key] = result
        logger.info(f"Added to session cache: {result['name']} at {result['company']}")


def is_email_cached(name: str, email: str, company: str, role: str) -> bool:
    """Check if an email is cached for today for the given contact."""
    return get_cached_email(name, email, company, role) is not None


def get_cache_stats() -> Dict[str, int]:
    """Get statistics about today's email cache."""
    _initialize_session_cache()
    
    total_cached = len(_session_cache)
    sent_count = sum(1 for result in _session_cache.values() if result.get('sent', False))
    error_count = sum(1 for result in _session_cache.values() if 'error' in result)
    
    return {
        'total_cached': total_cached,
        'sent_count': sent_count,
        'error_count': error_count,
        'unsent_count': total_cached - sent_count - error_count
    }


def clear_session_cache():
    """Clear the current session cache."""
    global _session_cache
    _session_cache.clear()
    logger.info("Session cache cleared")


def print_cache_summary():
    """Print a summary of today's cached emails."""
    _initialize_session_cache()
    
    stats = get_cache_stats()
    
    print("\n" + "="*60)
    print("📧 TODAY'S EMAIL CACHE SUMMARY")
    print("="*60)
    print(f"Total emails today: {stats['total_cached']}")
    print(f"Successfully sent: {stats['sent_count']}")
    print(f"Not yet sent: {stats['unsent_count']}")
    print(f"Generation errors: {stats['error_count']}")
    
    if _session_cache:
        print("\nToday's emails:")
        for i, (cache_key, result) in enumerate(_session_cache.items(), 1):
            status = "✅ Sent" if result.get('sent') else ("❌ Error" if 'error' in result else "📝 Generated")
            timestamp = result.get('timestamp', '')[:19] if result.get('timestamp') else 'Unknown'
            print(f"  [{i}] {result.get('name', '?')} @ {result.get('company', '?')} - {status} ({timestamp})")
    else:
        print("\nNo emails generated today yet.")
    
    print("="*60)