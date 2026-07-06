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
import json
import datetime
from unittest.mock import MagicMock, AsyncMock, patch

from fastapi.testclient import TestClient
from google.genai import types

from app.fast_api_app import app, rate_limiter
from app.app_utils.db_service import (
    clear_sessions,
    clear_db_store,
    clear_outcomes,
    create_session,
    save_profile_document,
    get_profile_document,
    get_recorded_outcomes,
)
from app.app_utils.crypto import encrypt_payload

def make_mock_response(text: str) -> types.GenerateContentResponse:
    """Helper to construct a valid google-genai GenerateContentResponse."""
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=text)]
                ),
                finish_reason=types.FinishReason.STOP
            )
        ],
        model_version="gemini-flash-latest"
    )

@pytest.fixture
def mock_genai_client():
    """Mock the google-genai Client calls to run E2E offline."""
    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        
        async def mock_generate_content_async(model, contents, config=None, **kwargs):
            contents_str = str(contents)
            if "Conversation Assistant" in contents_str or "target_goal" in contents_str:
                return make_mock_response(json.dumps({
                    "recipient_mood_analysis": "Concerned about QA verification.",
                    "suggestions": [
                        {
                            "tone_label": "Collaborative (Recommended)",
                            "suggested_text": "I will send over the QA test reports.",
                            "rationalization": "Addresses his risk-averse trait."
                        },
                        {
                            "tone_label": "Firm / Analytical",
                            "suggested_text": "QA dashboard shows 98.5% coverage.",
                            "rationalization": "Leverages metrics."
                        }
                    ]
                }))
            elif "Persona Builder" in contents_str or "distill" in contents_str:
                return make_mock_response(json.dumps({
                    "contact_id": "contact_john_doe_99",
                    "metadata": {
                        "name": "John Doe",
                        "role": "VP of Infrastructure",
                        "last_updated": "2026-07-04T15:30:00Z"
                    },
                    "behavioral_traits": ["highly risk-averse", "meticulous"],
                    "viewpoints_and_positions": ["Prioritizes safety above deadlines."],
                    "negotiation_style": {
                        "primary_mode": "Avoiding / Competing",
                        "description": "Prone to shutting down.",
                        "concession_response": "Demands reciprocity."
                    },
                    "cognitive_biases_and_triggers": {
                        "primary_triggers": ["Loss Aversion"],
                        "details": "Highly sensitive to loss framing."
                    },
                    "decision_making_style": {
                        "cognitive_mode": "System 2 (Analytical)",
                        "evaluation_type": "Maximizer",
                        "description": "Requires data tables."
                    },
                    "interaction_preferences": {
                        "preferred_channel": "Asynchronous written",
                        "formatting": "Bulleted summaries",
                        "tone_sensitivity": "No hype"
                    }
                }))
            return make_mock_response("{}")
            
        mock_client.aio.models.generate_content = mock_generate_content_async
        mock_client.models.generate_content = lambda *a, **kw: make_mock_response("{}")
        yield mock_client


def test_auth_login():
    clear_sessions()
    with TestClient(app) as client:
        payload = {
            "user_email": "manager@company.com",
            "password_hash": "hashed_login_password",
            "encryption_key_passphrase": "passphrase_for_vault_decryption"
        }
        response = client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "session_token" in data
        assert "expires_at" in data
        assert data["session_token"].startswith("token_session_live_")


