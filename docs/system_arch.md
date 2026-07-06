# System & Product Architecture: TactFlow

TactFlow's core value is built upon a secure, multi-agent architecture and a stateless, serverless deployment pattern on Google Cloud.

---

## Agent System & Product Architecture

To protect high-value persona assets, TactFlow enforces a **Strict Server-Side Boundary**. Decrypted profile data and personality traits **never leave the backend**. The client app (frontend) only holds a temporary session token and receives final suggestions; it never has visibility into the raw contact profile database.

```mermaid
graph TD
    Client([Client App / Frontend]) <-->|1. Login / Get Session Token| DA[Database Agent]
    Client <-->|2. Request Nudges (Passes Session Token + Turn)| CA[Conversation Assistant Agent]
    Client <-->|3. Submit Transcript (Passes Session Token + Log)| PB[Persona Builder Agent]
    CA -.->|4. Read Profile (Passes Session Token)| DA
    PB <-->|5. Write Update (Passes Session Token)| DA
    DA <-->|6. Decrypt / Audit logs| DB[(Encrypted Database)]
    
    classDef llm fill:#bae6fd,stroke:#0284c7,stroke-width:1px,color:#0369a1;
    classDef deterministic fill:#fed7aa,stroke:#ea580c,stroke-width:1px,color:#9a3412;
    class DA deterministic;
    class CA,PB llm;
    
    style DB fill:#f1f5f9,stroke:#94a3b8,stroke-width:2px;
```

### 1. Database (DB) Agent (Deterministic)
- **Security Guard & Gateway**: A purely deterministic, non-LLM agent whose lifecycle is tied to the active user session.
- **Session Token Generation**: Upon user login, the DB Agent uses credentials to decrypt the database key, stores it securely in-memory, and issues a short-lived **Session Token** to the client.
- **Internal API Access**: Exposes private endpoints for the Conversation Assistant and Persona Builder. It validates the client's Session Token before returning profile data (to CA) or committing updates (from PB).
- **Zero-Exposure Policy**: Under no circumstances does the DB Agent expose raw decrypted profiles to the client application.
- **Privacy & Audit Logging**: 100% auditable logs. Strips all Personally Identifiable Information (PII) before writing system logs.
- **Version Control & Rollback**: Implements a snapshot-based version control system (git-like). If the Persona Builder Agent hallucinates or corrupts a profile during updates, the user can request a rollback by passing the Session Token and target Version ID.

### 2. Persona Builder Agent (LLM-based)
- **Access Level**: Read-Write permission to the DB Agent via Session Token validation.
- **Profile Initialization**: During the profile creation phase, the user uploads raw past logs to the Persona Builder along with the Session Token. The Persona Builder analyzes these conversations to distill personality traits and writes the new profile to the DB Agent.
- **Post-Negotiation Synchronization**: At the end of a negotiation run, the client sends the entire conversation transcript and the Session Token to the Persona Builder. It extracts new traits and updates the record via the DB Agent (triggering a new snapshot version).

### 3. Conversation Assistant Agent (LLM-based)
- **Access Level**: Read-Only permission to the DB Agent via Session Token validation.
- **Operational Mode**: Runs in a fast, turn-by-turn loop. It accepts the recipient's unique ID, the goal statement, the latest conversation turn, and the Session Token.
- **Server-Side Reasoning**: The Conversation Assistant queries the DB Agent internally to retrieve the contact profile. It performs the strategic reasoning and returns **only the final phrasing suggestions** to the client. The raw profile remains securely within the server-side boundary.
- **ASR & Extensibility**: Designed with future extensibility in mind. Can receive inputs via Automatic Speech Recognition (ASR) transcriptions (out of current scope) and output suggestions to be displayed on mobile devices or wearable heads-up displays (e.g., smart glasses).


---

## Stateless, Serverless Deployment Architecture (Google Cloud)

