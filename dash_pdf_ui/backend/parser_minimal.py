from __future__ import annotations
from pathlib import Path
from typing import Dict, Any


def parse_report(pdf_path: Path) -> Dict[str, Any]:
    """Minimal parse_report used to start the server while parser is being fixed."""
    return {
        "_id": f"stub-{pdf_path.name}",
        "file_name": pdf_path.name,
        "header": {},
        "policies": [],
        "previous_inquiries": [],
        "claims": [],
        "pages_count": 0,
        "extraction_stats": [],
        "full_text": "",
    }