def test_suggest_endpoint(mock_genai_client):
    clear_sessions()
    rate_limiter.clear()
    
    # Pre-populate session token
    token = "token_session_live_abc123xyz789_c4b9"
    key = b"0" * 32
    create_session(token, key)
    
    with TestClient(app) as client:
        payload = {
            "session_token": token,
            "contact_id": "contact_john_doe_99",
            "target_goal": "Get John to approve extension.",
            "conversation_history": [{"sender": "user", "message": "Hi John"}]
        }
        response = client.post("/api/v1/assistant/suggest", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data
        assert len(data["suggestions"]) == 2
        assert data["recipient_mood_analysis"] == "Concerned about QA verification."


def test_suggest_unauthorized():
    clear_sessions()
    with TestClient(app) as client:
        payload = {
            "session_token": "token_session_live_abc123xyz789_c4b9", # checksum valid but not in cache
            "contact_id": "contact_john_doe_99",
            "target_goal": "Get John to approve extension.",
            "conversation_history": []
        }
        response = client.post("/api/v1/assistant/suggest", json=payload)
        assert response.status_code == 401
        assert "Session not found" in response.json()["detail"]


def test_suggest_rate_limit(mock_genai_client):
    clear_sessions()
    rate_limiter.clear()
    
    token = "token_session_live_abc123xyz789_c4b9"
    key = b"0" * 32
    create_session(token, key)
    
    with TestClient(app) as client:
        payload = {
            "session_token": token,
            "contact_id": "contact_john_doe_99",
            "target_goal": "Get John to approve extension.",
            "conversation_history": []
        }
        # Send 10 successful requests
        for _ in range(10):
            res = client.post("/api/v1/assistant/suggest", json=payload)
            assert res.status_code == 200
            
        # 11th request triggers 429
        res = client.post("/api/v1/assistant/suggest", json=payload)
        assert res.status_code == 429
        assert "Rate limit exceeded" in res.json()["detail"]


def test_distill_endpoint_queued(mock_genai_client):
    clear_sessions()
    rate_limiter.clear()
    clear_db_store()
    
    token = "token_session_live_abc123xyz789_c4b9"
    key = b"0" * 32
    create_session(token, key)
    
    contact_id = "contact_john_doe_99"
    save_profile_document(contact_id, {
        "contact_id": contact_id,
        "current_version": "v0",
        "snapshots": []
    })
    
    with TestClient(app) as client:
        payload = {
            "session_token": token,
            "contact_id": contact_id,
            "raw_conversation_transcript": [{"sender": "user", "message": "Deploy Friday"}]
        }
        response = client.post("/api/v1/builder/distill", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert "job_id" in data
        assert data["contact_id"] == contact_id


def test_rollback_endpoint(mock_genai_client):
    clear_sessions()
    clear_db_store()
    
    token = "token_session_live_abc123xyz789_c4b9"
    key = b"0" * 32
    create_session(token, key)
    
    contact_id = "contact_john_doe_99"
    profile_v1 = {"contact_id": contact_id, "negotiation_style": {"primary_mode": "Collaborating"}}
    profile_v2 = {"contact_id": contact_id, "negotiation_style": {"primary_mode": "Competing"}}
    
    encrypted_v1 = encrypt_payload(profile_v1, key)
    encrypted_v2 = encrypt_payload(profile_v2, key)
    
    doc = {
        "contact_id": contact_id,
        "current_version": "v2",
        "snapshots": [
            {
                "version_id": "v1",
                "timestamp": "2026-07-04T12:00:00Z",
                "changed_fields": [],
                "outcome_notes": "",
                "encrypted_profile": encrypted_v1
            },
            {
                "version_id": "v2",
                "timestamp": "2026-07-04T13:00:00Z",
                "changed_fields": [],
                "outcome_notes": "",
                "encrypted_profile": encrypted_v2
            }
        ],
        "active_profile_encrypted": encrypted_v2
    }
    save_profile_document(contact_id, doc)
    
    with TestClient(app) as client:
        payload = {
            "session_token": token,
            "contact_id": contact_id,
            "version_id": "v1"
        }
        response = client.post("/api/v1/profile/rollback", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["version_id"] == "v1"
        assert "rolled_back_at" in data
        
        # Verify db was updated
        doc_after = get_profile_document(contact_id)
        assert doc_after["current_version"] == "v1"
        assert doc_after["active_profile_encrypted"] == encrypted_v1


def test_negotiation_outcome_endpoint():
    clear_sessions()
    clear_outcomes()
    
    token = "token_session_live_abc123xyz789_c4b9"
    key = b"0" * 32
    create_session(token, key)
    
    with TestClient(app) as client:
        payload = {
            "session_token": token,
            "contact_id": "contact_john_doe_99",
            "goal_statement": "Get John to approve extension.",
            "outcome": "SUCCESS",
            "user_notes": "John approved it."
        }
        response = client.post("/api/v1/negotiation/outcome", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "session_id" in data
        assert "recorded_at" in data
        
        # Verify recorded in db service
        outcomes = get_recorded_outcomes()
        assert len(outcomes) == 1
        assert outcomes[0]["contact_id"] == "contact_john_doe_99"
        assert outcomes[0]["goal_statement"] == "Get John to approve extension."
        assert outcomes[0]["outcome"] == "SUCCESS"


def test_parameter_poisoning_validation():
    with TestClient(app) as client:
        # Send payload missing fields
        payload = {
            "user_email": "manager@company.com"
        }
        response = client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 422 # Pydantic validation error
