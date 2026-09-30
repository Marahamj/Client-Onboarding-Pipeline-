# Client Onboarding Pipeline (P3)

A reliable backend pipeline for automating client onboarding after a CRM deal is marked as **Won**.

The system creates and tracks a seven-step onboarding workflow:

1. Contract
2. Drive folders
3. Project board
4. Communication channel
5. Kickoff meeting
6. Invoice
7. Welcome email

The pipeline is designed to handle duplicate webhooks, transient failures, retries, and interrupted executions safely. Pipeline state is persisted in PostgreSQL, allowing an onboarding to be retried after a failure without re-running steps that have already completed.

## Current Implementation

The orchestration and reliability layer includes:

- Webhook ingestion and duplicate prevention
- Database-backed pipeline state
- Step-level idempotency
- Row-level locking for step claiming
- Retry with exponential backoff
- Dead-letter queue (DLQ)
- Resume after mid-pipeline failure
- Concurrent execution protection
- Logging-based supervisor failure alerts
- Streamlit monitoring dashboard
- Automated tests with pytest

External services are currently represented by mock providers. Each mock returns an `external_id` and `external_url` in the same shape expected from an external provider, allowing real integrations to be introduced without changing the main orchestration flow.

## What Is Real vs. Mocked

The seven pipeline steps execute in order with real database-backed state tracking, step claiming, idempotency checks, retry behavior, failure handling, and dead-lettering.

The external service calls themselves are currently mocked. `mock_provider.py` simulates external resource creation and returns mock identifiers and URLs instead of creating real Drive folders, Slack channels, invoices, calendar events, emails, or contracts.

This keeps the reliability and orchestration logic independent from provider-specific integrations.

## Architecture

```text
CRM "Deal Won" webhook
        │
        ▼
FastAPI
        │
        │ validates payload
        │ checks duplicate crm_deal_id
        │ finds/creates Client
        │ creates Onboarding + 7 PipelineSteps
        ▼
PostgreSQL
(source of truth for pipeline state)
        │
        ▼
Orchestrator
(run_onboarding → run_step)
        │
        ├── claim_step
        │     ├── row-level lock
        │     ├── skip completed step
        │     └── detect running step
        │
        ├── Mock Provider
        │     └── retry + exponential backoff
        │
        ├── Success
        │     ├── mark_step_completed
        │     └── resolve previous DLQ events
        │
        └── Failure after retries
              ├── mark_step_failed
              ├── create DLQ event
              └── log supervisor alert

Streamlit Dashboard
        │
        └── communicates with FastAPI only
            (does not access PostgreSQL directly)
```

A full sequence diagram is available in `docs/sequence.md`.

## Data Model

### `clients`

Stores client and company information. When a webhook arrives, the system looks for an existing client by email before creating a new record, allowing client records to be reused across deals.

### `onboardings`

Represents one onboarding workflow per CRM deal.

`crm_deal_id` has a database-level unique constraint, helping prevent duplicate onboardings when the same CRM webhook is received more than once.

### `pipeline_steps`

Stores one record for each pipeline step belonging to an onboarding.

Each record tracks information including:

- `step_name`
- `status`
- `attempt_count`
- `idempotency_key`
- `external_id`
- `external_url`
- `error_message`

`idempotency_key` is unique, and the `(onboarding_id, step_name)` pair also has a database-level unique constraint.

Completed steps are skipped when an onboarding is run again.

### `dead_letter_events`

Stores failures that reach the dead-letter handling path, including:

- Pipeline step
- Error message
- Attempt count
- Resolution status
- Creation time

When a previously failed step later completes successfully, its unresolved DLQ events are marked as resolved.

## Retry and Failure Handling

External provider execution is wrapped with Tenacity.

For `ConnectionError` failures, the system:

1. Retries the provider call up to 3 attempts.
2. Uses exponential backoff between attempts.
3. Marks the step as failed if execution still does not succeed.
4. Creates a dead-letter event.
5. Writes a supervisor alert to the application logs.
6. Stops the onboarding before later steps execute.

After the underlying problem is fixed, the onboarding can be run again. Previously completed steps are skipped and the incomplete step can be attempted again.

## Stack

- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Pydantic
- Tenacity
- Streamlit
- pytest
- Docker Compose

## Running the Project

Build and start the API and PostgreSQL services:

```bash
docker compose up -d --build
```

The API is available at:

```text
http://localhost:8000
```

Swagger documentation:

```text
http://localhost:8000/docs
```

Install the dashboard dependencies:

```bash
pip install streamlit requests
```

Start the dashboard:

```bash
streamlit run dashboard/app.py
```

The dashboard is available at:

```text
http://localhost:8501
```

## Simulating a Failure

For failure/recovery testing, set `FORCE_FAIL_STEP` in `docker-compose.yml` to a pipeline step such as:

```yaml
FORCE_FAIL_STEP: "invoice"
```

Then rebuild and restart:

```bash
docker compose up -d --build
```

The selected step will raise a simulated `ConnectionError`, allowing retry, DLQ, and recovery behavior to be tested.

After the failure test, disable the simulated outage:

```yaml
FORCE_FAIL_STEP: ""
```

Then rebuild before retrying the failed onboarding.

## Testing

Run the automated test suite with:

```bash
pytest -v
```

The tests cover behavior including:

- Webhook onboarding creation
- Duplicate webhook prevention
- Step claiming and completed-step skipping
- Retry after transient failures
- Dead-letter handling after exhausted retries
- Full seven-step onboarding execution
- Mid-pipeline failure and subsequent recovery
- Prevention of re-executing previously completed steps
- Dashboard API endpoints

The project was also tested through live API/Docker runs with three onboarding scenarios, including a forced `invoice` failure followed by successful recovery.

## Current Scope

### Implemented

- CRM Deal Won webhook
- Duplicate webhook protection
- Client lookup by email
- Seven-step onboarding state
- Database-backed idempotency
- Row-level locking during step claiming
- Retry with exponential backoff
- Dead-letter queue
- DLQ resolution after successful recovery
- Logging-based supervisor alerts
- Resume after pipeline failure
- Streamlit dashboard
- Automated pytest suite
- Dockerized API and PostgreSQL environment

### Future Work

- Real Google Drive integration
- Real project-management provider integration
- Real Slack/Teams integration
- Real Calendar integration
- Real invoicing integration
- Real email integration
- Real e-signature/contract integration
- External supervisor notifications such as Slack or email
- Background worker infrastructure if higher asynchronous workload requires it

## Operations

See `RUNBOOK.md` for operational instructions covering:

- Retrying failed onboardings
- Inspecting DLQ events
- Reading supervisor alerts
- Manual rollback procedures
- Current mock-provider limitations