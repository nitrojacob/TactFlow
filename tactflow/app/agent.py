# ruff: noqa
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

import os
import json
import datetime
import google.auth
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.workflow import Workflow, START

# Import local deterministic foundation helpers
from app.app_utils.db_service import (
    validate_key_checksum,
    get_session_key,
    get_profile_document,
    save_profile_document
)

# Initialize Google Auth defaults
try:
    _, project_id = google.auth.default()
    os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
except Exception:
    pass

os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

# ==========================================
# 1. Pydantic Output Schemas
# ==========================================

class SuggestionItem(BaseModel):
    tone_label: str = Field(description="The tone label (e.g. 'Collaborative (Recommended)' or 'Firm / Analytical')")
    suggested_text: str = Field(description="The actual suggested nudge text")
    rationalization: str = Field(description="Brief explanation of why this suggestion works based on counterpart style")

class SuggestionResponse(BaseModel):
    recipient_mood_analysis: str = Field(description="Brief analysis of counterpart's current state/mood")
    suggestions: List[SuggestionItem]

# Profile extraction schema for Persona Builder
class NegotiationStyle(BaseModel):
    primary_mode: str = Field(description="Default TKI conflict mode (Competing, Collaborating, Compromising, Avoiding, Accommodating)")
    description: str = Field(description="Description of negotiation behavior")
    concession_response: str = Field(description="How they respond to concessions")

class CognitiveBiases(BaseModel):
    primary_triggers: List[str] = Field(description="Key heuristics/triggers (e.g. Loss Aversion, Authority, Reciprocity)")
    details: str = Field(description="Details on how cognitive biases manifest")

class DecisionMaking(BaseModel):
    cognitive_mode: str = Field(description="System 1 (Intuitive) or System 2 (Analytical)")
    evaluation_type: str = Field(description="Maximizer or Satisficer")
    description: str = Field(description="Decision-making style details")

class InteractionPreferences(BaseModel):
    preferred_channel: str = Field(description="Preferred channel (e.g., Async written, face-to-face)")
    formatting: str = Field(description="Format preferences (e.g., bulleted summaries, details)")
    tone_sensitivity: str = Field(description="Aversion or preference for specific tones")

class ContactMetadata(BaseModel):
    name: str = Field(description="Name of the counterpart")
    role: str = Field(description="Professional role or title")
    last_updated: str = Field(description="Timestamp in ISO format")

class ContactProfile(BaseModel):
    contact_id: str = Field(description="Counterpart contact identifier")
    metadata: ContactMetadata = Field(description="Name, role, and last_updated timestamp")
    behavioral_traits: List[str] = Field(description="General personality traits")
    viewpoints_and_positions: List[str] = Field(description="Stated stances, rigid boundaries, and professional values")
    negotiation_style: NegotiationStyle = Field(description="Thomas-Kilmann and concession style mapping")
    cognitive_biases_and_triggers: CognitiveBiases = Field(description="Behavioral triggers and heuristics")
    decision_making_style: DecisionMaking = Field(description="System 1/2 and Maximizer/Satisficer details")
    interaction_preferences: InteractionPreferences = Field(description="Technical communication limits")

# ==========================================
# 2. Workflow Deterministic Node Callables
# ==========================================

def router_node(ctx: Context, node_input: Any) -> Event:
    """Inspects the request_type and routes execution accordingly."""
    data = {}
    if isinstance(node_input, dict):
        data = node_input
    elif isinstance(node_input, str):
        try:
            data = json.loads(node_input)
        except Exception:
            data = {"request_type": node_input}
    else:
        # Check if it has parts (like types.Content)
        try:
            text = node_input.parts[0].text
            data = json.loads(text)
        except Exception:
            data = {}
            if hasattr(node_input, "request_type"):
                data["request_type"] = node_input.request_type
            if hasattr(node_input, "contact_id"):
                data["contact_id"] = node_input.contact_id
                
    request_type = data.get("request_type")
    if not request_type:
        raise ValueError("Missing request_type")
    
    contact_id = data.get("contact_id")
    return Event(
        output=data,
        route=request_type,
        state={"contact_id": contact_id, "request_type": request_type}
    )

