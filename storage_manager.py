#!/usr/bin/env python3
"""
Email Storage Management Utility
Provides commands to view, search, and manage permanently stored emails
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import argparse
from email_store import (
    print_storage_summary, 
    get_storage_stats, 
    list_stored_emails, 
    delete_stored_email,
    get_stored_email
)
from logger import logger

def show_storage():
    """Display detailed storage information"""
    print_storage_summary()
    
    stored_emails = list_stored_emails()
    
    if stored_emails:
        print("\n📁 DETAILED STORAGE CONTENTS:")
        print("-" * 90)
        for i, email in enumerate(stored_emails, 1):
            status_icon = "✅" if email.get('sent') else "📝"
            stored_date = email.get('stored_at', '')[:10] if email.get('stored_at') else 'Unknown'
            
            print(f"[{i:2d}] {status_icon} {email.get('name', '?'):20} | {email.get('company', '?'):15} | {stored_date}")
            print(f"     📧 {email.get('email', '?')}")
            print(f"     📝 {email.get('subject', '?')[:70]}...")
            print(f"     📁 {os.path.basename(email.get('file_path', ''))}")
            print()

def search_storage(query: str):
    """Search for specific contacts in storage"""
    stored_emails = list_stored_emails()
    query_lower = query.lower()
    
    matches = []
    for email in stored_emails:
        if (query_lower in email.get('name', '').lower() or 
            query_lower in email.get('email', '').lower() or 
            query_lower in email.get('company', '').lower() or
            query_lower in email.get('role', '').lower()):
            matches.append(email)
    
    if matches:
        print(f"\n🔍 Found {len(matches)} matches for '{query}' in storage:")
        print("-" * 70)
        for i, email in enumerate(matches, 1):
            status_icon = "✅" if email.get('sent') else "📝"
            stored_date = email.get('stored_at', '')[:10] if email.get('stored_at') else 'Unknown'
            print(f"[{i}] {status_icon} {email.get('name', '?')} @ {email.get('company', '?')} ({stored_date})")
            print(f"    📧 {email.get('email', '?')}")
            print(f"    📝 {email.get('subject', '?')}")
            print()
    else:
        print(f"❌ No matches found for '{query}' in storage")

def view_email(name: str, email: str, company: str, role: str):
    """View full content of a stored email"""
    stored_email = get_stored_email(name, email, company, role)
    
    if stored_email:
        print("\n" + "="*70)
        print("📧 STORED EMAIL DETAILS")
        print("="*70)
        print(f"Name: {stored_email.get('name', 'Unknown')}")
        print(f"Email: {stored_email.get('email', 'Unknown')}")
        print(f"Company: {stored_email.get('company', 'Unknown')}")
        print(f"Role: {stored_email.get('role', 'Unknown')}")
        print(f"Subject: {stored_email.get('subject', 'No Subject')}")
        print(f"Sent: {'✅ Yes' if stored_email.get('sent') else '📝 No'}")
        print(f"Stored: {stored_email.get('stored_at', 'Unknown')[:19]}")
        print("-"*70)
        print("BODY:")
        print(stored_email.get('body', 'No body content'))
        
        if stored_email.get('referral'):
            print("\n--- REFERRAL MESSAGE ---")
            print(stored_email.get('referral'))
        
        print("="*70)
    else:
        print(f"❌ No stored email found for {name} at {company}")

def delete_email(name: str, email: str, company: str, role: str):
    """Delete a stored email"""
    if delete_stored_email(name, email, company, role):
        print(f"✅ Deleted stored email for {name} at {company}")
    else:
        print(f"❌ No stored email found for {name} at {company}")

def list_companies():
    """List all companies with stored emails"""
    stored_emails = list_stored_emails()
    
    companies = {}
    for email in stored_emails:
        company = email.get('company', 'Unknown')
        if company not in companies:
            companies[company] = {'total': 0, 'sent': 0}
        companies[company]['total'] += 1
        if email.get('sent'):
            companies[company]['sent'] += 1
    
    if companies:
        print("\n🏢 COMPANIES WITH STORED EMAILS:")
        print("-" * 50)
        for company, stats in sorted(companies.items()):
            print(f"{company:30} | {stats['sent']:2d}/{stats['total']:2d} sent")
    else:
        print("❌ No companies found in storage")

def main():
    parser = argparse.ArgumentParser(description="Email Storage Management Utility")
    parser.add_argument("action", choices=["show", "search", "view", "delete", "stats", "companies"], 
                       help="Action to perform")
    parser.add_argument("--query", help="Search query (for search action)")
    parser.add_argument("--name", help="Contact name (for view/delete actions)")
    parser.add_argument("--email", help="Contact email (for view/delete actions)")
    parser.add_argument("--company", help="Company name (for view/delete actions)")
    parser.add_argument("--role", help="Role name (for view/delete actions)")
    
    args = parser.parse_args()
    
    if args.action == "show":
        show_storage()
    elif args.action == "search":
        if not args.query:
            print("❌ Search requires --query parameter")
            sys.exit(1)
        search_storage(args.query)
    elif args.action == "view":
        if not all([args.name, args.email, args.company, args.role]):
            print("❌ View requires --name, --email, --company, and --role parameters")
            sys.exit(1)
        view_email(args.name, args.email, args.company, args.role)
    elif args.action == "delete":
        if not all([args.name, args.email, args.company, args.role]):
            print("❌ Delete requires --name, --email, --company, and --role parameters")
            sys.exit(1)
        delete_email(args.name, args.email, args.company, args.role)
    elif args.action == "companies":
        list_companies()
    elif args.action == "stats":
        stats = get_storage_stats()
        print("📊 STORAGE STATISTICS")
        print("=" * 30)
        print(f"Total stored emails: {stats['total_stored']}")
        print(f"Successfully sent: {stats['sent_count']}")
        print(f"Not yet sent: {stats['unsent_count']}")

if __name__ == "__main__":
    main()