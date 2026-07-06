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

import contextlib
import os
import datetime
import json
import uuid
import zlib
from collections.abc import AsyncIterator
from typing import List, Dict, Any

import google.auth
from a2a.server.tasks import InMemoryTaskStore
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import Runner
from google.cloud import logging as google_cloud_logging

from app.app_utils import services
from app.app_utils.a2a import attach_a2a_routes
from app.app_utils.telemetry import setup_telemetry
from app.app_utils.typing import Feedback
from app.app_utils.db_service import (
    RateLimiter,
    get_session_key,
    validate_key_checksum,
    create_session,
    record_outcome,
)

load_dotenv()
setup_telemetry()
_, project_id = google.auth.default()
logging_client = google_cloud_logging.Client()
logger = logging_client.logger(__name__)
allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else ["*"]
)

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ==========================================
# Pydantic Request Models
# ==========================================

class LoginRequest(BaseModel):
    user_email: str
    password_hash: str
    encryption_key_passphrase: str

class SuggestRequest(BaseModel):
    session_token: str
    contact_id: str
    target_goal: str
    conversation_history: List[Dict[str, Any]]

class DistillRequest(BaseModel):
    session_token: str
    contact_id: str
    raw_conversation_transcript: List[Dict[str, Any]]

class RollbackRequest(BaseModel):
    session_token: str
    contact_id: str
    version_id: str

class OutcomeRequest(BaseModel):
    session_token: str
    contact_id: str
    goal_statement: str
    outcome: str
    user_notes: str

class RetrieveProfileRequest(BaseModel):
    session_token: str
    contact_id: str


# Initialize rate limiter
rate_limiter = RateLimiter()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from app.agent import app as adk_app
    from app.agent import root_agent

    runner = Runner(
        app=adk_app,
        session_service=services.get_session_service(),
        artifact_service=services.get_artifact_service(),
        auto_create_session=True,
    )
    app.state.runner = runner
    app.state.agent_app_name = adk_app.name
    await attach_a2a_routes(
        app,
        agent=root_agent,
        runner=runner,
        task_store=InMemoryTaskStore(),
        rpc_path=f"/a2a/{adk_app.name}",
    )
    yield


app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    artifact_service_uri=services.ARTIFACT_SERVICE_URI,
    allow_origins=allow_origins,
    session_service_uri=services.SESSION_SERVICE_URI,
    otel_to_cloud=False,
    lifespan=lifespan,
)
app.title = "tactflow"
app.description = "API for interacting with the Agent tactflow"


# ==========================================
# REST Endpoints Mapping
# ==========================================

