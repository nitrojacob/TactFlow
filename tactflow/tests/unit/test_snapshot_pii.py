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

import pytest
import os
from app.app_utils.snapshot_pii import SnapshotManager, strip_pii

def test_snapshot_creation():
    key = os.urandom(32)
    manager = SnapshotManager(key)
    
    db_doc = {
        "contact_id": "contact_john_doe_99",
        "current_version": "v0"
    }
    
    profile_v1 = {"contact_id": "contact_john_doe_99", "negotiation_style": {"primary_mode": "Collaborating"}}
    
    # Create first snapshot
    db_doc = manager.create_snapshot(db_doc, profile_v1, ["negotiation_style"], "Initial profile setup")
    assert db_doc["current_version"] == "v1"
    assert len(db_doc["snapshots"]) == 1
    assert db_doc["snapshots"][0]["version_id"] == "v1"
    assert db_doc["snapshots"][0]["changed_fields"] == ["negotiation_style"]
    assert db_doc["snapshots"][0]["outcome_notes"] == "Initial profile setup"
    
    # Verify active profile decodes correctly
    assert manager.decrypt_active_profile(db_doc) == profile_v1

def test_rollback_functionality():
    key = os.urandom(32)
    manager = SnapshotManager(key)
    
    db_doc = {
        "contact_id": "contact_john_doe_99",
        "current_version": "v0"
    }
    
    profile_v1 = {"contact_id": "contact_john_doe_99", "negotiation_style": {"primary_mode": "Collaborating"}}
    profile_v2 = {"contact_id": "contact_john_doe_99", "negotiation_style": {"primary_mode": "Competing"}}
    
    # Write v1
    db_doc = manager.create_snapshot(db_doc, profile_v1, ["negotiation_style"], "First version")
    assert db_doc["current_version"] == "v1"
    
    # Write v2
    db_doc = manager.create_snapshot(db_doc, profile_v2, ["negotiation_style"], "Second version")
    assert db_doc["current_version"] == "v2"
    assert manager.decrypt_active_profile(db_doc) == profile_v2
    assert len(db_doc["snapshots"]) == 2
    
    # Rollback to v1
    db_doc = manager.rollback(db_doc, "v1")
    assert db_doc["current_version"] == "v1"
    assert manager.decrypt_active_profile(db_doc) == profile_v1
    
    # Attempt rollback to non-existent version
    with pytest.raises(ValueError, match="Snapshot version v99 not found"):
        manager.rollback(db_doc, "v99")

def test_pii_stripping():
    # Test email stripping
    email_text = "My email is john@company.com. Please write back."
    assert strip_pii(email_text) == "My email is [REDACTED_EMAIL]. Please write back."
    
    # Test phone number stripping
    phone_text = "Reach me at +1-555-0199 or 555-0199."
    # The regex should replace both +1-555-0199 and 555-0199
    assert strip_pii(phone_text) == "Reach me at [REDACTED_PHONE] or [REDACTED_PHONE]."
    
    # Test name/sensitive terms stripping
    name_text = "John Doe is the VP of Infrastructure at Google."
    redacted = strip_pii(name_text, sensitive_names=["John Doe", "Google"])
    assert redacted == "[REDACTED_NAME] is the VP of Infrastructure at [REDACTED_NAME]."
    
    # Test empty / None input
    assert strip_pii("") == ""
    assert strip_pii(None) == ""
