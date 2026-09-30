from app import models
from app.services.orchestrator import run_step

def test_step_moves_to_dlq_after_retries_exhausted(
    client, db_session, sample_payload, monkeypatch
):
    client.post("/webhooks/crm-deal-won", json=sample_payload)
    
    def always_fail(*args, **kwargs):
        raise ConnectionError("Drive API unreachable")
    
    monkeypatch.setattr(
        "app.services.orchestrator.execute_mock_step", always_fail
    )
    result = run_step(
        db=db_session,
        onboarding_id=1,
        crm_deal_id=sample_payload["crm_deal_id"],
        step_name="drive_folders",
    )

    assert result["status"] == "dead_letter", result

    event = db_session.query(models.DeadLetterEvent).first()
    assert event is not None
    assert event.resolved is False
    assert "Drive API unreachable" in event.error_message