"""
Email Validation Module
- Validates email format and deliverability
- Checks if emails exist and can receive messages
- Removes invalid emails from CSV files
- Supports batch validation with progress tracking
"""
import re
import csv
import os
import socket
import smtplib
import dns.resolver
from typing import List, Dict, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from logger import logger


class EmailValidator:
    """Email validation with format, domain, and SMTP checks."""
    
    def __init__(self, timeout: int = 10, max_workers: int = 5):
        """
        Initialize email validator.
        
        Args:
            timeout: Timeout for network operations in seconds
            max_workers: Maximum concurrent validation threads
        """
        self.timeout = timeout
        self.max_workers = max_workers
        self.email_regex = re.compile(
            r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        )
    
    def validate_format(self, email: str) -> bool:
        """
        Validate email format using regex.
        
        Args:
            email: Email address to validate
            
        Returns:
            bool: True if format is valid
        """
        if not email or not isinstance(email, str):
            return False
        
        email = email.strip().lower()
        return bool(self.email_regex.match(email))
    
    def validate_domain(self, email: str) -> bool:
        """
        Validate email domain by checking MX records.
        
        Args:
            email: Email address to validate
            
        Returns:
            bool: True if domain has valid MX records
        """
        try:
            domain = email.split('@')[1]
            mx_records = dns.resolver.resolve(domain, 'MX')
            return len(mx_records) > 0
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, 
                dns.resolver.Timeout, IndexError, Exception):
            return False
    
    def validate_smtp(self, email: str) -> Tuple[bool, str]:
        """
        Validate email deliverability using SMTP.
        
        Args:
            email: Email address to validate
            
        Returns:
            Tuple[bool, str]: (is_valid, status_message)
        """
        try:
            domain = email.split('@')[1]
            
            # Get MX record
            try:
                mx_records = dns.resolver.resolve(domain, 'MX')
                mx_record = str(mx_records[0].exchange)
            except:
                return False, "No MX record found"
            
            # Connect to SMTP server
            with smtplib.SMTP(timeout=self.timeout) as server:
                server.connect(mx_record, 25)
                server.helo('localhost')
                server.mail('test@example.com')
                
                # Try to validate the recipient
                code, message = server.rcpt(email)
                
                if code == 250:
                    return True, "Valid"
                elif code == 550:
                    return False, "Mailbox not found"
                elif code == 553:
                    return False, "Invalid address"
                else:
                    return False, f"SMTP error: {code} {message.decode()}"
                    
        except smtplib.SMTPConnectError:
            return False, "Cannot connect to mail server"
        except smtplib.SMTPServerDisconnected:
            return False, "Mail server disconnected"
        except socket.timeout:
            return False, "Connection timeout"
        except Exception as e:
            return False, f"SMTP validation error: {str(e)}"
    
    def validate_email(self, email: str, check_smtp: bool = True) -> Dict[str, any]:
        """
        Comprehensive email validation.
        
        Args:
            email: Email address to validate
            check_smtp: Whether to perform SMTP validation
            
        Returns:
            Dict with validation results
        """
        result = {
            'email': email,
            'valid': False,
            'format_valid': False,
            'domain_valid': False,
            'smtp_valid': False,
            'smtp_message': '',
            'error': None
        }
        
        try:
            # Format validation
            result['format_valid'] = self.validate_format(email)
            if not result['format_valid']:
                result['error'] = "Invalid email format"
                return result
            
            # Domain validation
            result['domain_valid'] = self.validate_domain(email)
            if not result['domain_valid']:
                result['error'] = "Invalid domain or no MX record"
                return result
            
            # SMTP validation (optional)
            if check_smtp:
                smtp_valid, smtp_message = self.validate_smtp(email)
                result['smtp_valid'] = smtp_valid
                result['smtp_message'] = smtp_message
                
                if not smtp_valid:
                    result['error'] = smtp_message
                    return result
            else:
                result['smtp_valid'] = True  # Skip SMTP check
            
            # All validations passed
            result['valid'] = True
            
        except Exception as e:
            result['error'] = f"Validation error: {str(e)}"
            logger.error(f"Email validation failed for {email}: {e}")
        
        return result
    
    def validate_batch(self, emails: List[str], check_smtp: bool = True) -> List[Dict[str, any]]:
        """
        Validate multiple emails concurrently.
        
        Args:
            emails: List of email addresses to validate
            check_smtp: Whether to perform SMTP validation
            
        Returns:
            List of validation results
        """
        results = []
        
        logger.info(f"Validating {len(emails)} emails (SMTP: {check_smtp})")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all validation tasks
            future_to_email = {
                executor.submit(self.validate_email, email, check_smtp): email 
                for email in emails
            }
            
            # Collect results as they complete
            for i, future in enumerate(as_completed(future_to_email), 1):
                try:
                    result = future.result()
                    results.append(result)
                    
                    # Progress logging
                    if i % 10 == 0 or i == len(emails):
                        valid_count = sum(1 for r in results if r['valid'])
                        logger.info(f"Progress: {i}/{len(emails)} validated, {valid_count} valid")
                        
                except Exception as e:
                    email = future_to_email[future]
                    logger.error(f"Validation failed for {email}: {e}")
                    results.append({
                        'email': email,
                        'valid': False,
                        'error': f"Validation exception: {str(e)}"
                    })
        
        return results


