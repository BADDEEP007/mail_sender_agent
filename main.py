"""
main.py — Entry point for the Automated Outreach Pipeline

Usage:
  Single contact:
    python main.py --name "Nishant Chouhan" --email "nishant@softude.com" \
                   --company "Softude" --role "CTO" \
                   --resume data/resumes/Backend_Resume.pdf

  Batch from CSV:
    python main.py --csv contacts.csv --resume data/resumes/Backend_Resume.pdf

  Generate and review before sending:
    python main.py --csv contacts.csv --generate-review --resume data/resumes/Backend_Resume.pdf

  Validate emails before processing:
    python main.py --csv contacts.csv --validate-emails --resume data/resumes/Backend_Resume.pdf

  Use custom profile file:
    python main.py --csv contacts.csv --profile my_profile.txt

  Disable email caching (regenerate all):
    python main.py --csv contacts.csv --no-cache

  Dry run (no emails sent):
    DRY_RUN=true python main.py --csv contacts.csv

  Rebuild FAISS index:
    python main.py --csv contacts.csv --rebuild-index
"""
import argparse
import sys
import os

# Allow running from project root
sys.path.insert(0, os.path.dirname(__file__))

from pipeline import run_single, run_batch_from_csv, generate_and_review_batch, send_generated_emails
from profile_store import get_retriever
from config import DRY_RUN
from logger import logger
from email_validator import validate_csv_emails


def parse_args():
    parser = argparse.ArgumentParser(description="Automated Outreach Pipeline")
    parser.add_argument("--name",          help="Recipient name (single mode)")
    parser.add_argument("--email",         help="Recipient email (single mode)")
    parser.add_argument("--company",       help="Target company (single mode)")
    parser.add_argument("--role",          help="Target role (single mode)")
    parser.add_argument("--resume",        help="Path to resume PDF to attach", default=None)
    parser.add_argument("--relationship",  help="stranger | alumni | mutual", default=None)
    parser.add_argument("--csv",           help="Path to CSV for batch mode")
    parser.add_argument("--no-send",       action="store_true", help="Generate only, don't send")
    parser.add_argument("--generate-review", action="store_true", help="Generate all emails first, then ask for approval before sending")
    parser.add_argument("--validate-emails", action="store_true", help="Validate and clean emails in CSV before processing")
    parser.add_argument("--no-smtp-validation", action="store_true", help="Skip SMTP validation (faster but less accurate)")
    parser.add_argument("--profile",       help="Path to profile text file (default: profile.txt)", default=None)
    parser.add_argument("--no-store",      action="store_true", help="Disable email storage, regenerate all emails")
    parser.add_argument("--rebuild-index", action="store_true", help="Force rebuild FAISS index")
    return parser.parse_args()


