# Persona Identification & Behavioral Science Framework: TactFlow

This document establishes the scientific grounding for TactFlow. It outlines the psychological frameworks, negotiation science, and nudge theory principles that underpin our contact database schema. It also defines the **identification methodology** for the **Persona Builder Agent** to parse raw text into structured persona insights.

---

## 1. Scientific Foundations

To move beyond generic chatbot templates, TactFlow integrates three mature domains of behavioral science:

```
                      ┌────────────────────────────────────────┐
                      │          TACTFLOW NUDGE ENGINE         │
                      └───────────────────┬────────────────────┘
                                          │
         ┌────────────────────────────────┼────────────────────────────────┐
         ▼                                ▼                                ▼
┌──────────────────┐             ┌──────────────────┐             ┌──────────────────┐
│ NEGOTIATION Sci. │             │   NUDGE THEORY   │             │ COGNITIVE PSYCH. │
│ (Harvard/TKI)    │             │(Thaler/Sunstein) │             │(Kahneman/Simon)  │
├──────────────────┤             ├──────────────────┤             ├──────────────────┤
│• Conflict Modes  │             │• Choice Framing  │             │• System 1 vs 2   │
│• Interests/Stops │             │• Cognitive Biases│             │• Maximizer vs    │
│• Reciprocity     │             │• Social Proof    │             │  Satisficer      │
└──────────────────┘             └──────────────────┘             └──────────────────┘
```

### A. Negotiation Science (TKI vs. Big Five)

#### 1. What is the Thomas-Kilmann Conflict Mode Instrument (TKI)?
Developed by Kenneth W. Thomas and Ralph H. Kilmann, the TKI is the leading model for analyzing conflict behavior. It maps individual reactions along two independent dimensions:
*   **Assertiveness**: The extent to which a person attempts to satisfy their own concerns.
*   **Cooperativeness**: The extent to which a person attempts to satisfy the other person's concerns.

By combining these dimensions, TKI identifies **five distinct conflict-handling modes**:
1.  **Competing** (High Assertiveness, Low Cooperativeness): A power-oriented mode. The person pursues their own concerns at the counterpart's expense.
2.  **Collaborating** (High Assertiveness, High Cooperativeness): An integrative, win-win mode. The person works with the counterpart to explore underlying concerns and find alternatives that satisfy both.
3.  **Compromising** (Intermediate Assertiveness & Cooperativeness): A middle-ground mode. The person seeks an expedient, mutually acceptable solution that partially satisfies both parties.
4.  **Avoiding** (Low Assertiveness, Low Cooperativeness): A defensive mode. The person sidesteps or postpones the conflict, refusing to engage.
5.  **Accommodating** (Low Assertiveness, High Cooperativeness): A self-sacrificing mode. The person neglects their own concerns to satisfy the counterpart's concerns.

#### 2. Why Focus on TKI over the Big Five?
*   **Actionable Clues vs. Baseline Traits**: The *Big Five* (Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism) measures broad, lifetime baseline personality traits. Knowing someone is "highly agreeable" is helpful, but it doesn't translate directly into negotiation tactics. 
*   **Direct Tactical Levers**: TKI is *action-oriented*. If the Conversation Assistant knows the counterpart is in **Competing** mode, it will block the user from making immediate concessions (which will be absorbed without reciprocity) and instead prompt the user to establish firm boundaries. If they are in **Avoiding** mode, it will recommend async, low-pressure channels to prevent them from locking up or going silent.
*   *Verdict*: While baseline traits (Big Five) are tracked to understand temperament, **TKI is the primary driver** for the Conversation Assistant's prompts.

#### 3. Interests vs. Positions (Fisher & Ury)
Effective negotiation shifts the focus from rigid positions ("I want X") to underlying interests ("Why I need X"). Identifying a persona's core viewpoints helps the Conversation Assistant uncover win-win interests.


