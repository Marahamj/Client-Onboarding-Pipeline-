from app.services.orchestrator import run_step
from app import models
from app.services import mock_provider


def test_run_step_completes_and_skips(
    client,
    db_session,
    sample_payload,
):
    client.post("/webhooks/crm-deal-won", json=sample_payload)

    first_result = run_step(
        db=db_session,
        onboarding_id=1,
        crm_deal_id="DEAL-TEST-001",
        step_name="contract",
    )

    assert first_result["status"] == "completed"
    assert first_result["attempt_count"] == 1

    second_result = run_step(
        db=db_session,
        onboarding_id=1,
        crm_deal_id="DEAL-TEST-001",
        step_name="contract",
    )

    assert second_result["status"] == "skipped"


def test_run_step_retries_and_succeeds(
    client,
    db_session,
    sample_payload,
):
    client.post("/webhooks/crm-deal-won", json=sample_payload)

    mock_provider._call_counts.clear()

    result = run_step(
        db=db_session,
        onboarding_id=1,
        crm_deal_id=sample_payload["crm_deal_id"],
        step_name="drive_folders",
    )

    assert result["status"] == "completed"


def test_retry_succeeds_after_two_failures(
    client,
    db_session,
    sample_payload,
):
    client.post("/webhooks/crm-deal-won", json=sample_payload)

    mock_provider._call_counts.clear()

    result = run_step(
        db=db_session,
        onboarding_id=1,
        crm_deal_id=sample_payload["crm_deal_id"],
        step_name="contract",
        fail_until_attempt=2,
    )

    assert result["status"] == "completed"


def test_step_goes_to_dlq_after_all_retries_fail(
    client,
    db_session,
    sample_payload,
):
    client.post("/webhooks/crm-deal-won", json=sample_payload)

    mock_provider._call_counts.clear()

    result = run_step(
        db=db_session,
        onboarding_id=1,
        crm_deal_id=sample_payload["crm_deal_id"],
        step_name="contract",
        fail_until_attempt=3,
    )

    assert result["status"] == "dead_letter", result

    events = db_session.query(models.DeadLetterEvent).all()

    assert len(events) == 1
    assert events[0].resolved is False