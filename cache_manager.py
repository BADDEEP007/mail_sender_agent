#!/usr/bin/env python3
"""
Session Email Cache Management Utility
Provides commands to view and manage today's email cache
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import argparse
from email_cache import print_cache_summary, get_cache_stats, clear_session_cache, _initialize_session_cache, _session_cache
from logger import logger

def show_cache():
    """Display detailed cache information for today"""
    print_cache_summary()
    
    _initialize_session_cache()
    stats = get_cache_stats()
    
    if _session_cache:
        print("\n📋 DETAILED TODAY'S CACHE CONTENTS:")
        print("-" * 80)
        for i, (cache_key, result) in enumerate(_session_cache.items(), 1):
            status_icon = "✅" if result.get('sent') else ("❌" if 'error' in result else "📝")
            timestamp = result.get('timestamp', 'Unknown')[:19]  # Show date/time only
            
            print(f"[{i:2d}] {status_icon} {result.get('name', '?'):20} | {result.get('company', '?'):15} | {timestamp}")
            print(f"     📧 {result.get('email', '?')}")
            print(f"     📝 {result.get('subject', '?')[:60]}...")
            if 'error' in result:
                print(f"     ❌ Error: {result['error']}")
            print()

def clear_cache():
    """Clear today's session cache"""
    clear_session_cache()
    print("✅ Today's session cache cleared")
    print("   Note: This only clears the in-memory cache for today")
    print("   Saved files in output/ directory are not affected")

def search_cache(query: str):
    """Search for specific contacts in today's cache"""
    _initialize_session_cache()
    query_lower = query.lower()
    
    matches = []
    for cache_key, result in _session_cache.items():
        if (query_lower in result.get('name', '').lower() or 
            query_lower in result.get('email', '').lower() or 
            query_lower in result.get('company', '').lower() or
            query_lower in result.get('role', '').lower()):
            matches.append(result)
    
    if matches:
        print(f"\n🔍 Found {len(matches)} matches for '{query}' in today's cache:")
        print("-" * 60)
        for i, result in enumerate(matches, 1):
            status_icon = "✅" if result.get('sent') else ("❌" if 'error' in result else "📝")
            timestamp = result.get('timestamp', '')[:19] if result.get('timestamp') else 'Unknown'
            print(f"[{i}] {status_icon} {result.get('name', '?')} @ {result.get('company', '?')} ({timestamp})")
            print(f"    📧 {result.get('email', '?')}")
            print(f"    📝 {result.get('subject', '?')}")
            if 'error' in result:
                print(f"    ❌ {result['error']}")
            print()
    else:
        print(f"❌ No matches found for '{query}' in today's cache")

def main():
    parser = argparse.ArgumentParser(description="Session Email Cache Management Utility")
    parser.add_argument("action", choices=["show", "clear", "search", "stats"], 
                       help="Action to perform")
    parser.add_argument("--query", help="Search query (for search action)")
    
    args = parser.parse_args()
    
    if args.action == "show":
        show_cache()
    elif args.action == "clear":
        clear_cache()
    elif args.action == "search":
        if not args.query:
            print("❌ Search requires --query parameter")
            sys.exit(1)
        search_cache(args.query)
    elif args.action == "stats":
        stats = get_cache_stats()
        print("📊 TODAY'S CACHE STATISTICS")
        print("=" * 35)
        print(f"Total emails today: {stats['total_cached']}")
        print(f"Successfully sent: {stats['sent_count']}")
        print(f"Not yet sent: {stats['unsent_count']}")
        print(f"Generation errors: {stats['error_count']}")

if __name__ == "__main__":
    main()