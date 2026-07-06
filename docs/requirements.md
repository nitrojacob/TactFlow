# Requirements Specification: TactFlow

This document defines the functional, performance, and security requirements for the TactFlow agent system. To minimize latency, operational cost, and internal communication overhead, the system implements a **Consolidated ADK 2.0 Workflow Graph** architecture where the Database Agent, Persona Builder, and Conversation Assistant run within the same containerized service process and communicate in-memory using shared state.

---

## 1. System-Wide Architecture Requirements

### 1.1 Consolidated Graph Model
- **In-Memory Communication**: All agent-to-agent (a2a) and database agent integrations must run within a single compiled `Workflow` graph. There shall be no internal HTTP/REST API calls between agents (e.g., `GET /internal/v1/profile` over VPC is eliminated).
- **Session State Sharing**: Data such as decrypted contact profiles, session metadata, and parsed inputs must be passed through the ADK `Context.state` dictionary rather than being serialized over network sockets.
- **Unified Compute Instance**: The entire workflow graph must compile into a single FastAPI/ADK container deployed to Google Cloud Run, supporting scaling to zero and concurrency.

### 1.2 Strict Server-Side Boundary
- **Zero-Exposure Policy**: Under no circumstances shall raw decrypted persona profiles, behavioral traits, viewpoints, or triggers be returned in public API payloads.
- **Client Session Isolation**: The client application (frontend) shall only receive short-lived session tokens and processed suggestion lists.

### 1.3 Ingress Rate-Limiting (Anti-DoS)
- **Middleware Rate-Limiter**: Enforce strict rate limits at the FastAPI request receiver layer before calling any database decryption or LLM generation nodes.
- **Quota Budgets**: Limit resource-heavy endpoints to prevent Denial of Service cost spikes (e.g., maximum 10 suggestion requests per minute and 2 distillation requests per minute per authenticated session token/IP).

### 1.4 Strict Input Schema Validation
- **Pydantic Validation**: Implement strict Pydantic schemas on all public FastAPI endpoints to reject malformed data types, parameter manipulation, or unexpected keys before routing to the workflow execution engine.


---

## 2. Database Agent Requirements (Deterministic)

The Database Agent is a deterministic (non-LLM) set of functions and class methods integrated directly into the workflow graph as tools/nodes.

### 2.1 Functional Requirements
- **Session & Key Derivation**: 
  - Upon receiving authentication requests (`/api/v1/auth/login`), derive the database encryption key from the user's passphrase.
  - Generate a secure, short-lived session token containing a signature or checksum.
  - Cache the derived key in secure, process-level in-memory storage, associated with the session token.
- **Secure Read Access**:
  - Intercept incoming request payloads, validate the session token, and retrieve the encrypted counterpart profile.
  - Decrypt the profile using the session key and load it into the graph's `Context.state` for use by downstream LLM nodes.
- **Secure Write Access**:
  - Accept updated profile structures from the Persona Builder node.
  - Encrypt the profile JSON before writing to the persistent database (Firestore or Cloud SQL).
- **PII Stripping & Logging**:
  - Scan and strip all Personally Identifiable Information (PII) such as personal emails, phone numbers, exact addresses, and client-sensitive names from standard application logs.
- **Version Control & Rollback (Git-like)**:
  - Every profile write must increment a version ID (e.g., `v1`, `v2`, `v3`).
  - Store a chronological changelog snapshot containing the timestamp, changed fields, outcome notes, and a copy of the encrypted profile state.
  - Support reverting a profile to a specific version ID upon verifying a valid session token and rollback request.

### 2.2 Performance Requirements
- **Token Verification Latency**: Deterministic token check and key validation must execute in `< 5ms`.
- **Read & Decrypt Latency**: Profile retrieval and decryption must execute in `< 50ms`.

### 2.3 Security Requirements
- **Key Isolation**: Session keys must remain strictly in-memory (never written to disk or logged).
- **Cryptographic Standards**: Use AES-256-GCM for profile payload encryption/decryption.

---

## 3. Persona Builder Agent Requirements (LLM-based)

The Persona Builder is an LLM-driven node in the workflow graph that processes raw logs to extract and refine contact profiles.

### 3.1 Functional Requirements
- **Linguistic Marker Extraction**:
  - Parse raw conversation transcripts for linguistic cues, grammatical complexity, and specific keywords to identify decision-making modes (System 1/System 2), evaluation styles (Maximizer/Satisficer), TKI conflict modes, and nudge triggers.
- **Profile Generation & Updates**:
  - Map extracted observations into the refined database schema fields (`behavioral_traits`, `viewpoints_and_positions`, `negotiation_style`, `cognitive_biases_and_triggers`, `decision_making_style`, `interaction_preferences`).
- **Temporal Weighting**:
  - Apply higher mathematical weighting (e.g., 70% weight) to recent logs (last 3 transcripts) over older historical profiles during trait updates.
- **Conflict Resolution**:
  - If new observations contradict historical profile data, do not wipe viewpoints. Append them as context-specific rules (e.g., "Maintains competitive posture regarding budget decisions but collaborates on timeline adjustments").

### 3.2 Performance & Quality Requirements
- **Execution Time**: Parsing and profile distillation should complete in `< 15s`.
- **Extraction Accuracy**: Structured profiles must achieve an `85%` or higher alignment score against expert-annotated validation datasets.
- **Hallucination Control**: Extracted behavioral traits and viewpoints must be directly traceable to specific text statements in the raw input transcripts.

---

## 4. Conversation Assistant Agent Requirements (LLM-based)

The Conversation Assistant is a fast, turn-by-turn LLM-driven node in the workflow graph that generates strategic phrasing suggestions.

### 4.1 Functional Requirements
- **Profile-Primed Suggestions**:
  - Retrieve the decrypted counterpart profile from the graph state.
  - Inject the counterpart's traits, preferred tone, and negotiation style into the LLM system prompt instructions.
- **Multi-Tone Output Generation**:
  - Generate exactly two suggestions with distinct strategic focus:
    1. **Collaborative (Recommended)**: Focused on win-win alignment, addressing interests, and building rapport.
    2. **Firm / Analytical**: Focused on direct logical proof, data metrics, and rigid boundaries.
- **Goal Alignment**:
  - Frame suggestions directly to steer the conversation toward the user's `target_goal`.
- **Nudge Framing**:
  - Apply tailored behavioral economics nudges based on the counterpart's profile triggers (e.g., framing suggestions in terms of "risk reduction" for highly Loss-Averse counterparts, or using "bulleted metrics" for Maximizers).
- **Zero-Leak Output Constraint**:
  - Suggestions must not mention, reference, or leak raw psychological classifications (e.g., "Thomas-Kilmann Competing mode"), specific behavioral trait tags, or viewpoints in the text shown to the user.


### 4.2 Performance & Quality Requirements
- **End-to-End Latency**: The turn-by-turn suggest flow (`POST /api/v1/assistant/suggest`) must return suggestions in `< 2.5s` (including API gateway traversal).
- **Tone Adherence**: Suggestions must score `90%` or higher on adherence to the counterpart's preferred communication channels and tone sensitivities.
- **Safety**: Generated texts must be strictly professional, non-confrontational, and free of hostile language.