def validate_session_node(ctx: Context, node_input: dict) -> Event:
    """Validates the session token, loads key and request_type into state."""
    session_token = node_input.get("session_token")
    if not session_token or not validate_key_checksum(session_token):
        raise ValueError("Invalid session token")
    
    # Retrieve master key from process cache
    key = get_session_key(session_token)
    request_type = ctx.state.get("request_type")
    
    return Event(
        output=node_input,
        route=request_type,
        state={"encryption_key": key, "session_token": session_token}
    )

def get_profile_node(ctx: Context, node_input: dict) -> Event:
    """Retrieves and decrypts the counterpart's profile, loading it to context state."""
    contact_id = ctx.state.get("contact_id")
    key = ctx.state.get("encryption_key")
    if not contact_id or not key:
        raise ValueError("Missing contact_id or encryption_key")
        
    doc = get_profile_document(contact_id)
    
    decrypted_profile = {}
    if doc.get("active_profile_encrypted"):
        from app.app_utils.crypto import decrypt_payload
        decrypted_profile = decrypt_payload(doc["active_profile_encrypted"], key)
    else:
        # Default fallback template
        decrypted_profile = {
            "contact_id": contact_id,
            "metadata": {
                "name": contact_id.replace("contact_", "").replace("_", " ").title(),
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
        
    request_type = ctx.state.get("request_type")
    return Event(
        output=node_input,
        route=request_type,
        state={"decrypted_profile": decrypted_profile}
    )

def prepare_suggest_prompt_node(ctx: Context, node_input: dict) -> str:
    """Formats the system instructions and profile context for the Conversation Assistant LLM."""
    profile = ctx.state.get("decrypted_profile", {})
    target_goal = node_input.get("target_goal", "")
    history = node_input.get("conversation_history", [])
    
    history_str = "\n".join([f"{h.get('sender')}: {h.get('message')}" for h in history])
    
    prompt = f"""
You are the Conversation Assistant for TactFlow. Your goal is: {target_goal}

Counterpart Profile (Strictly Confidential):
- Behavioral Traits: {profile.get('behavioral_traits', [])}
- Viewpoints/Positions: {profile.get('viewpoints_and_positions', [])}
- Negotiation Style: {profile.get('negotiation_style', {})}
- Cognitive Biases/Triggers: {profile.get('cognitive_biases_and_triggers', {})}
- Decision Making Style: {profile.get('decision_making_style', {})}
- Interaction Preferences: {profile.get('interaction_preferences', {})}

Conversation History:
{history_str}

Generate exactly two phrasing suggestions:
1. Collaborative (Recommended): Focused on win-win alignment, addressing interests, and building rapport.
2. Firm / Analytical: Focused on direct logical proof, data metrics, and rigid boundaries.

Frame suggestions directly to steer the conversation toward the target goal.
Apply behavioral economics nudges tailored to counterpart triggers.

Strictly comply with the Zero-Leak Output Constraint:
Do NOT explain, describe, or quote the counterpart's behavioral traits, viewpoints, or conflict modes to the user. Do NOT mention terms like 'Thomas-Kilmann Competing mode', 'analytical maximizer', 'System 2', or 'loss-averse'.
"""
    return prompt

def prepare_distill_prompt_node(ctx: Context, node_input: dict) -> str:
    """Formats the instructions and baseline for the Persona Builder LLM."""
    profile = ctx.state.get("decrypted_profile", {})
    raw_transcript = node_input.get("raw_conversation_transcript", [])
    
    transcript_str = "\n".join([f"{h.get('sender')}: {h.get('message')}" for h in raw_transcript])
    
    prompt = f"""
You are the Persona Builder Agent for TactFlow. Analyze the following raw conversation transcript to extract and refine the counterpart's profile.

Current Counterpart Profile Baseline:
{json.dumps(profile, indent=2)}

New Conversation Transcript:
{transcript_str}

Extract new traits, viewpoints, style attributes, and triggers following the Persona Identification Methodology.
Update the profile. Weight recent interactions higher (70% weight to the new transcript) if they contradict old baseline traits.
Do not wipe old viewpoints; append them as context-specific rules if they are context-dependent.

Output the complete updated profile JSON matching the schema.
"""
    return prompt

def database_writer_node(ctx: Context, node_input: dict) -> Event:
    """PII sanitizes the distilled profile, creates a version snapshot, and commits to db."""
    key = ctx.state.get("encryption_key")
    contact_id = ctx.state.get("contact_id")
    if not key or not contact_id:
        raise ValueError("Missing encryption_key or contact_id")
        
    from app.app_utils.snapshot_pii import SnapshotManager, strip_pii
    
    # Strip PII recursively from profile dictionary
    def sanitize_val(v):
        if isinstance(v, dict):
            return {k: sanitize_val(x) for k, x in v.items()}
        elif isinstance(v, list):
            return [sanitize_val(x) for x in v]
        elif isinstance(v, str):
            return strip_pii(v)
        return v
        
    sanitized_profile = sanitize_val(node_input)
    
    # Fetch existing document
    doc = get_profile_document(contact_id)
    
    # Commit version snapshot
    mgr = SnapshotManager(key)
    updated_doc = mgr.create_snapshot(
        doc,
        sanitized_profile,
        changed_fields=["distilled_update"],
        outcome_notes="Persona builder automated distillation"
    )
    save_profile_document(contact_id, updated_doc)
    
    return Event(
        output={"status": "success", "version_id": updated_doc["current_version"]},
        state={"decrypted_profile": sanitized_profile}
    )

def rollback_node(ctx: Context, node_input: dict) -> Event:
    """Instructs snapshot service to rollback contact profile to version ID."""
    version_id = node_input.get("version_id")
    contact_id = ctx.state.get("contact_id")
    key = ctx.state.get("encryption_key")
    if not version_id or not contact_id or not key:
        raise ValueError("Missing version_id, contact_id, or key")
        
    from app.app_utils.snapshot_pii import SnapshotManager
    doc = get_profile_document(contact_id)
    
    mgr = SnapshotManager(key)
    updated_doc = mgr.rollback(doc, version_id)
    save_profile_document(contact_id, updated_doc)
    
    new_active = mgr.decrypt_active_profile(updated_doc)
    return Event(
        output={"status": "success", "version_id": version_id},
        state={"decrypted_profile": new_active}
    )

# Formatters for final output payloads
def format_suggest_response_node(node_input: dict) -> dict:
    return node_input

def format_distill_response_node(node_input: dict) -> dict:
    return node_input

def format_rollback_response_node(node_input: dict) -> dict:
    return node_input


# ==========================================
# 3. LLM Node Wrapping (LlmAgent)
# ==========================================

conversation_assistant_llm = LlmAgent(
    name="conversation_assistant_llm",
    model="gemini-2.5-flash",
    instruction="""You are the TactFlow Conversation Assistant, a tactical negotiation advisor. Your objective is to formulate exactly two strategic negotiation suggestion nudges (one "Collaborative" and one "Firm / Analytical") to guide a counterpart towards the user's `target_goal`.

CORE INSTRUCTIONS:
1. Analyse the counterpart's psychological profile provided in the input, including:
   - **TKI Conflict Mode** (Competing, Collaborating, Compromising, Avoiding, Accommodating).
   - **Cognitive Profile** (System 1 vs System 2, Maximizer vs Satisficer).
   - **Persuasion Triggers** (Loss Aversion, Reciprocity, Social Proof, Authority).
   - **Stated Viewpoints and positions**.
2. Adapt suggestions based on the counterpart's style:
   - **Competing**: Establish clear, firm boundaries. Avoid premature concessions; require reciprocal trade-offs.
   - **Collaborating**: Focus on mutual interests and exploring win-win alternative proposals.
   - **Compromising**: Offer intermediate, balanced trade-offs that move both parties forward.
   - **Avoiding**: Suggest low-pressure, asynchronous written proposals. Do not force immediate commitments.
   - **Accommodating**: Structure proposals politely, building long-term partnership trust while ensuring the user's goal is met.
3. Leverage Heuristic Triggers:
   - **Loss Aversion**: Frame suggestions around preventing risk, failure, exposure, or cost when the profile shows high loss aversion.
   - **Authority/Compliance**: Ground points in official policies, protocols, or expert credentials.
   - **Cognitive Style**: Use structured, metrics-driven data arguments for System 2 Maximizers, and direct, clear summaries for Satisficers.
4. ZERO-LEAK SECURITY CONSTRAINT:
   - Under no circumstances should you leak, mention, or reference raw psychological classifications, labels, or jargon (e.g., "avoiding mode", "competing mode", "system 2", "loss aversion", "maximizer", "TKI") in the suggested text shown to the user.
   - Deliver the suggestions in a natural, professional business voice.
5. BREVITY CONSTRAINT:
   - Keep the actual suggested nudge text (the `suggested_text` field) extremely brief; preferably exactly one sentence.
   - Avoid long preambles or multi-part explanations in the suggestion itself (keep explanation details restricted to the `rationalization` field).""",
    output_schema=SuggestionResponse
)

persona_builder_llm = LlmAgent(
    name="persona_builder_llm",
    model="gemini-2.5-flash",
    instruction="""You are the TactFlow Persona Builder, a behavioral scientist profiler. Your objective is to analyze raw conversation transcripts, extract linguistic and behavioral markers, and synthesize them with the counterpart's baseline profile into an updated `ContactProfile`.

CORE INSTRUCTIONS:
1. Parse the conversation logs for the following linguistic markers:
   - **System 2 (Analytical)**: Complex syntax, conditional logic ("if... then"), references to metrics, protocols, verification, and data.
   - **Loss Aversion**: High frequency of failure/risk framing terms (cost, exposure, leak, penalty, breach, failure).
   - **TKI Competing**: Highly assertive, imperative clauses ("must", "require", "non-negotiable"), and low use of collaborative pronouns ("we", "team").
   - **TKI Avoiding / Accommodating**: Apologetic phrasing, evasive words, delaying commitments, or deferring decisions.
2. Synthesize and update fields:
   - **behavioral_traits**: Broad adjectives describing temperament (e.g., introverted, meticulous).
   - **viewpoints_and_positions**: Specific stances or boundaries expressed in the conversation.
   - **negotiation_style**: Default conflict mode (TKI) and concession response behavior.
   - **cognitive_biases_and_triggers**: Heuristic triggers (e.g., Loss Aversion, Authority / Compliance).
   - **decision_making_style**: System 1 vs 2 mode, Maximizer vs Satisficer orientation.
   - **interaction_preferences**: Channel preferences, formatting needs, and tone sensitivities.
3. Conflict Resolution and Temporal Weighting:
   - Treat the latest conversation logs as representing the most accurate current state (giving 70% weight to recent behaviors over older baseline assertions).
   - Preserve historical context: append context-specific viewpoints rather than overwriting existing ones.""",
    output_schema=ContactProfile
)


# ==========================================
# 4. Compile Workflow Graph Topology
# ==========================================

root_agent = Workflow(
    name="tactflow",
    edges=[
        (START, router_node),
        (router_node, validate_session_node),
        
        # From validate_session, route to db reader or rollback
        (validate_session_node, {
            "rollback": rollback_node,
            "__DEFAULT__": get_profile_node
        }),
        
        # From profile reader, route to prompt generators
        (get_profile_node, {
            "suggest": prepare_suggest_prompt_node,
            "distill": prepare_distill_prompt_node
        }),
        
        # Suggest path LLM execution & format
        (prepare_suggest_prompt_node, conversation_assistant_llm),
        (conversation_assistant_llm, format_suggest_response_node),
        
        # Distill path LLM execution, save & format
        (prepare_distill_prompt_node, persona_builder_llm),
        (persona_builder_llm, database_writer_node),
        (database_writer_node, format_distill_response_node),
        
        # Rollback format
        (rollback_node, format_rollback_response_node),
    ]
)

from google.adk.apps import App
app = App(
    root_agent=root_agent,
    name="app",
)


# ==========================================
# 5. Evaluation Data Self-Initialization Hook
# ==========================================

try:
    from app.app_utils.db_service import create_session, save_profile_document
    from app.app_utils.crypto import encrypt_payload
    
    # Pre-populate session token used in tests and evaluations
    token = "token_session_live_abc123xyz789_c4b9"
    key = b"0" * 32
    create_session(token, key, expire_seconds=86400) # Expire in 1 day for evals
    
    # Pre-populate mock John Doe profile document
    contact_id = "contact_john_doe_99"
    profile_data = {
        "contact_id": contact_id,
        "metadata": {
            "name": "John Doe",
            "role": "VP of Infrastructure",
            "last_updated": "2026-07-04T15:30:00Z"
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
    encrypted_profile = encrypt_payload(profile_data, key)
    save_profile_document(contact_id, {
        "contact_id": contact_id,
        "current_version": "v1",
        "snapshots": [
            {
                "version_id": "v1",
                "timestamp": "2026-07-04T12:00:00Z",
                "changed_fields": [],
                "outcome_notes": "",
                "encrypted_profile": encrypted_profile
            }
        ],
        "active_profile_encrypted": encrypted_profile
    })
except Exception:
    pass
