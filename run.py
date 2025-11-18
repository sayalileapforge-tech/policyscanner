#!/usr/bin/env python
"""
Render deployment entry point.
This script allows Render to run the FastAPI app from the repository root.
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path so 'dash_pdf_ui' module can be found
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Now import and run the FastAPI app
from dash_pdf_ui.backend.main import app

if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment variable or default to 8000
    port = int(os.environ.get("PORT", 8000))
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
