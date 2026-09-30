from sqlalchemy.orm import Session
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.services.alerting import alert_supervisor
from app.services.dlq_service import resolve_dlq_events, send_to_dlq

from app.services.idempotency import (
    claim_step,
    create_dead_letter_event,
    mark_step_completed,
    mark_step_failed,
)
from app.services.mock_provider import execute_mock_step
from app import models
from app.constants import ONBOARDING_STEPS


@retry(
    retry = retry_if_exception_type(ConnectionError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
def _execute_with_retry(
    crm_deal_id: str,
    step_name: str,
    idempotency_key: str,
    fail_until_attempt: int = 0,
) -> dict[str, str]:
    return execute_mock_step(
        crm_deal_id=crm_deal_id,
        step_name=step_name,
        idempotency_key=idempotency_key,
        fail_until_attempt=fail_until_attempt,
    )


def run_step(
    db: Session,
    onboarding_id: int,
    crm_deal_id: str,
    step_name: str,
    fail_until_attempt: int = 0,
) -> dict:
    idempotency_key = f"{crm_deal_id}:{step_name}"

    result, step = claim_step(
        db=db,
        onboarding_id=onboarding_id,
        step_name=step_name,
    )

    if result == "not_found":
        return {
            "status": "error",
            "message": "Pipeline step not found",
        }

    if result == "skipped":
        return {
            "status": "skipped",
            "step_name": step_name,
            "external_id": step.external_id,
            "message": "Step already completed",
        }

    if result == "busy":
        return {
            "status": "busy",
            "step_name": step_name,
            "message": "Step is already running",
        }
        
    try:
        external_result = _execute_with_retry(
            crm_deal_id, step_name, idempotency_key,fail_until_attempt
        )
    except Exception as error:
        message = f"{type(error).__name__}: {error}"

        failed_step = mark_step_failed(
            db=db,
            step_id=step.id,
            error_message=message,
        )
        send_to_dlq(db, failed_step, message)
        alert_supervisor(step_name, crm_deal_id, message)

        return {
            "status": "dead_letter",
            "step_name": step_name,
            "error": message,
            "attempt_count": failed_step.attempt_count,
        }

    completed_step = mark_step_completed(
        db=db,
        step_id=step.id,
        external_id=external_result["external_id"],
        external_url=external_result["external_url"],
    )
    resolve_dlq_events(db, step.id)

    return {
        "status": "completed",
        "step_name": completed_step.step_name,
        "external_id": completed_step.external_id,
        "external_url": completed_step.external_url,
        "attempt_count": completed_step.attempt_count,
    }

def run_onboarding(db: Session, onboarding_id: int) -> dict:
    onboarding = (
        db.query(models.Onboarding)
        .filter(models.Onboarding.id == onboarding_id)
        .first()
    )

    if onboarding is None:
        return {"status": "error", "message": "Onboarding not found"}

    crm_deal_id = onboarding.crm_deal_id
    onboarding.status = "in_progress"
    db.commit()
    results = []

    for step_name in ONBOARDING_STEPS:
        onboarding.current_step = step_name
        db.commit()
        result = run_step(
            db=db,
            onboarding_id=onboarding_id,
            crm_deal_id=crm_deal_id,
            step_name=step_name,
        )
        results.append(result)
        if result["status"] in ("completed", "skipped"):
            continue
        
        if result["status"] != "busy":
            onboarding.status = "failed"
            db.commit()
            
        return {
            "onboarding_id": onboarding_id,
            "status": result["status"],
            "stopped_at": step_name,
            "results": results,
        }
        
    onboarding.status = "completed"
    db.commit()

    return {
        "onboarding_id": onboarding_id,
        "status": "completed",
        "results": results,
    }


