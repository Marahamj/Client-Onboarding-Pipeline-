from app import models
from app.services.orchestrator import run_onboarding

def test_full_onboarding_completes(client, db_session, sample_payload):
    client.post("/webhooks/crm-deal-won", json=sample_payload)

    result = run_onboarding(db=db_session, onboarding_id=1)

    assert result["status"] == "completed", result
    assert len(result["results"]) == 7

def test_pipeline_resumes_after_mid_failure(
    client, db_session, sample_payload, monkeypatch
):
    client.post("/webhooks/crm-deal-won", json=sample_payload)
    def fail_on_invoice(crm_deal_id, step_name, idempotency_key,fail_until_attempt=0):
        if step_name == "invoice":
            raise ConnectionError("Invoicing API down")
        return {
            "external_id": f"mock-{step_name}-{crm_deal_id}",
            "external_url": f"https://mock.example.com/{step_name}/{crm_deal_id}",
        }
    monkeypatch.setattr(
        "app.services.orchestrator.execute_mock_step", fail_on_invoice
    )
     #First run: Fails at invoice
    first = run_onboarding(db=db_session, onboarding_id=1)
    assert first["status"] =="dead_letter",first
    assert first["stopped_at"]=="invoice"
    
    completed =(
         db_session.query(models.PipelineStep).filter(models.PipelineStep.status == "completed").count()
    )
    assert completed == 5
    #Fix the problem, then restart.
    monkeypatch.undo()
    second = run_onboarding(db=db_session, onboarding_id=1)
    assert second["status"] == "completed", second
    
    #The old steps were not repeated.   
    contract = (
        db_session.query(models.PipelineStep)
        .filter(models.PipelineStep.step_name == "contract")
        .first()
    )
    assert contract.attempt_count == 1

    
    



