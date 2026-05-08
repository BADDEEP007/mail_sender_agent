#!/usr/bin/env python3
"""
Cleanup Redundant Files Script
Identifies and removes duplicate/redundant files in the project.
"""
import os
import hashlib
import csv
from collections import defaultdict
from logger import logger


def get_file_hash(file_path: str) -> str:
    """Calculate MD5 hash of a file."""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.error(f"Error hashing {file_path}: {e}")
        return ""


def find_duplicate_csv_files(csv_dir: str = "csv") -> dict:
    """Find duplicate CSV files based on content hash."""
    if not os.path.exists(csv_dir):
        return {}
    
    file_hashes = defaultdict(list)
    
    for filename in os.listdir(csv_dir):
        if filename.endswith('.csv'):
            file_path = os.path.join(csv_dir, filename)
            file_hash = get_file_hash(file_path)
            if file_hash:
                file_hashes[file_hash].append(file_path)
    
    # Return only groups with duplicates
    duplicates = {hash_val: files for hash_val, files in file_hashes.items() if len(files) > 1}
    return duplicates


def analyze_csv_content(csv_dir: str = "csv") -> dict:
    """Analyze CSV files to understand their content and structure."""
    analysis = {}
    
    if not os.path.exists(csv_dir):
        return analysis
    
    for filename in os.listdir(csv_dir):
        if filename.endswith('.csv'):
            file_path = os.path.join(csv_dir, filename)
            try:
                with open(file_path, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    
                    analysis[filename] = {
                        'path': file_path,
                        'rows': len(rows),
                        'columns': list(reader.fieldnames) if reader.fieldnames else [],
                        'has_email_column': 'Email' in (reader.fieldnames or []),
                        'sample_emails': [row.get('Email', '') for row in rows[:3] if row.get('Email')],
                        'file_size': os.path.getsize(file_path)
                    }
            except Exception as e:
                logger.error(f"Error analyzing {file_path}: {e}")
                analysis[filename] = {'error': str(e)}
    
    return analysis


def suggest_files_to_remove(duplicates: dict, analysis: dict) -> list:
    """Suggest which duplicate files can be safely removed."""
    suggestions = []
    
    for hash_val, files in duplicates.items():
        if len(files) <= 1:
            continue
        
        # Sort files by preference (keep the original, remove copies)
        files_with_info = []
        for file_path in files:
            filename = os.path.basename(file_path)
            
            # Scoring system for which file to keep
            score = 0
            
            # Prefer files without "copy" in the name
            if 'copy' not in filename.lower():
                score += 10
            
            # Prefer shorter names (likely original)
            score += max(0, 20 - len(filename))
            
            # Prefer files with more standard names
            if filename in ['hr1.csv', 'contacts.csv', 'hr_contacts.csv']:
                score += 15
            
            files_with_info.append((score, file_path, filename))
        
        # Sort by score (highest first) and keep the best one
        files_with_info.sort(reverse=True)
        keep_file = files_with_info[0][1]
        remove_files = [info[1] for info in files_with_info[1:]]
        
        suggestions.append({
            'keep': keep_file,
            'remove': remove_files,
            'reason': f"Duplicate content (hash: {hash_val[:8]}...)"
        })
    
    return suggestions


def cleanup_redundant_files(csv_dir: str = "csv", dry_run: bool = True) -> dict:
    """Clean up redundant CSV files."""
    logger.info(f"Analyzing CSV files in {csv_dir}...")
    
    # Find duplicates
    duplicates = find_duplicate_csv_files(csv_dir)
    analysis = analyze_csv_content(csv_dir)
    suggestions = suggest_files_to_remove(duplicates, analysis)
    
    results = {
        'total_files': len(analysis),
        'duplicate_groups': len(duplicates),
        'files_to_remove': sum(len(s['remove']) for s in suggestions),
        'removed_files': [],
        'kept_files': [],
        'errors': []
    }
    
    print("\n" + "="*70)
    print("🧹 CSV FILE CLEANUP ANALYSIS")
    print("="*70)
    print(f"Total CSV files found: {results['total_files']}")
    print(f"Duplicate groups found: {results['duplicate_groups']}")
    print(f"Files suggested for removal: {results['files_to_remove']}")
    
    if not suggestions:
        print("\n✅ No redundant files found!")
        return results
    
    print("\n📋 CLEANUP SUGGESTIONS:")
    print("-" * 50)
    
    for i, suggestion in enumerate(suggestions, 1):
        keep_file = os.path.basename(suggestion['keep'])
        remove_files = [os.path.basename(f) for f in suggestion['remove']]
        
        print(f"\n[{i}] {suggestion['reason']}")
        print(f"    Keep: {keep_file}")
        print(f"    Remove: {', '.join(remove_files)}")
        
        # Show file details
        keep_info = analysis.get(keep_file, {})
        print(f"    Details: {keep_info.get('rows', 0)} rows, {keep_info.get('file_size', 0)} bytes")
    
    if dry_run:
        print(f"\n🔍 DRY RUN MODE - No files were actually removed")
        print("Run with --execute to perform the cleanup")
    else:
        print(f"\n🗑️  EXECUTING CLEANUP...")
        
        for suggestion in suggestions:
            results['kept_files'].append(suggestion['keep'])
            
            for file_to_remove in suggestion['remove']:
                try:
                    os.remove(file_to_remove)
                    results['removed_files'].append(file_to_remove)
                    logger.info(f"Removed duplicate file: {file_to_remove}")
                except Exception as e:
                    error_msg = f"Failed to remove {file_to_remove}: {e}"
                    results['errors'].append(error_msg)
                    logger.error(error_msg)
        
        print(f"✅ Cleanup complete!")
        print(f"   Removed: {len(results['removed_files'])} files")
        print(f"   Kept: {len(results['kept_files'])} files")
        if results['errors']:
            print(f"   Errors: {len(results['errors'])}")
    
    print("="*70)
    return results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Cleanup redundant CSV files")
    parser.add_argument("--directory", default="csv", help="CSV directory to clean")
    parser.add_argument("--execute", action="store_true", help="Actually remove files (default is dry run)")
    parser.add_argument("--analyze-only", action="store_true", help="Only show analysis, no cleanup suggestions")
    
    args = parser.parse_args()
    
    if args.analyze_only:
        analysis = analyze_csv_content(args.directory)
        
        print("\n" + "="*70)
        print("📊 CSV FILE ANALYSIS")
        print("="*70)
        
        for filename, info in analysis.items():
            if 'error' in info:
                print(f"❌ {filename}: {info['error']}")
            else:
                email_status = "✅" if info['has_email_column'] else "❌"
                print(f"{email_status} {filename}")
                print(f"    Rows: {info['rows']}, Columns: {len(info['columns'])}")
                print(f"    Size: {info['file_size']} bytes")
                if info['sample_emails']:
                    print(f"    Sample emails: {', '.join(info['sample_emails'][:2])}")
                print()
    else:
        cleanup_redundant_files(args.directory, dry_run=not args.execute)


if __name__ == "__main__":
    main()