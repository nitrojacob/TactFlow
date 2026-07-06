# TactFlow Specifications & Documentation

This directory houses the product, business, architectural, and scientific specifications for **TactFlow**, an agentic, persona-driven negotiation and conversational nudge assistant.

---

## Concept & Architecture

| File | Description |
| :--- | :--- |
| **[business_plan.md](./business_plan.md)** | Outlines the product's value proposition, target customer profiles (ranked by profitability), monetization structures, and direct/indirect competitor analysis. |
| **[system_arch.md](./system_arch.md)** | Defines the decoupled Multi-Agent design (DB Agent, Persona Builder, Conversation Assistant), the Google Cloud serverless/stateless deployment architecture, and API security/auth protocols. |
| **[persona_identification.md](./persona_identification.md)** | Establishes the psychological science behind TactFlow (Thomas-Kilmann Conflict Modes, Nudge Theory, Cognitive Biases, Dual-Process Theory) and details the extraction methodology for the Persona Builder Agent. |
| **[interface_spec.md](./interface_spec.md)** | Serves as the single source of truth for all data contracts, including the database profile schema and the request/response payloads for all API endpoints. |

---

## Detailed Design

This section references files establishing requirements, development planning, testing criteria, and technical execution for the consolidated architecture.

| File | Description |
| :--- | :--- |
| **[detailed_design.md](./detailed_design.md)** | Serves as the golden reference for the consolidated ADK 2.0 workflow graph, mapping node topologies, caching strategies, and in-memory communications. |
| **[requirements.md](./requirements.md)** | Specifies functional, performance, and security specifications for Database, Persona Builder, and Conversation Assistant modules. |
| **[development_plan.md](./development_plan.md)** | Outlines the phased milestones for implementation, testing, integration, and serverless Cloud Run deployment. |
| **[test_plan.md](./test_plan.md)** | Outlines unit tests (for cryptography, cache, and snapshots), E2E integrations, and quality metric evaluations using `agents-cli eval`. |
| **[threat_model.md](./threat_model.md)** | Systematic threat model assessing the consolidated graph design against the STRIDE security framework (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege). |



