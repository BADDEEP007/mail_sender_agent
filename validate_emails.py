#!/usr/bin/env python3
"""
Email Validation CLI Tool
Integrates with the existing outreach pipeline to validate and clean CSV files.
"""
import argparse
import sys
import os
from email_validator import validate_csv_emails, validate_all_csv_files, EmailValidator
from logger import logger


def main():
    parser = argparse.ArgumentParser(
        description="Email Validation Tool for Outreach Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate single CSV file
  python validate_emails.py --csv csv/hr1.csv
  
  # Validate all CSV files in directory
  python validate_emails.py --directory csv
  
  # Skip SMTP validation (faster but less accurate)
  python validate_emails.py --csv csv/hr1.csv --no-smtp
  
  # Specify custom email column name
  python validate_emails.py --csv contacts.csv --email-column "email_address"
  
  # Validate and show detailed results
  python validate_emails.py --csv csv/hr1.csv --verbose
        """
    )
    
    # Input options
    parser.add_argument(
        "--csv", 
        help="Path to single CSV file to validate"
    )
    parser.add_argument(
        "--directory", 
        default="csv", 
        help="Directory containing CSV files (default: csv)"
    )
    
    # Validation options
    parser.add_argument(
        "--no-smtp", 
        action="store_true", 
        help="Skip SMTP validation (faster but less accurate)"
    )
    parser.add_argument(
        "--email-column", 
        default="Email", 
        help="Name of email column in CSV (default: Email)"
    )
    
    # Output options
    parser.add_argument(
        "--output", 
        help="Output path for cleaned CSV (default: input_cleaned.csv)"
    )
    parser.add_argument(
        "--verbose", 
        action="store_true", 
        help="Show detailed validation results"
    )
    
    # Performance options
    parser.add_argument(
        "--max-workers", 
        type=int, 
        default=5, 
        help="Maximum concurrent validation threads (default: 5)"
    )
    parser.add_argument(
        "--timeout", 
        type=int, 
        default=10, 
        help="Timeout for network operations in seconds (default: 10)"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.csv and not os.path.exists(args.csv):
        logger.error(f"CSV file not found: {args.csv}")
        sys.exit(1)
    
    if not args.csv and not os.path.exists(args.directory):
        logger.error(f"Directory not found: {args.directory}")
        sys.exit(1)
    
    check_smtp = not args.no_smtp
    
    try:
        if args.csv:
            # Validate single CSV file
            logger.info(f"Validating single CSV file: {args.csv}")
            logger.info(f"SMTP validation: {'enabled' if check_smtp else 'disabled'}")
            
            stats = validate_csv_emails(
                csv_path=args.csv,
                output_path=args.output,
                check_smtp=check_smtp,
                email_column=args.email_column
            )
            
            # Display results
            print("\n" + "="*60)
            print("📧 EMAIL VALIDATION RESULTS")
            print("="*60)
            print(f"Input file: {stats['input_file']}")
            print(f"Output file: {stats['output_file']}")
            print(f"Total rows: {stats['total_rows']}")
            print(f"Valid emails: {stats['valid_emails']}")
            print(f"Invalid emails: {stats['invalid_emails']}")
            print(f"Validation rate: {stats['validation_rate']:.1f}%")
            
            if stats['invalid_report']:
                print(f"Invalid emails report: {stats['invalid_report']}")
            
            if args.verbose and stats['invalid_emails'] > 0:
                print(f"\n📋 Invalid emails saved to: {stats['invalid_report']}")
                print("You can review the validation errors in the report file.")
            
            print("="*60)
            
            if stats['valid_emails'] > 0:
                print(f"\n✅ Success! {stats['valid_emails']} valid emails ready for outreach.")
                print(f"Use the cleaned file: {stats['output_file']}")
            else:
                print(f"\n❌ No valid emails found in {args.csv}")
                
        else:
            # Validate all CSV files in directory
            logger.info(f"Validating all CSV files in directory: {args.directory}")
            logger.info(f"SMTP validation: {'enabled' if check_smtp else 'disabled'}")
            
            all_stats = validate_all_csv_files(
                csv_directory=args.directory,
                check_smtp=check_smtp
            )
            
            if not all_stats:
                print(f"\n❌ No CSV files found in {args.directory}")
                sys.exit(1)
            
            # Display summary
            total_files = len(all_stats)
            successful_files = sum(1 for s in all_stats if not s.get('error'))
            total_rows = sum(s.get('total_rows', 0) for s in all_stats)
            total_valid = sum(s.get('valid_emails', 0) for s in all_stats)
            total_invalid = sum(s.get('invalid_emails', 0) for s in all_stats)
            
            print("\n" + "="*70)
            print("📧 BATCH EMAIL VALIDATION SUMMARY")
            print("="*70)
            print(f"Files processed: {successful_files}/{total_files}")
            print(f"Total rows: {total_rows}")
            print(f"Valid emails: {total_valid}")
            print(f"Invalid emails: {total_invalid}")
            print(f"Overall validation rate: {total_valid/total_rows*100 if total_rows else 0:.1f}%")
            
            if args.verbose:
                print("\nPer-file results:")
                for i, stats in enumerate(all_stats, 1):
                    if stats.get('error'):
                        print(f"  [{i:2d}] ❌ {os.path.basename(stats['input_file'])}: {stats['error']}")
                    else:
                        rate = stats['validation_rate']
                        status = "✅" if rate > 80 else "⚠️" if rate > 50 else "❌"
                        print(f"  [{i:2d}] {status} {os.path.basename(stats['input_file'])}: "
                              f"{stats['valid_emails']}/{stats['total_rows']} ({rate:.1f}%)")
            
            print("="*70)
            
            if total_valid > 0:
                print(f"\n✅ Success! {total_valid} total valid emails ready for outreach.")
                print("Cleaned CSV files have been created with '_cleaned' suffix.")
            else:
                print(f"\n❌ No valid emails found in any CSV files.")
    
    except KeyboardInterrupt:
        logger.info("Validation interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()