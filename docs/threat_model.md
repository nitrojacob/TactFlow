# STRIDE Threat Model Assessment: TactFlow

This document presents a systematic threat modeling assessment for TactFlow, evaluating the consolidated ADK 2.0 Workflow Graph architecture against the six pillars of the STRIDE framework.

---

## 1. System Boundaries & Trust Zones

To analyze vulnerabilities, we map TactFlow's architecture into distinct trust zones separated by boundaries:

```
[ UNTRUSTED ZONE: CLIENT ]
       │  (Mobile App / Wearable HUD)
       │  
───────┼────────────────────────────── Trust Boundary 1: API Gateway (Authentication & Key Checksum)
       ▼
[ DMZ / INGRESS: Cloud Run container ]
       │  (FastAPI endpoints & Session cache)
       │
───────┼────────────────────────────── Trust Boundary 2: Graph Context (In-Memory Session Keys)
       ▼
[ CONSOLIDATED WORKFLOW GRAPH ]
       │  (validate_session -> get_profile -> LLM Nodes)
       │
───────┼────────────────────────────── Trust Boundary 3: Database Encryption Gateway (AES-256-GCM)
       ▼
[ SECURE ZONE: Firestore / Cloud SQL ]
```

---

## 2. STRIDE Threat Analysis

### 2.1 Spoofing (Identity)
- **Threat Scenario**: An attacker attempts to replay or forge session tokens to read or update another user's contact persona database.
- **Vulnerability**: If session tokens are easily guessable or lack cryptographic signatures, attackers can impersonate legitimate user sessions.
- **Mitigation & Countermeasures**:
  - **Cryptographic Session Tokens**: Session tokens are derived using CSPRNG with 128-bit entropy and appended with a CRC32/HMAC verification checksum.
  - **Key-to-Session Binding**: The Database Agent matches session tokens against symmetric keys stored strictly in-process. A spoofed token with an invalid signature will not match any cache entry, failing decryption of database payloads.
  - **Mitigation Status**: **Secured**.

### 2.2 Tampering (Integrity)
- **Threat Scenario**: An attacker intercepts and tampers with Firestore database records or alters in-memory graph state parameters (e.g. modifying the counterpart ID or goal statement) to influence LLM recommendations.
- **Vulnerability**: Direct database access or parameters passed in HTTP requests could lead to profile corruption or prompt injections.
- **Mitigation & Countermeasures**:
  - **Authenticated Encryption (AES-256-GCM)**: All contact profiles are encrypted at-rest. Any tampering with ciphertext corrupts the authentication tag (GCM tag), causing decryption to fail deterministically.
  - **Version Snapshots & Rollback**: Every update generates a Git-like snapshot. If the LLM generates a corrupted profile during distillation (due to prompt injection), the user can invoke the rollback node to restore the profile to a clean historical version.
  - **Mitigation Status**: **Secured**.

### 2.3 Repudiation (Auditability)
- **Threat Scenario**: A malicious user claims they did not trigger a rollback or update a profile, and the system is unable to audit actions due to strict privacy rules.
- **Vulnerability**: Stripping PII from system logs might result in a complete lack of operational auditing records.
- **Mitigation & Countermeasures**:
  - **Anonymized Snapshot Changelogs**: The Database Agent records all write transactions, snapshot increments, and rollbacks with timestamps, action types, and session hashes while omitting direct PII (e.g. names and emails).
  - **Audit Logging**: Maintain write-once, append-only logs in Google Cloud Logging with strict access controls.
  - **Mitigation Status**: **Secured**.

### 2.4 Information Disclosure (Confidentiality)
- **Threat Scenario**: 
  1. Decrypted profiles leak back to the client application in public API payloads.
  2. PII leaks into application logs.
  3. The Conversation Assistant LLM leaks raw profile parameters in the suggestion text (e.g., "Since John is risk-averse, say X...").
- **Vulnerability**: Insufficient output sanitization at the API, LLM, or logging layers.
- **Mitigation & Countermeasures**:
  - **Strict Server-Side Boundary**: The public `/suggest` endpoint contract returns only final suggested text strings. Decrypted profile fields never cross back to the client.
  - **LLM Prompt Guarding**: System instructions for the Conversation Assistant explicitly prohibit explaining behavioral traits or mentioning database metadata (e.g., conflict modes) to the user.
  - **PII Filtering Utility**: Active regex-based log filters strip emails, phone numbers, and names from standard logs before writing to stdout.
  - **Mitigation Status**: **Secured**.

### 2.5 Denial of Service (Availability)
- **Threat Scenario**: Attackers flood the `/api/v1/assistant/suggest` or `/api/v1/builder/distill` endpoints to trigger heavy LLM execution and decryption operations, causing compute resource exhaustion and cost spikes.
- **Vulnerability**: LLM API calls are highly computationally expensive and billing-sensitive.
- **Mitigation & Countermeasures**:
  - **Fast Key Checksum Verification**: Incoming requests validate token structures in `< 5ms` before hitting any database query or LLM execution node. Malformed requests are rejected instantly.
  - **FastAPI Background Tasks**: Long-running distillation requests are queued instantly to prevent socket depletion.
  - **Required Enhancement**: Rate-limiting middleware (e.g., SlowAPI or Cloud Armor) must be configured to throttle requests per session token or source IP.
  - **Mitigation Status**: **Partially Secured** (Rate-limiting to be added in Phase 3).

### 2.6 Elevation of Privilege (Authorization)
- **Threat Scenario**: An unauthenticated user directly invokes the internal database update or rollback functions.
- **Vulnerability**: Insecure direct object reference (IDOR) or unauthenticated internal routes.
- **Mitigation & Countermeasures**:
  - **Local VPC Isolation**: Internal database read/write routines are not exposed as HTTP endpoints. They are local Python methods invoked within the container.
  - **Graph Execution Gate**: Within the compiled graph, all functional routes (Suggest, Distill, Rollback) flow through `validate_session_node` first. If token validation fails, graph execution aborts.
  - **Mitigation Status**: **Secured**.

---

## 3. Threat Model Summary & Action Items

| STRIDE Pillar | Identified Threat | Priority | Action Item |
| :--- | :--- | :--- | :--- |
| **Denial of Service** | Resource exhaustion via API flooding | High | Implement FastAPI rate-limiting middleware in Phase 3. |
| **Information Disclosure** | LLM output leaking behavioral traits | Medium | Add negative examples in the system prompt to enforce zero-leak output constraints. |
| **Tampering** | Parameter manipulation via HTTP payloads | Medium | Enforce strict Pydantic model validation on all incoming FastAPI endpoints. |
