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

import re
import datetime
from typing import List, Dict, Optional
from app.app_utils.crypto import encrypt_payload, decrypt_payload

class SnapshotManager:
    """Manager for version control, snapshotting, and rollback of contact profiles."""
    def __init__(self, key: bytes):
        self.key = key

    def create_snapshot(
        self,
        db_doc: dict,
        new_profile: dict,
        changed_fields: List[str],
        outcome_notes: str
    ) -> dict:
        """Create a new version snapshot and update active profile."""
        if "snapshots" not in db_doc:
            db_doc["snapshots"] = []
        if "current_version" not in db_doc or not db_doc["current_version"]:
            db_doc["current_version"] = "v0"

        # Determine next version id
        curr_v = db_doc["current_version"]
        try:
            version_num = int(curr_v.replace("v", ""))
        except ValueError:
            version_num = 0
        new_v = f"v{version_num + 1}"

        # Encrypt the new profile state
        encrypted_profile = encrypt_payload(new_profile, self.key)

        snapshot = {
            "version_id": new_v,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "changed_fields": changed_fields,
            "outcome_notes": outcome_notes,
            "encrypted_profile": encrypted_profile
        }

        db_doc["snapshots"].append(snapshot)
        db_doc["current_version"] = new_v
        db_doc["active_profile_encrypted"] = encrypted_profile
        return db_doc

    def rollback(self, db_doc: dict, target_version_id: str) -> dict:
        """Rollback active profile to a target snapshot version."""
        if "snapshots" not in db_doc or not db_doc["snapshots"]:
            raise ValueError("No snapshots found")

        target_snapshot = None
        for snap in db_doc["snapshots"]:
            if snap["version_id"] == target_version_id:
                target_snapshot = snap
                break

        if not target_snapshot:
            raise ValueError(f"Snapshot version {target_version_id} not found")

        db_doc["active_profile_encrypted"] = target_snapshot["encrypted_profile"]
        db_doc["current_version"] = target_version_id
        return db_doc

    def decrypt_active_profile(self, db_doc: dict) -> dict:
        """Decrypt and return the current active profile from the document."""
        if not db_doc.get("active_profile_encrypted"):
            raise ValueError("No active profile data found")
        return decrypt_payload(db_doc["active_profile_encrypted"], self.key)


def strip_pii(text: str, sensitive_names: Optional[List[str]] = None) -> str:
    """Filter out personal emails, phone numbers, and sensitive terms from text."""
    if not text:
        return ""

    # Replace emails
    email_pattern = r'\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]{2,}\b'
    text = re.sub(email_pattern, '[REDACTED_EMAIL]', text)

    # Replace phone numbers (checking for at least 7 digits to avoid false matches)
    phone_pattern = r'\+?\d{1,4}[-.\s]?\(?\d{1,3}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}'
    def replace_phone(match):
        val = match.group(0)
        digits = sum(1 for c in val if c.isdigit())
        if digits >= 7:
            return '[REDACTED_PHONE]'
        return val

    text = re.sub(phone_pattern, replace_phone, text)

    # Replace sensitive names
    if sensitive_names:
        for name in sensitive_names:
            pattern = r'\b' + re.escape(name) + r'\b'
            text = re.sub(pattern, '[REDACTED_NAME]', text, flags=re.IGNORECASE)

    return text
