# Sequence Diagram

## What does it show?

The sequence diagram shows **when and how** the main components interact during the onboarding process.

- **When:** the order in which actions happen, from receiving the CRM webhook to completing the onboarding.
- **How:** how FastAPI, PostgreSQL, the Orchestrator, the Mock Provider, and the Dashboard communicate during normal execution, failure, retry, and recovery.

```mermaid
sequenceDiagram
    autonumber

    actor CRM
    actor User
    participant API as FastAPI
    participant DB as PostgreSQL
    participant ORCH as Orchestrator
    participant MOCK as Mock Provider (in-process)
    participant DASH as Streamlit Dashboard

    CRM->>API: POST /webhooks/crm-deal-won
    API->>DB: Check crm_deal_id

    alt Duplicate deal
        DB-->>API: Existing onboarding
        API-->>CRM: Return existing onboarding
    else New deal
        API->>DB: Find/Create Client
        API->>DB: Create Onboarding
        API->>DB: Create 7 PipelineSteps
        API-->>CRM: Onboarding created
    end

    User->>DASH: Click Run / Retry
    DASH->>API: POST /onboardings/{id}/run
    API->>ORCH: run_onboarding()

    loop Each pipeline step
        ORCH->>DB: claim_step() with row lock

        alt Step already completed
            DB-->>ORCH: skipped

        else Step ready
            DB-->>ORCH: claimed

            Note over ORCH,MOCK: In-process Python function call
            ORCH->>MOCK: execute_mock_step()

            Note over MOCK: Real provider integration would happen here later

            alt Provider succeeds
                MOCK-->>ORCH: external_id + external_url
                ORCH->>DB: mark_step_completed()
                ORCH->>DB: Resolve open DLQ records for this step

            else ConnectionError
                Note over ORCH,MOCK: Retry up to 3 total attempts with exponential backoff
                ORCH->>MOCK: Retry execute_mock_step()
                MOCK-->>ORCH: ConnectionError

                ORCH->>DB: mark_step_failed()
                ORCH->>DB: INSERT dead_letter_events
                Note over DB: DLQ is a PostgreSQL table, not a separate service
                ORCH->>ORCH: Log SUPERVISOR ALERT
                ORCH-->>API: Stop pipeline
            end
        end
    end

    API-->>DASH: Pipeline result

    Note over User,MOCK: Simulated outage is fixed

    User->>DASH: Click Run / Retry again
    DASH->>API: POST /onboardings/{id}/run
    API->>ORCH: run_onboarding()

    ORCH->>DB: claim_step() for completed steps
    DB-->>ORCH: skipped

    ORCH->>DB: claim previously failed step
    DB-->>ORCH: claimed

    ORCH->>MOCK: execute_mock_step()
    MOCK-->>ORCH: Success

    ORCH->>DB: mark_step_completed()
    ORCH->>DB: Mark previous DLQ event resolved

    ORCH->>MOCK: Execute remaining step(s)
    MOCK-->>ORCH: Success
    ORCH->>DB: mark_step_completed()
    ORCH->>DB: Mark onboarding completed

    ORCH-->>API: completed
    API-->>DASH: completed



