# backend/db.py
from __future__ import annotations
from typing import Dict, Any, List, Optional
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import ServerSelectionTimeoutError
import threading
import os

# Try to connect to MongoDB with a short timeout. If unavailable, fall back to
# a simple in-memory store so the app can run without a Mongo daemon (useful
# for development / demo environments).

_USE_MOCK = False
_mock_lock = threading.Lock()
_mock_store: Dict[str, Dict[str, Any]] = {}

def get_client(uri: str = None, timeout_ms: int = 2000):
    # Use MONGO_URI environment variable if available, otherwise use MongoDB Atlas
    if uri is None:
        uri = os.environ.get("MONGO_URI", "mongodb+srv://policydbuser:dbuser1234@policy-cluster.csl5psp.mongodb.net/?appName=policy-cluster")
    return MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)

def clear_mock_store():
    """Clear the in-memory mock store - useful for development."""
    global _mock_store
    with _mock_lock:
        _mock_store.clear()

def _get_collection():
    global _USE_MOCK
    if _USE_MOCK:
        return None
    client = get_client()
    try:
        # quick ping to ensure server is up
        client.admin.command("ping")
    except ServerSelectionTimeoutError:
        _USE_MOCK = True
        return None
    db = client["dash_reports"]
    return db["reports"]

def upsert_report(doc: Dict[str, Any]) -> Dict[str, Any]:
    col = _get_collection()
    if col is None:
        # in-memory fallback
        with _mock_lock:
            _mock_store[doc["_id"]] = doc.copy()
            result = _mock_store[doc["_id"]]
            print(f"[DB DEBUG] Upserted to mock store. Policies count: {len(result.get('policies', []))}")
            if result.get('policies'):
                print(f"[DB DEBUG] First policy has 'start_of_earliest_term': {'start_of_earliest_term' in result['policies'][0]}")
            return result

    result = col.find_one_and_update(
        {"_id": doc["_id"]},
        {"$set": doc},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    print(f"[DB DEBUG] Upserted to MongoDB. Policies count: {len(result.get('policies', []))}")
    if result.get('policies'):
        print(f"[DB DEBUG] First policy has 'start_of_earliest_term': {'start_of_earliest_term' in result['policies'][0]}")
    return result

def list_reports() -> List[Dict[str, Any]]:
    col = _get_collection()
    if col is None:
        with _mock_lock:
            # omit full_text for listing
            return [ {k: v for k, v in doc.items() if k != "full_text"} for doc in sorted(_mock_store.values(), key=lambda d: d.get("_id")) ]
    return list(col.find({}, {"full_text": 0}).sort([("_id", 1)]))

def get_report(doc_id: str) -> Optional[Dict[str, Any]]:
    col = _get_collection()
    if col is None:
        return _mock_store.get(doc_id)
    return col.find_one({"_id": doc_id})

def delete_report(doc_id: str) -> bool:
    """Delete a report by ID. Returns True if deleted, False if not found."""
    col = _get_collection()
    if col is None:
        # in-memory fallback
        with _mock_lock:
            if doc_id in _mock_store:
                del _mock_store[doc_id]
                return True
            return False
    
    result = col.delete_one({"_id": doc_id})
    return result.deleted_count > 0