### B. Nudge Theory & Behavioral Economics (Thaler, Sunstein & Cialdini)
*   **Choice Architecture**: Designing the presentation of options to favor certain decisions.
*   **Heuristics & Persuasion Triggers (Robert Cialdini)**: 
    *   *Loss Aversion*: The pain of losing is twice as powerful as the pleasure of gaining.
    *   *Reciprocity*: The desire to return concessions.
    *   *Social Proof*: Aligning with peer consensus.
    *   *Authority*: Deferring to institutional policies or expert credentials.

### C. Cognitive Psychology (Kahneman & Simon)
*   **Dual-Process Theory (System 1 vs. System 2)**:
    *   *System 1 (Fast/Intuitive)*: Relies on heuristics, emotional cues, and shortcuts.
    *   *System 2 (Slow/Analytical)*: Relies on raw data, logical arguments, and metrics.
*   **Maximizers vs. Satisficers (Herbert Simon)**:
    *   *Maximizers*: Compelled to find the absolute best option; they demand exhaustive comparisons.
    *   *Satisficers*: Look for options that meet their threshold criteria and decide quickly once met.

---

## 2. Database Schema: Original vs. Refined

Our original schema (`traits`, `viewpoints`, `philosophical_outlooks`, `interaction_preferences`) was too generic. To generate highly actionable conversational nudges, we have refined the schema to map directly to behavioral science dimensions:

| Original Field | Refined Database Field | Scientific Mapping | Why it's a Better Datapoint |
| :--- | :--- | :--- | :--- |
| `traits` | **`behavioral_traits`** | Big Five Personality | Identifies general personality characteristics (e.g., high conscientiousness, introversion). |
| `viewpoints` | **`viewpoints_and_positions`** | Interests vs. Positions | Records their stated stances, rigid boundaries, and professional values. |
| `philosophical_outlooks` | **`negotiation_style`** | TKI Conflict Modes | Identifies their default conflict mode (*Competing, Collaborating, etc.*) and how they treat concessions. |
| *(None)* | **`cognitive_biases_and_triggers`** | Nudge Theory / Heuristics | Pinpoints key behavioral triggers they yield to (e.g., highly *Loss-Averse*, responds to *Authority*). |
| *(None)* | **`decision_making_style`** | Dual-Process Theory | Determines if they process information via *System 1* (fast/feeling) or *System 2* (slow/analytical/data), and if they are a *Maximizer* or *Satisficer*. |
| `interaction_preferences` | **`interaction_preferences`** | Communication & Flow | Tracks technical communication limits (e.g., format preference, tone sensitivity, cadence). |

---

## 3. Refined Schema Definition (JSON)

Every contact profile in TactFlow's encrypted database is stored in a structured JSON schema. 