def main():
    args = parse_args()
    send = not args.no_send
    use_stored = not args.no_store
    mode = "DRY RUN" if DRY_RUN else ("GENERATE ONLY" if not send else "LIVE")
    storage_mode = "STORAGE ENABLED" if use_stored else "NO STORAGE"
    logger.info(f"Starting pipeline — mode: {mode}, {storage_mode}")

    if args.csv:
        # Validate emails first if requested
        csv_to_process = args.csv
        if args.validate_emails:
            logger.info("Validating emails in CSV before processing...")
            check_smtp = not args.no_smtp_validation
            
            try:
                stats = validate_csv_emails(
                    csv_path=args.csv,
                    check_smtp=check_smtp
                )
                
                print(f"\n📧 Email validation complete:")
                print(f"  Valid emails: {stats['valid_emails']}/{stats['total_rows']} ({stats['validation_rate']:.1f}%)")
                
                if stats['valid_emails'] == 0:
                    print("❌ No valid emails found. Exiting.")
                    sys.exit(1)
                elif stats['invalid_emails'] > 0:
                    print(f"  Invalid emails removed: {stats['invalid_emails']}")
                    print(f"  Using cleaned CSV: {stats['output_file']}")
                    csv_to_process = stats['output_file']
                
            except Exception as e:
                logger.error(f"Email validation failed: {e}")
                print("❌ Email validation failed. Use --no-smtp-validation for faster validation or proceed without validation.")
                sys.exit(1)
        
        # Batch mode
        if args.generate_review:
            # Generate all emails first, then ask for approval
            logger.info("Generating emails for review...")
            results = generate_and_review_batch(
                csv_path=csv_to_process,
                resume_path=args.resume,
                force_rebuild=args.rebuild_index,
                profile_path=args.profile,
                use_stored=use_stored
            )
            
            # Display all generated emails for review
            print("\n" + "="*80)
            print(f"GENERATED {len(results)} EMAILS FOR REVIEW")
            if use_stored:
                stored_count = sum(1 for r in results if r.get('stored_at'))
                print(f"({stored_count} from storage, {len(results) - stored_count} newly generated)")
            print("="*80)
            
            for i, result in enumerate(results, 1):
                if result.get("error"):
                    print(f"\n[{i}] ERROR - {result.get('name', '?')} ({result.get('email', '?')})")
                    print(f"    Error: {result['error']}")
                    continue
                    
                storage_indicator = "📁" if result.get('stored_at') else "✨"
                print(f"\n[{i}] {storage_indicator} {result['name']} - {result['role']} @ {result['company']}")
                print(f"    To: {result['email']}")
                print(f"    Subject: {result['subject']}")
                print(f"    Body Preview: {result['body'][:150]}...")
                if result.get('referral'):
                    print(f"    Referral: {result['referral'][:100]}...")
            
            print("\n" + "="*80)
            
            # Ask for approval
            while True:
                response = input("\nReview complete. Send all emails? (y/n/preview): ").lower().strip()
                
                if response == 'y' or response == 'yes':
                    print("\nSending emails...")
                    stats = send_generated_emails(results)
                    print(f"\nDone! {stats['sent']}/{stats['total']} emails sent successfully")
                    break
                elif response == 'n' or response == 'no':
                    print("Emails not sent. Generated emails are saved for later review.")
                    break
                elif response == 'preview':
                    # Show full preview of a specific email
                    try:
                        email_num = int(input("Enter email number to preview (1-{}): ".format(len(results))))
                        if 1 <= email_num <= len(results):
                            result = results[email_num - 1]
                            if not result.get("error"):
                                print("\n" + "-"*60)
                                print(f"FULL PREVIEW - Email #{email_num}")
                                print(f"To: {result['email']}")
                                print(f"Subject: {result['subject']}")
                                print("-"*60)
                                print(result['body'])
                                if result.get('referral'):
                                    print("\n--- REFERRAL MESSAGE ---")
                                    print(result['referral'])
                                print("-"*60)
                            else:
                                print(f"Email #{email_num} has an error: {result['error']}")
                        else:
                            print("Invalid email number")
                    except ValueError:
                        print("Please enter a valid number")
                else:
                    print("Please enter 'y' (yes), 'n' (no), or 'preview'")
        else:
            # Original batch mode
            results = run_batch_from_csv(
                csv_path=csv_to_process,
                resume_path=args.resume,
                send=send,
                force_rebuild=args.rebuild_index,
                profile_path=args.profile,
                use_stored=use_stored
            )
            sent  = sum(1 for r in results if r.get("sent"))
            total = len(results)
            logger.info(f"Done — {sent}/{total} emails sent")

    elif args.name and args.email and args.company and args.role:
        # Single mode
        retriever = get_retriever(profile_path=args.profile, force_rebuild=args.rebuild_index)
        result = run_single(
            name=args.name,
            email=args.email,
            company=args.company,
            role=args.role,
            resume_path=args.resume,
            relationship=args.relationship,
            send=send,
            retriever=retriever,
            profile_path=args.profile,
            use_stored=use_stored
        )
        print("\n" + "="*60)
        print(f"Subject : {result['subject']}")
        print(f"To      : {result['email']}")
        print("-"*60)
        print(result["body"])
        if result.get("referral"):
            print("\n--- REFERRAL MESSAGE ---")
            print(result["referral"])
        print("="*60)
        print(f"Sent    : {result['sent']}")

    else:
        print("Provide either --csv OR (--name --email --company --role)")
        print("Run with --help for usage.")
        sys.exit(1)


if __name__ == "__main__":
    main()