To optimize cost, scaling, and operational simplicity, TactFlow's backend runs on **stateless, serverless** infrastructure. All agent memory and state are externalized, meaning the backend agents do not hold any in-memory session details between requests.

```mermaid
flowchart TD
    Client[Client App: Mobile / Wearable] -->|1. Authenticated API Call| Gateway[Apigee / Cloud API Gateway]
    Gateway -->|2. Route Request| Run[Cloud Run: Stateless API Service]
    Run -->|3. Read/Write Keys| Secret[Cloud Secret Manager]
    Run -->|4. Decrypt Persona Profile| DB[Cloud Firestore / Cloud SQL]
    Run -->|5. Orchestrate LLM Calls| Vertex[Vertex AI Gemini API]
    
    subgraph Google Cloud Platform (GCP)
        Gateway
        Run
        Secret
        DB
        Vertex
    end
```

### 1. Compute Options
*   **Google Cloud Run (Recommended)**: Runs the core API service containing the Conversation Assistant, Persona Builder, and DB Agent code inside stateless Docker containers.
    *   *Why*: Cloud Run scales automatically to zero when there is no traffic (eliminating idle compute costs) but supports **concurrency** (handling multiple API requests on a single container instance). It supports up to 60-minute timeouts, which is ideal if the Persona Builder needs to run heavy post-negotiation processing.
*   **Cloud Run Functions (Event-Driven)**: Used for asynchronous, background processing (e.g., running the Persona Builder to update the database *after* a negotiation is completed without blocking the main user API thread).

### 2. State & Data Persistence
*   **Encrypted Firestore or Cloud SQL**: Stores the encrypted contact persona profiles and version-controlled snapshots. 
*   **Request Payload**: Since the compute is stateless, the client app passes the session context (user token, counterpart ID, conversation history, and target goal) with every API request.

---

## API Security & Authentication Best Practices

To protect user accounts and secure the proprietary persona databases, TactFlow uses industry-standard security frameworks.

### 1. User Authentication
*   **OAuth 2.0 / OpenID Connect (OIDC)**: Use JWT (JSON Web Tokens) for client-side authentication (e.g., Mobile App or Web Frontend). Tokens should be short-lived (e.g., 15 minutes) with secure HTTP-only refresh tokens.
*   **MFA (Multi-Factor Authentication)**: Enforced since the database contains highly sensitive personal profiling data.

### 2. API Key Design (For Programmatic/Developer Access)
For external integrations or integrations with wearable glasses, API keys should be constructed following modern safety standards:

*   **Structure**: `prefix_payload_checksum` (e.g., `tf_live_a1b2c3d4..._9e7f`)
    *   **Prefix**: `tf_live_` (TactFlow Live) or `tf_test_` (TactFlow Test). Allows developers and secret-scanning tools (e.g., GitHub Secret Scanning) to immediately detect leaked keys.
    *   **Separator**: Underscores (`_`) are preferred over hyphens because double-clicking the key in a terminal selects the entire token.
    *   **Payload**: Cryptographically secure pseudo-random string (CSPRNG) with at least 128 bits of entropy (e.g., 32 characters of Base62/hex).
    *   **Checksum**: A 4-character suffix derived from a fast hash (like CRC32 or a basic HMAC) of the payload. The API Gateway validates this checksum instantly to drop malformed requests without querying the database, avoiding DoS vector costs.
*   **Storage**: **Never store API keys in plain text**. Store only a salted SHA-256 hash of the API key in the database. When an API call is received, hash the incoming key and compare it to the database record.

---

## Agent API Schema (JSON Inputs & Outputs)

JSON is the industry-standard exchange format for stateless microservices. Since our serverless agent endpoints must be stateless, all session context and inputs are passed via JSON.

For the full JSON schema specifications (inputs/outputs) for the DB Agent, Persona Builder Agent, Conversation Assistant Agent, and Negotiation Outcome endpoint, please see the central [API Schema Specifications in interface_spec.md](./interface_spec.md#2-api-endpoints--requestresponse-schemas).