@app.post("/api/v1/auth/login")
def login(payload: LoginRequest):
    try:
        from app.app_utils.crypto import derive_key
        
        # Salt derived from user email
        salt = (payload.user_email + "tactflow_salt_padding").encode()
        derived_key = derive_key(payload.encryption_key_passphrase, salt)
        
        # Generate session token with valid CRC32 checksum
        rand = os.urandom(12).hex()
        checksum = f"{zlib.crc32(rand.encode()) & 0xffff:04x}"
        session_token = f"token_session_live_{rand}_{checksum}"
        
        # Store in cache (900 seconds = 15 minutes)
        create_session(session_token, derived_key, expire_seconds=900)
        
        # Pre-populate and encrypt default contact profile with the active derived key
        from app.app_utils.crypto import encrypt_payload
        from app.app_utils.db_service import save_profile_document
        
        contact_id = "contact_john_doe_99"
        profile_data = {
            "contact_id": contact_id,
            "metadata": {
                "name": "John Doe",
                "role": "VP of Infrastructure",
                "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat()
            },
            "behavioral_traits": ["highly risk-averse", "meticulous"],
            "viewpoints_and_positions": ["Prioritizes system stability and safety above release deadlines."],
            "negotiation_style": {
                "primary_mode": "Avoiding / Competing",
                "description": "Prone to shutting down conversations if pushed hard (Avoiding), but holds ground rigidly on safety standards (Competing).",
                "concession_response": "Demands strict reciprocity."
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
                "tone_sensitivity": "Highly averse to marketing hype"
            }
        }
        
        encrypted_profile = encrypt_payload(profile_data, derived_key)
        save_profile_document(contact_id, {
            "contact_id": contact_id,
            "current_version": "v1",
            "snapshots": [
                {
                    "version_id": "v1",
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "changed_fields": [],
                    "outcome_notes": "",
                    "encrypted_profile": encrypted_profile
                }
            ],
            "active_profile_encrypted": encrypted_profile
        })
        
        expires_at = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=900)).isoformat()
        
        return {
            "status": "success",
            "session_token": session_token,
            "expires_at": expires_at
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/assistant/suggest")
async def suggest(payload: SuggestRequest):
    # 1. Validate session token structure
    if not validate_key_checksum(payload.session_token):
        raise HTTPException(status_code=401, detail="Invalid session token checksum")
        
    # 2. Retrieve encryption key from cache
    try:
        get_session_key(payload.session_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
        
    # 3. Enforce rate limit (max 10 requests per minute)
    if not rate_limiter.check_rate_limit(payload.session_token, limit=10, window_seconds=60):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
    # 4. Invoke Consolidated ADK Workflow
    try:
        from google.genai import types
        
        runner = app.state.runner
        session = await runner.session_service.create_session(
            app_name=app.state.agent_app_name,
            user_id="anonymous"
        )
        
        wf_input = {
            "request_type": "suggest",
            "session_token": payload.session_token,
            "contact_id": payload.contact_id,
            "target_goal": payload.target_goal,
            "conversation_history": payload.conversation_history
        }
        
        output_event = None
        async for event in runner.run_async(
            user_id="anonymous",
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part.from_text(text=json.dumps(wf_input))]),
        ):
            if event.output is not None:
                output_event = event
                
        if output_event is None or not output_event.output:
            raise HTTPException(status_code=500, detail="Workflow failed to generate nudge suggestions")
            
        return output_event.output
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


async def run_background_distill(runner, session_id, wf_input):
    from google.genai import types
    try:
        async for event in runner.run_async(
            user_id="anonymous",
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part.from_text(text=json.dumps(wf_input))]),
        ):
            pass
    except Exception as e:
        logger.log_struct({"message": "Background distill failed", "error": str(e)}, severity="ERROR")