def validate_csv_emails(csv_path: str, output_path: str = None, 
                       check_smtp: bool = True, email_column: str = 'Email') -> Dict[str, any]:
    """
    Validate emails in a CSV file and create a cleaned version.
    
    Args:
        csv_path: Path to input CSV file
        output_path: Path for cleaned CSV (defaults to input_path_cleaned.csv)
        check_smtp: Whether to perform SMTP validation
        email_column: Name of the email column in CSV
        
    Returns:
        Dict with validation statistics and file paths
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    if output_path is None:
        base, ext = os.path.splitext(csv_path)
        output_path = f"{base}_cleaned{ext}"
    
    logger.info(f"Validating emails in CSV: {csv_path}")
    
    # Read CSV file
    with open(csv_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames
    
    if email_column not in fieldnames:
        raise ValueError(f"Email column '{email_column}' not found in CSV. Available columns: {fieldnames}")
    
    # Extract emails for validation
    emails = [row[email_column].strip() for row in rows if row[email_column].strip()]
    unique_emails = list(set(emails))  # Remove duplicates for validation
    
    logger.info(f"Found {len(emails)} emails ({len(unique_emails)} unique) in CSV")
    
    # Validate emails
    validator = EmailValidator()
    validation_results = validator.validate_batch(unique_emails, check_smtp=check_smtp)
    
    # Create lookup for validation results
    email_validity = {result['email']: result for result in validation_results}
    
    # Filter rows with valid emails
    valid_rows = []
    invalid_rows = []
    
    for row in rows:
        email = row[email_column].strip()
        if email and email_validity.get(email, {}).get('valid', False):
            valid_rows.append(row)
        else:
            invalid_rows.append({
                **row,
                'validation_error': email_validity.get(email, {}).get('error', 'Unknown error')
            })
    
    # Write cleaned CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        if valid_rows:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(valid_rows)
    
    # Write invalid emails report
    invalid_report_path = f"{os.path.splitext(output_path)[0]}_invalid.csv"
    if invalid_rows:
        with open(invalid_report_path, 'w', newline='', encoding='utf-8') as f:
            invalid_fieldnames = fieldnames + ['validation_error']
            writer = csv.DictWriter(f, fieldnames=invalid_fieldnames)
            writer.writeheader()
            writer.writerows(invalid_rows)
    
    # Statistics
    stats = {
        'total_rows': len(rows),
        'valid_emails': len(valid_rows),
        'invalid_emails': len(invalid_rows),
        'validation_rate': len(valid_rows) / len(rows) * 100 if rows else 0,
        'input_file': csv_path,
        'output_file': output_path,
        'invalid_report': invalid_report_path if invalid_rows else None
    }
    
    logger.info(f"Email validation complete:")
    logger.info(f"  Total rows: {stats['total_rows']}")
    logger.info(f"  Valid emails: {stats['valid_emails']}")
    logger.info(f"  Invalid emails: {stats['invalid_emails']}")
    logger.info(f"  Validation rate: {stats['validation_rate']:.1f}%")
    logger.info(f"  Cleaned CSV: {output_path}")
    if stats['invalid_report']:
        logger.info(f"  Invalid emails report: {invalid_report_path}")
    
    return stats


def validate_all_csv_files(csv_directory: str = "csv", check_smtp: bool = True) -> List[Dict[str, any]]:
    """
    Validate emails in all CSV files in a directory.
    
    Args:
        csv_directory: Directory containing CSV files
        check_smtp: Whether to perform SMTP validation
        
    Returns:
        List of validation statistics for each file
    """
    if not os.path.exists(csv_directory):
        raise FileNotFoundError(f"CSV directory not found: {csv_directory}")
    
    csv_files = [f for f in os.listdir(csv_directory) if f.endswith('.csv')]
    
    if not csv_files:
        logger.warning(f"No CSV files found in {csv_directory}")
        return []
    
    logger.info(f"Found {len(csv_files)} CSV files to validate")
    
    all_stats = []
    
    for csv_file in csv_files:
        csv_path = os.path.join(csv_directory, csv_file)
        
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing: {csv_file}")
            logger.info(f"{'='*60}")
            
            stats = validate_csv_emails(csv_path, check_smtp=check_smtp)
            all_stats.append(stats)
            
        except Exception as e:
            logger.error(f"Failed to validate {csv_file}: {e}")
            all_stats.append({
                'input_file': csv_path,
                'error': str(e),
                'total_rows': 0,
                'valid_emails': 0,
                'invalid_emails': 0,
                'validation_rate': 0
            })
    
    # Summary report
    total_rows = sum(s.get('total_rows', 0) for s in all_stats)
    total_valid = sum(s.get('valid_emails', 0) for s in all_stats)
    total_invalid = sum(s.get('invalid_emails', 0) for s in all_stats)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"BATCH VALIDATION SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Files processed: {len(csv_files)}")
    logger.info(f"Total rows: {total_rows}")
    logger.info(f"Valid emails: {total_valid}")
    logger.info(f"Invalid emails: {total_invalid}")
    logger.info(f"Overall validation rate: {total_valid/total_rows*100 if total_rows else 0:.1f}%")
    
    return all_stats


if __name__ == "__main__":
    # Example usage
    import argparse
    
    parser = argparse.ArgumentParser(description="Email Validation Tool")
    parser.add_argument("--csv", help="Path to CSV file to validate")
    parser.add_argument("--directory", default="csv", help="Directory containing CSV files")
    parser.add_argument("--no-smtp", action="store_true", help="Skip SMTP validation")
    parser.add_argument("--email-column", default="Email", help="Name of email column")
    
    args = parser.parse_args()
    
    check_smtp = not args.no_smtp
    
    if args.csv:
        # Validate single CSV file
        stats = validate_csv_emails(args.csv, check_smtp=check_smtp, email_column=args.email_column)
        print(f"\nValidation complete: {stats['valid_emails']}/{stats['total_rows']} emails valid")
    else:
        # Validate all CSV files in directory
        all_stats = validate_all_csv_files(args.directory, check_smtp=check_smtp)
        print(f"\nBatch validation complete: {len(all_stats)} files processed")