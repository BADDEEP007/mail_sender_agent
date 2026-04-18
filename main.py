"""
main.py — Entry point for the Automated Outreach Pipeline

Usage:
  Single contact:
    python main.py --name "Nishant Chouhan" --email "nishant@softude.com" \
                   --company "Softude" --role "CTO" \
                   --resume data/resumes/Backend_Resume.pdf

  Batch from CSV:
    python main.py --csv contacts.csv --resume data/resumes/Backend_Resume.pdf

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

from pipeline import run_single, run_batch_from_csv
from resume_store import get_retriever
from config import DRY_RUN
from logger import logger


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
    parser.add_argument("--rebuild-index", action="store_true", help="Force rebuild FAISS index")
    return parser.parse_args()


def main():
    args = parse_args()
    send = not args.no_send
    mode = "DRY RUN" if DRY_RUN else ("GENERATE ONLY" if not send else "LIVE")
    logger.info(f"Starting pipeline — mode: {mode}")

    if args.csv:
        # Batch mode
        results = run_batch_from_csv(
            csv_path=args.csv,
            resume_path=args.resume,
            send=send,
            force_rebuild=args.rebuild_index
        )
        sent  = sum(1 for r in results if r.get("sent"))
        total = len(results)
        logger.info(f"Done — {sent}/{total} emails sent")

    elif args.name and args.email and args.company and args.role:
        # Single mode
        retriever = get_retriever(force_rebuild=args.rebuild_index)
        result = run_single(
            name=args.name,
            email=args.email,
            company=args.company,
            role=args.role,
            resume_path=args.resume,
            relationship=args.relationship,
            send=send,
            retriever=retriever
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
