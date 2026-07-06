# Interface Specification & JSON Schemas: TactFlow

This document acts as the single source of truth for all JSON-based data structures and API payloads used within TactFlow's microservice architecture. 

To prevent leaking sensitive persona assets, **all raw decrypted profiles remain strictly behind the server-side boundary**. The client application (frontend) communicates using temporary session tokens and never receives the raw profile database fields.

---

## 1. Database Schema: Contact Profile (Internal Server-Side Only)

This JSON structure represents a decrypted contact profile stored in the encrypted database managed by the **DB Agent**. It is never returned to the client frontend.

```json
{
  "contact_id": "contact_john_doe_99",
  "metadata": {
    "name": "John Doe",
    "role": "VP of Infrastructure",
    "last_updated": "2026-07-04T15:30:00Z"
  },
  "behavioral_traits": [
    "highly risk-averse",
    "meticulous",
    "skeptical of rapid changes"
  ],
  "viewpoints_and_positions": [
    "Prioritizes system stability and safety above release deadlines.",
    "Believes manual QA audits are superior to fully automated testing pipelines."
  ],
  "negotiation_style": {
    "primary_mode": "Avoiding / Competing",
    "description": "Prone to shutting down conversations if pushed hard (Avoiding), but holds ground rigidly on safety standards (Competing).",
    "concession_response": "Demands strict reciprocity; rarely gives concessions without receiving one first."
  },
  "cognitive_biases_and_triggers": {
    "primary_triggers": ["Loss Aversion", "Authority / Compliance"],
    "details": "Highly sensitive to loss framing (e.g. risk of system failure). Defers to written compliance protocols and regulatory frameworks."
  },
  "decision_making_style": {
    "cognitive_mode": "System 2 (Analytical)",
    "evaluation_type": "Maximizer",
    "description": "Requires exhaustive, structured data tables and direct comparisons. Unmoved by emotional or relationship-based pitches."
  },
  "interaction_preferences": {
    "preferred_channel": "Asynchronous written (Email / Slack)",
    "formatting": "Bulleted summaries, direct charts, no fluff",
    "tone_sensitivity": "Highly averse to marketing hype, sales language, or emotional pleading"
  }
}
```

---

## 2. Public API Endpoints (Client to Gateway)

These endpoints are exposed to the client application and require a valid, active `session_token`.

### A. Authentication & Session Setup

#### `POST /api/v1/auth/login`
Authenticates the user and derives the in-memory decryption key. Returns a temporary session token.
*   **Request Payload**:
    ```json
    {
      "user_email": "manager@company.com",
      "password_hash": "hashed_login_password",
      "encryption_key_passphrase": "passphrase_for_vault_decryption"
    }
    ```
*   **Response Payload**:
    ```json
    {
      "status": "success",
      "session_token": "token_session_live_abc123xyz789_c4b9",
      "expires_at": "2026-07-04T17:00:00Z"
    }
    ```

---

### B. Conversation Assistant

#### `POST /api/v1/assistant/suggest`
Turn-by-turn endpoint to retrieve nudge suggestions. The client passes the session token; the agent fetches the profile internally. **No raw profile is returned to the client.**
*   **Request Payload**:
    ```json
    {
      "session_token": "token_session_live_abc123xyz789_c4b9",
      "contact_id": "contact_john_doe_99",
      "target_goal": "Get John to approve the Friday deployment deadline extension.",
      "conversation_history": [
        {
          "sender": "user",
          "message": "Hi John, we need to push the deployment to Friday. Are you okay with that?"
        },
        {
          "sender": "counterpart",
          "message": "Not until I see the QA reports. We can't deploy if the tests are failing."
        }
      ]
    }
    ```
