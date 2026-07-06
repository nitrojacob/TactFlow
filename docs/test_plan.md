# Test Plan: TactFlow

This document outlines the testing strategy for the TactFlow agent system. To validate both deterministic processes (cryptography, token validation, database snapshooting) and LLM-driven behaviors (personality distillation, turn-by-turn nudges), the testing methodology is divided into three tiers: **Deterministic Unit Tests**, **End-to-End Integration Tests**, and **LLM Evaluation Metrics**.

---

## 1. Deterministic Unit Tests

These tests focus on verification of local Python code modules using `pytest`. They execute quickly and run in the local environment without making LLM calls.

### 1.1 Cryptography (`tests/unit/test_crypto.py`)
- **Key Derivation (PBKDF2)**: Verify that the same passphrase and salt consistently generate identical cryptographic keys. Check that invalid passphrase inputs raise validation errors.
- **Payload Encryption/Decryption (AES-256-GCM)**: 
  - Encrypt a mock JSON profile and verify the ciphertext is returned.
  - Decrypt the ciphertext and assert it matches the original JSON profile.
  - Attempt decryption with an incorrect key; assert a cryptographic decryption error is raised.

### 1.2 Database & Session Cache (`tests/unit/test_db_service.py`)
- **API Key Checksum Validation**: Verify that the fast checksum matching logic instantly rejects malformed keys without executing database calls.
- **Session Token Expiration**: Verify that a token is correctly evicted from the in-memory cache after its expiration duration (e.g. 15 minutes), rejecting subsequent read/write queries.
- **Rate Limiting Enforcement**: Verify that requests exceeding defined quotas (e.g. >10 suggest/min or >2 distill/min) trigger a `429 Too Many Requests` status code.

### 1.3 Snapshotting, Rollback, & PII Stripping (`tests/unit/test_snapshot_pii.py`)
- **Snapshot Creation**: Write a profile update and assert that a new snapshot is pushed to the version list, and the list size increases by 1.
- **Rollback Functionality**:
  - Write version `v1` (with `primary_mode: "Collaborating"`).
  - Write version `v2` (with `primary_mode: "Competing"`).
  - Trigger rollback to `v1` and assert the current active profile matches the `v1` snapshot.
- **PII Stripping**: Pass strings containing phone numbers (e.g., `+1-555-0199`), email addresses (e.g., `john@company.com`), and names into the PII filter, and assert they are replaced with standard placeholders (e.g. `[REDACTED_EMAIL]`).

---

## 2. End-to-End Integration Tests

Integration tests run using `pytest` and target the consolidated ADK 2.0 `Workflow` graph, mocking the external Firestore and Vertex AI calls where necessary, or using live test services in sandboxed modes.

### 2.1 Graph Routing Integration (`tests/integration/test_workflow.py`)
- **Suggest Route E2E**: Pass a mock session token, contact ID, and negotiation history with `request_type = "suggest"`. Assert that the workflow triggers `validate_session_node` and `get_profile_node`, passes state in-memory, runs `conversation_assistant_node`, and returns suggestions without network exceptions.
- **Distill Route E2E**: Pass raw logs with `request_type = "distill"`. Verify that the Persona Builder node runs and passes the update to `database_writer_node`, which commits the snapshot version.
- **State Integrity**: Assert that the database agent's decrypted profiles never leak into the output payload return structure.

### 2.2 FastAPI Server Integration (`tests/integration/test_endpoints.py`)
- Use `fastapi.testclient.TestClient` to call the public endpoints:
  - `POST /api/v1/auth/login` (Verify status `success` and token generation).
  - `POST /api/v1/assistant/suggest` (Verify suggestions schema).
  - `POST /api/v1/builder/distill` (Verify background task starts and returns `queued` status immediately).
  - `POST /api/v1/profile/rollback` (Verify reversion code).
- **Parameter Poisoning Validation**: Send payloads with malformed structures, extra fields, or invalid types, and assert FastAPI returns `422 Unprocessable Entity` schemas.

---

## 3. LLM Evaluation (Quality Flywheel)

Because the Conversation Assistant and Persona Builder are LLM-based, we use `agents-cli eval` to evaluate prompt performance, accuracy, and compliance against validation datasets.

### 3.1 Evaluation Datasets (`tests/eval/datasets/eval_data.json`)
We establish a dataset of 50+ negotiation contexts, containing:
- Counterpart Profile JSON (Behavioral baseline).
- User Target Goal.
- Active Conversation Turn logs.
- Golden Suggestion Examples (written by negotiation professionals).
- Expected Distilled Profiles.

### 3.2 Conversation Assistant Metrics (LLM-as-a-Judge)
We define custom metrics in `tests/eval/eval_config.yaml`:
- **Tone Adherence Score (1-5)**: Judges if suggestions match the counterpart's communication channels and tone sensitivities (e.g. no hype for John Doe).
- **Goal Relevance Score (1-5)**: Judges if suggestions actively guide the conversation toward the target goal.
- **Tone Diversity Flag (Boolean)**: Verifies that the suggestions list contains exactly one Collaborative text and one Firm/Analytical text.
- **Zero-Exposure Security Leak Check (Boolean)**: Scans suggestions output text to verify it does not contain raw database fields, behavioral tags, or psychological classifications (e.g. "Avoid mode", "System 2", "loss aversion").

### 3.3 Persona Builder Metrics (LLM-as-a-Judge)
- **Distillation Accuracy (Cosine Similarity / LLM Match)**: Compares the generated profile JSON schema values against the golden baseline profile.
- **PII Compliance (Boolean)**: Verifies that the generated profile does not leak real PII fields.
- **Groundedness Score (1-5)**: Verifies that all behavioral traits, viewpoints, and style attributes listed in the profile are logically backed by text indicators in the source transcript.

### 3.4 Evaluation Execution CLI Commands
```bash
# Install evaluation dependencies
agents-cli install --group eval

# Run agent over the eval dataset and generate traces
agents-cli eval generate --dataset tests/eval/datasets/eval_data.json --output tests/eval/traces.json

# Run LLM-as-a-judge grading over the generated traces
agents-cli eval grade --traces tests/eval/traces.json --config tests/eval/eval_config.yaml --output tests/eval/grades.json

# If iterating on prompts, compare current run with previous run
agents-cli eval compare tests/eval/grades_old.json tests/eval/grades.json
```
