from sqlalchemy.orm import Session

from app import models


def get_step_for_update(
    db: Session,
    onboarding_id: int,
    step_name: str,
):
    """
    يجلب الخطوة مع قفل صف قاعدة البيانات.
    القفل يمنع عاملين من حجز نفس الخطوة في نفس الوقت.
    """
    return (
        db.query(models.PipelineStep)
        .filter(
            models.PipelineStep.onboarding_id == onboarding_id,
            models.PipelineStep.step_name == step_name,
        )
        .with_for_update()
        .first()
    )


def claim_step(
    db: Session,
    onboarding_id: int,
    step_name: str,
) -> tuple[str, models.PipelineStep | None]:
    """
    Attempts to claim a step for execution.

    Results:
    - claimed: The step has been claimed and is ready for execution.
     - skipped: The step is already complete.
    - busy: The step is currently being executed.
    - not_found: The step does not exist.
    """

    step = get_step_for_update(
        db=db,
        onboarding_id=onboarding_id,
        step_name=step_name,
    )

    if step is None:
        return "not_found", None

    if step.status == "completed" or step.external_id:
        return "skipped", step

    if step.status == "running":
        return "busy", step

    step.status = "running"
    step.attempt_count += 1

    db.commit()

    return "claimed", step


def mark_step_completed(
    db: Session,
    step_id: int,
    external_id: str,
    external_url: str | None = None,
):
    step = (
        db.query(models.PipelineStep)
        .filter(models.PipelineStep.id == step_id)
        .first()
    )

    if step is None:
        raise ValueError("Pipeline step not found")

    step.status = "completed"
    step.external_id = external_id
    step.external_url = external_url
    step.error_message = None

    db.commit()

    return step


def mark_step_failed(
    db: Session,
    step_id: int,
    error_message: str,
):
    step = (
        db.query(models.PipelineStep)
        .filter(models.PipelineStep.id == step_id)
        .first()
    )

    if step is None:
        raise ValueError("Pipeline step not found")

    step.status = "failed"
    step.error_message = error_message

    db.commit()

    return step
def create_dead_letter_event(db: Session,
    step_id: int,
    error_message: str,
    attempt_count: int,):
    
    event = models.DeadLetterEvent(
        pipeline_step_id=step_id,
        error_message=error_message,
        attempt_count=attempt_count,
        resolved=False,
    )

    db.add(event)
    db.commit()

    return event
    