*   **Response Payload**:
    ```json
    {
      "recipient_mood_analysis": "Concerned about deployment instability. Focused strictly on safety criteria and verification documents.",
      "suggestions": [
        {
          "tone_label": "Collaborative (Recommended)",
          "suggested_text": "I completely agree we shouldn't compromise on quality. I'll send over the complete QA test reports by 3 PM today. Once you review the safety metrics, let's target Friday afternoon for the deployment.",
          "rationalization": "Addresses his risk-averse trait and preference for documentation sign-off, building alignment rather than pushing back on deadlines."
        },
        {
          "tone_label": "Firm / Analytical",
          "suggested_text": "Understood. The QA dashboard currently shows 98.5% test coverage and zero critical bugs. I will compile the formal metrics report for your review before we finalize the Friday date.",
          "rationalization": "Leverages his analytical nature by providing raw metrics and promising formal documentation."
        }
      ]
    }
    ```

---

### C. Persona Builder (Asynchronous Processing)

#### `POST /api/v1/builder/distill`
Called by the client to initialize or sync a persona profile from a chat history transcript.
*   **Request Payload**:
    ```json
    {
      "session_token": "token_session_live_abc123xyz789_c4b9",
      "contact_id": "contact_john_doe_99",
      "raw_conversation_transcript": [
        {
          "sender": "user",
          "message": "We need to push this release to Friday."
        },
        {
          "sender": "counterpart",
          "message": "I cannot sign off on that without seeing the testing logs first. If safety is compromised, we halt."
        }
      ]
    }
    ```
*   **Response Payload**:
    ```json
    {
      "status": "queued",
      "job_id": "job_distill_992a83f1",
      "contact_id": "contact_john_doe_99"
    }
    ```

---

### D. Negotiation Outcome (User Input)

#### `POST /api/v1/negotiation/outcome`
Called by the client to explicitly record whether a negotiation goal succeeded.
*   **Request Payload**:
    ```json
    {
      "session_token": "token_session_live_abc123xyz789_c4b9",
      "contact_id": "contact_john_doe_99",
      "goal_statement": "Get John to approve the Friday deployment deadline extension.",
      "outcome": "SUCCESS",
      "user_notes": "John approved after seeing the QA reports. The collaborative suggestion worked perfectly."
    }
    ```
*   **Response Payload**:
    ```json
    {
      "status": "success",
      "session_id": "sess_883a2b1c4e90",
      "recorded_at": "2026-07-04T13:15:00Z"
    }
    ```

---

### E. Database Rollback

#### `POST /api/v1/profile/rollback`
Reverts a contact profile to a specified prior version snapshot.
*   **Request Payload**:
    ```json
    {
      "session_token": "token_session_live_abc123xyz789_c4b9",
      "contact_id": "contact_john_doe_99",
      "version_id": "v2"
    }
    ```
*   **Response Payload**:
    ```json
    {
      "status": "success",
      "version_id": "v2",
      "rolled_back_at": "2026-07-04T13:48:00Z"
    }
    ```

---

## 3. [DEPRECATED] Internal In-Memory Data Sharing (Replaces VPC HTTP Endpoints)

> [!NOTE]
> To minimize latency, network overhead, and inter-service authentication costs, the private network HTTP/REST internal endpoints (`GET /internal/v1/profile` and `POST /internal/v1/profile/update`) are **deprecated** and replaced by local in-memory transfers.
>
> Data is shared directly using ADK's `Context.state` object and local method calls to `DatabaseService` inside the consolidated workflow graph container. The JSON schemas defined below remain the schema definitions for the in-memory data exchange.

### A. DB Agent Read Profile (In-Memory Reference)
- **Implementation**: The `get_profile_node` calls `DatabaseService.read_profile()`.
- **Payload Schema**:
  - Requires: `session_token` and `contact_id`.
  - Returns: The full **Contact Profile JSON** schema (defined in Section 1).

### B. DB Agent Write Profile Update (In-Memory Reference)
- **Implementation**: The `database_writer_node` calls `DatabaseService.write_profile()`.
- **Payload Schema**:
  - Requires: `session_token`, `contact_id`, and `profile` (matching the Contact Profile JSON schema).
  - Returns:
    ```json
    {
      "status": "success",
      "version_id": "v4",
      "updated_at": "2026-07-04T13:45:12Z"
    }
    ```