@app.post("/api/v1/builder/distill")
async def distill(payload: DistillRequest, background_tasks: BackgroundTasks):
    # 1. Validate session
    if not validate_key_checksum(payload.session_token):
        raise HTTPException(status_code=401, detail="Invalid session token checksum")
    try:
        get_session_key(payload.session_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
        
    # 2. Enforce rate limit (max 2 requests per minute)
    if not rate_limiter.check_rate_limit(payload.session_token, limit=2, window_seconds=60):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
    # 3. Start background job
    try:
        job_id = f"job_distill_{uuid.uuid4().hex[:8]}"
        runner = app.state.runner
        session = await runner.session_service.create_session(
            app_name=app.state.agent_app_name,
            user_id="anonymous"
        )
        
        wf_input = {
            "request_type": "distill",
            "session_token": payload.session_token,
            "contact_id": payload.contact_id,
            "raw_conversation_transcript": payload.raw_conversation_transcript
        }
        
        background_tasks.add_task(run_background_distill, runner, session.id, wf_input)
        
        return {
            "status": "queued",
            "job_id": job_id,
            "contact_id": payload.contact_id
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/profile/rollback")
async def rollback(payload: RollbackRequest):
    # 1. Validate session
    if not validate_key_checksum(payload.session_token):
        raise HTTPException(status_code=401, detail="Invalid session token checksum")
    try:
        get_session_key(payload.session_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
        
    # 2. Invoke consolidated workflow runner
    try:
        from google.genai import types
        
        runner = app.state.runner
        session = await runner.session_service.create_session(
            app_name=app.state.agent_app_name,
            user_id="anonymous"
        )
        
        wf_input = {
            "request_type": "rollback",
            "session_token": payload.session_token,
            "contact_id": payload.contact_id,
            "version_id": payload.version_id
        }
        
        output_event = None
        async for event in runner.run_async(
            user_id="anonymous",
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part.from_text(text=json.dumps(wf_input))]),
        ):
            if event.output is not None:
                output_event = event
                
        if output_event is None or not output_event.output or output_event.output.get("status") != "success":
            raise HTTPException(status_code=400, detail="Rollback failed")
            
        return {
            "status": "success",
            "version_id": payload.version_id,
            "rolled_back_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/profile/retrieve")
async def retrieve_profile(payload: RetrieveProfileRequest):
    # 1. Validate session
    if not validate_key_checksum(payload.session_token):
        raise HTTPException(status_code=401, detail="Invalid session token checksum")
    try:
        key = get_session_key(payload.session_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
        
    try:
        from app.app_utils.db_service import get_profile_document, save_profile_document
        from app.app_utils.crypto import decrypt_payload, encrypt_payload
        
        doc = get_profile_document(payload.contact_id)
        if not doc or not doc.get("active_profile_encrypted"):
            # Initialize default baseline profile for new counterpart on the fly
            default_profile = {
                "contact_id": payload.contact_id,
                "metadata": {
                    "name": payload.contact_id.replace("contact_", "").replace("_", " ").title(),
                    "role": "Counterpart",
                    "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat()
                },
                "behavioral_traits": [],
                "viewpoints_and_positions": [],
                "negotiation_style": {
                    "primary_mode": "Collaborating",
                    "description": "Default collaborating starting posture.",
                    "concession_response": "Responds positively to mutual value creation."
                },
                "cognitive_biases_and_triggers": {
                    "primary_triggers": [],
                    "details": "No known cognitive bias triggers."
                },
                "decision_making_style": {
                    "cognitive_mode": "System 1",
                    "evaluation_type": "Satisficer",
                    "description": "Standard processing mode."
                },
                "interaction_preferences": {
                    "preferred_channel": "Asynchronous written",
                    "formatting": "Direct summary",
                    "tone_sensitivity": "Professional"
                }
            }
            encrypted_profile = encrypt_payload(default_profile, key)
            doc = {
                "contact_id": payload.contact_id,
                "current_version": "v1",
                "snapshots": [
                    {
                        "version_id": "v1",
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "changed_fields": ["initialization"],
                        "outcome_notes": "Automated on-demand profile initialization",
                        "encrypted_profile": encrypted_profile
                    }
                ],
                "active_profile_encrypted": encrypted_profile
            }
            save_profile_document(payload.contact_id, doc)
            
        decrypted = decrypt_payload(doc["active_profile_encrypted"], key)
        return {
            "status": "success",
            "profile": decrypted,
            "current_version": doc.get("current_version", "v1")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/negotiation/outcome")
def negotiation_outcome(payload: OutcomeRequest):
    # 1. Validate session
    if not validate_key_checksum(payload.session_token):
        raise HTTPException(status_code=401, detail="Invalid session token checksum")
    try:
        get_session_key(payload.session_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
        
    # 2. Record the outcome details directly to database
    try:
        outcome_data = {
            "goal_statement": payload.goal_statement,
            "outcome": payload.outcome,
            "user_notes": payload.user_notes,
            "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        record_outcome(payload.contact_id, outcome_data)
        
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        
        return {
            "status": "success",
            "session_id": session_id,
            "recorded_at": outcome_data["recorded_at"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    """Collect and log feedback."""
    logger.log_struct(feedback.model_dump(), severity="INFO")
    return {"status": "success"}


# Main execution
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
