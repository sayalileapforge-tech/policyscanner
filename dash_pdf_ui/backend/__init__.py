"""Backend package initializer.

This file makes `backend` a proper package so relative imports like
`from .parser import parse_report` work reliably when running the app.
"""

__all__ = ["db", "parser", "main"]
