"""
Output Writer — saves generated emails to JSON and CSV.
"""
import os
import json
import csv
from datetime import datetime
from config import OUTPUT_DIR
from logger import logger

os.makedirs(OUTPUT_DIR, exist_ok=True)


def save_results(records: list[dict], run_id: str | None = None) -> str:
    """
    Save list of generated email records to JSON + CSV.
    Each record should have: name, email, company, role, subject, body,
                              referral (optional), sent (bool)
    Returns path to JSON file.
    """
    if not run_id:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = os.path.join(OUTPUT_DIR, f"run_{run_id}.json")
    csv_path  = os.path.join(OUTPUT_DIR, f"run_{run_id}.csv")

    with open(json_path, "w") as f:
        json.dump(records, f, indent=2)
    logger.info(f"Results saved to {json_path}")

    if records:
        fieldnames = list(records[0].keys())
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)
        logger.info(f"Results saved to {csv_path}")

    return json_path