For the complete schema definitions and mock data, see the central [Refined Schema Definition in interface_spec.md](./interface_spec.md#1-database-schema-contact-profile).

---

## 4. Persona Identification Methodology (For Persona Builder Agent)

This section serves as the technical blueprint for the **Persona Builder Agent**'s extraction logic.

```
       RAW CONVERSATION INPUT
                  │
                  ▼
   [Step 1: Linguistic Extraction] ──► Parse pronoun usage, sentiment shifts, syntax complexity
                  │
                  ▼
   [Step 2: Behavioral Classifiers] ─► Map behavioral indices to TKI & Cognitive heuristics
                  │
                  ▼
  [Step 3: Conflict Resolution] ────► Reconcile old profile version with new data
                  │
                  ▼
      UPDATED PROFILE VERSION
```

### Step 1: Linguistic Parsing & Marker Extraction
The Persona Builder Agent must scan the raw logs for specific linguistic cues:

*   **System 2 (Analytical) Indicators**: Highly complex syntax, conditional clauses ("if... then," "subject to," "on the condition that"), frequent use of numerical metrics, data references, and words like *measure, analyze, verify, risk, metrics, protocol*.
*   **Loss Aversion Indicators**: Over-indexing on negative outcomes (*failure, cost, risk, exposure, leak, penalty, breach*), focus on preventing worst-case scenarios rather than seeking upside gains.
*   **TKI Competing Indicators**: Imperative sentences, short/assertive statements, frequent use of *must, require, non-negotiable, mandatory*, and low frequency of collaborative pronouns (*we, team, together*).
*   **TKI Avoiding/Accommodating Indicators**: Evasive phrasings, delayed responses, apologetic openings, conditional agreements ("I guess that works," "if there's no other way"), and words like *fine, okay, defer, postpone*.

### Step 2: Mapping to the Behavioral Schema
The agent maps extracted observations into the schema using these rules:

1.  **If the text contains extensive citations of guidelines, policies, or organizational rules:**
    *   Update `cognitive_biases_and_triggers` to include `"Authority / Compliance"`.
    *   Update `interaction_preferences.tone_sensitivity` to `"Requires grounding in formal policies"`.
2.  **If the counterpart insists on comparing multiple options in detail and delays final decision to review edge cases:**
    *   Set `decision_making_style.evaluation_type` to `"Maximizer"`.
    *   Set `decision_making_style.cognitive_mode` to `"System 2 (Analytical)"`.
3.  **If the counterpart yields easily to a request but expresses concern about being blamed for the outcome:**
    *   Set `negotiation_style.primary_mode` to `"Accommodating"` or `"Avoiding"`.
    *   Update `behavioral_traits` with `"risk-averse"`, `"fear of culpability"`.

### Step 3: Conflict Resolution & Version Snapshotting
TactFlow operates on a **100% agent-controlled database write model**. Users are **never** given the interface options to manually add, edit, or delete persona attributes. This guarantees the structural integrity of the psychological profiles.

Because of this, the Persona Builder Agent must resolve contradictions programmatically and handle profile errors using these rules:

*   **Temporal Weighting**: Recent interactions represent the most accurate state. If historical logs showed a "Collaborating" style, but the last 3 negotiation logs show a rigid "Competing" style due to a change in management pressure, the agent weights the recent interactions higher (70% weight to the latest 3 logs) and updates the style.
*   **Context Preservation**: Viewpoints are often context-dependent. Do not overwrite viewpoints; append them as context-specific rules (e.g., "Holds a strict viewpoint on budget X, but is flexible on scheduling Y").
*   **No Manual Edits; Rollback Only**: Because users cannot edit individual fields, if they observe that the Conversation Assistant is making out-of-character suggestions (indicating profile degradation or builder hallucination), they can only trigger a **Rollback**. This rolls back the entire contact record to a previous version snapshot (e.g., `v2` instead of `v3`) managed by the deterministic DB Agent.


---

## 5. Practical Extraction Example

### Raw Conversation Input (End of negotiation)
> **John Doe**: "Look, I hear your points about wanting to ship this on Wednesday. But from my end, we cannot compromise on the database migration verification. Our protocol explicitly states that migrations require a 24-hour soak test. If we skip that to hit Wednesday, and the API throws 500s, it's my team on the hook. I need to see the full simulation logs before I sign off. If you can send me the logs by Wednesday night, we can target Thursday morning for the deployment. Otherwise, we delay to next week."

### Persona Builder Extraction Logic (Mental Walkthrough)
1.  **Linguistic cues**: "we cannot compromise," "protocol explicitly states," "my team on the hook," "I need to see the full simulation logs."
2.  **Traits identified**: Meticulous, protective of team, highly risk-averse.
3.  **Viewpoints**: Adheres strictly to the 24-hour soak test policy; values simulation verification logs.
4.  **Negotiation Style**: *Competing* regarding safety/protocol, but *Compromising* on scheduling if credentials/logs are provided (Wed night -> Thu morning).
5.  **Cognitive Triggers**: *Authority/Compliance* (cites protocol), *Loss Aversion* ("API throws 500s," "team on the hook").
6.  **Decision-Making**: *System 2 (Analytical)* ("need to see the full simulation logs") and *Maximizer* (wants complete validation data).
7.  **Interaction Preferences**: Prefers structured validation reports (simulation logs) before approval.

The resulting output matches the JSON schema defined in Section 3 of this document.
