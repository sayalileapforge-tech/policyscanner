#!/usr/bin/env python
from pathlib import Path
import sys
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from dash_pdf_ui.backend.parser import parse_report

pdf_path = Path("dash_pdf_ui\\DASH Report - REDDY, VISHWANAUTH - 2025-11-07 19-43-39-EST - En.pdf")

if not pdf_path.exists():
    print(f"PDF not found: {pdf_path}")
    sys.exit(1)

print(f"Parsing: {pdf_path}")
print("=" * 80)

report = parse_report(pdf_path)

print("\n[TEST] PARSED REPORT STRUCTURE:")
print(f"Number of policies: {len(report.get('policies', []))}")

if report.get('policies'):
    for idx, policy in enumerate(report['policies']):
        print(f"\n[TEST] Policy {idx}:")
        print(f"  Keys: {list(policy.keys())}")
        print(f"  Has 'start_of_earliest_term': {'start_of_earliest_term' in policy}")
        if 'start_of_earliest_term' in policy:
            print(f"  start_of_earliest_term value: {policy['start_of_earliest_term']}")
        print(f"  header.effective_date: {policy.get('header', {}).get('effective_date')}")
        print(f"  header.expiry_date: {policy.get('header', {}).get('expiry_date')}")
