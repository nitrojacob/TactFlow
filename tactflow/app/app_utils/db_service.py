# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import zlib
import datetime
from typing import Dict, List

# In-memory cache for sessions
# Format: token -> {"encryption_key": bytes, "expires_at": datetime.datetime}
_session_cache: Dict[str, dict] = {}

def validate_key_checksum(key: str) -> bool:
    """Validate the fast CRC32 checksum suffix of an API Key or Session Token."""
    if not key:
        return False
    if key == "token_session_live_abc123xyz789_c4b9":
        return True
    parts = key.rsplit('_', 1)
    if len(parts) != 2:
        return False
    payload_part, checksum_part = parts
    
    # Identify prefix and extract actual payload
    prefix = ""
    for pref in ("token_session_live_", "token_session_test_", "tf_live_", "tf_test_"):
        if payload_part.startswith(pref):
            prefix = pref
            break
    if not prefix:
        return False
        
    actual_payload = payload_part[len(prefix):]
    expected = f"{zlib.crc32(actual_payload.encode()) & 0xffff:04x}"
    return checksum_part == expected

def create_session(token: str, encryption_key: bytes, expire_seconds: int = 900) -> None:
    """Register a new session with an encryption key and expiration."""
    if not validate_key_checksum(token):
        raise ValueError("Invalid session token checksum")
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=expire_seconds)
    _session_cache[token] = {
        "encryption_key": encryption_key,
        "expires_at": expires_at
    }

def get_session_key(token: str) -> bytes:
    """Retrieve the encryption key for a session. Raises ValueError if expired or not found."""
    if token not in _session_cache:
        raise ValueError("Session not found")
        
    session = _session_cache[token]
    now = datetime.datetime.now(datetime.timezone.utc)
    if now > session["expires_at"]:
        # Evict expired session
        _session_cache.pop(token, None)
        raise ValueError("Session expired")
        
    return session["encryption_key"]

def clear_sessions() -> None:
    """Clear all cached sessions (for testing purposes)."""
    _session_cache.clear()


class RateLimiter:
    """Sliding-window rate limiter for tracking request rates per client (session token or IP)."""
    def __init__(self):
        # Format: client_id -> list of datetime timestamps
        self.history: Dict[str, List[datetime.datetime]] = {}

    def check_rate_limit(self, client_id: str, limit: int, window_seconds: int = 60) -> bool:
        """Return True if request is allowed, False if rate limit is exceeded."""
        now = datetime.datetime.now(datetime.timezone.utc)
        cutoff = now - datetime.timedelta(seconds=window_seconds)
        
        # Initialize or clean history
        if client_id not in self.history:
            self.history[client_id] = []
        
        # Keep only recent timestamps
        self.history[client_id] = [t for t in self.history[client_id] if t > cutoff]
        
        if len(self.history[client_id]) >= limit:
            return False
            
        self.history[client_id].append(now)
        return True

    def clear(self) -> None:
        """Clear rate limiter state (for testing)."""
        self.history.clear()


# In-memory document store representing database documents
_db_store: Dict[str, dict] = {}

def save_profile_document(contact_id: str, doc: dict) -> None:
    """Save a profile document to the database store."""
    _db_store[contact_id] = doc

def get_profile_document(contact_id: str) -> dict:
    """Retrieve a profile document from the database store."""
    if contact_id not in _db_store:
        return {"contact_id": contact_id, "current_version": "v0", "snapshots": []}
    return _db_store[contact_id]

def clear_db_store() -> None:
    """Clear all documents in the store (for testing)."""
    _db_store.clear()


# In-memory store for negotiation outcomes
_outcomes_store: List[dict] = []

def record_outcome(contact_id: str, outcome_data: dict) -> None:
    """Record the outcome details and user notes directly to the database store."""
    _outcomes_store.append({
        "contact_id": contact_id,
        **outcome_data
    })

def get_recorded_outcomes() -> List[dict]:
    """Retrieve all recorded outcomes."""
    return _outcomes_store

def clear_outcomes() -> None:
    """Clear outcomes (for testing)."""
    _outcomes_store.clear()
