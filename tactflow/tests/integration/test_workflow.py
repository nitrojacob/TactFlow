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

from google.adk.runners import InMemoryRunner
from google.adk.apps import App
from google.genai import types

from app.agent import app as adk_app
from app.app_utils.db_service import create_session, clear_sessions, get_profile_document, save_profile_document
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
        
        # Mock both sync and async generate_content
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

@pytest.mark.asyncio
async def test_suggest_route_e2e(mock_genai_client):
    clear_sessions()
    
    # 1. Setup session and keys
    token = "token_session_live_abc123xyz789_c4b9"
    key = b"0" * 32
    create_session(token, key)
    
    # 2. Run runner
    runner = InMemoryRunner(app=adk_app)
    session = await runner.session_service.create_session(
        app_name="app", user_id="test_user"
    )
    
    payload = {
        "request_type": "suggest",
        "session_token": token,
        "contact_id": "contact_john_doe_99",
        "target_goal": "Get John to approve the Friday deployment deadline extension.",
        "conversation_history": [
            {
                "sender": "user",
                "message": "Hi John, we need to push the deployment to Friday. Are you okay with that?"
            }
        ]
    }
    
    # Run the workflow
    output_event = None
    async for event in runner.run_async(
        user_id="test_user",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part.from_text(text=json.dumps(payload))]),
    ):
        if event.output is not None:
            output_event = event
            
    assert output_event is not None
    assert "suggestions" in output_event.output
    assert len(output_event.output["suggestions"]) == 2
    assert output_event.output["recipient_mood_analysis"] == "Concerned about QA verification."
    
    # State Integrity: Ensure decrypted profile never leaks in output
    assert "decrypted_profile" not in output_event.output
    assert "encryption_key" not in output_event.output

@pytest.mark.asyncio
async def test_distill_route_e2e(mock_genai_client):
    clear_sessions()
    
    token = "token_session_live_abc123xyz789_c4b9"
    key = b"0" * 32
    create_session(token, key)
    
    runner = InMemoryRunner(app=adk_app)
    session = await runner.session_service.create_session(
        app_name="app", user_id="test_user"
    )
    
    # Initial setup: save empty doc
    contact_id = "contact_john_doe_99"
    save_profile_document(contact_id, {
        "contact_id": contact_id,
        "current_version": "v0",
        "snapshots": []
    })
    
    payload = {
        "request_type": "distill",
        "session_token": token,
        "contact_id": contact_id,
        "raw_conversation_transcript": [
            {
                "sender": "user",
                "message": "We need to push this release to Friday."
            }
        ]
    }
    
    output_event = None
    async for event in runner.run_async(
        user_id="test_user",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part.from_text(text=json.dumps(payload))]),
    ):
        if event.output is not None:
            output_event = event
            
    assert output_event is not None
    assert output_event.output["status"] == "success"
    assert output_event.output["version_id"] == "v1"
    
    # Verify the document is committed in the mock database
    doc = get_profile_document(contact_id)
    assert doc["current_version"] == "v1"
    assert len(doc["snapshots"]) == 1

@pytest.mark.asyncio
async def test_rollback_route_e2e(mock_genai_client):
    clear_sessions()
    
    token = "token_session_live_abc123xyz789_c4b9"
    key = b"0" * 32
    create_session(token, key)
    
    # Setup document with snapshots having valid encrypted profiles
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
    
    runner = InMemoryRunner(app=adk_app)
    session = await runner.session_service.create_session(
        app_name="app", user_id="test_user"
    )
    
    payload = {
        "request_type": "rollback",
        "session_token": token,
        "contact_id": contact_id,
        "version_id": "v1"
    }
    
    output_event = None
    async for event in runner.run_async(
        user_id="test_user",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part.from_text(text=json.dumps(payload))]),
    ):
        if event.output is not None:
            output_event = event
            
    assert output_event is not None
    assert output_event.output["status"] == "success"
    assert output_event.output["version_id"] == "v1"
    
    # Verify the document is reverted in database
    doc_after = get_profile_document(contact_id)
    assert doc_after["current_version"] == "v1"
    assert doc_after["active_profile_encrypted"] == encrypted_v1
