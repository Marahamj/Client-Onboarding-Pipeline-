from sqlalchemy.orm import Session
from app import models

def send_to_dlq(
    db: Session,
    step: models.PipelineStep,
    error_message: str,
) -> models.DeadLetterEvent:
     """Registering a step that ultimately failed after exhausting attempts."""
     event = models.DeadLetterEvent(
         pipeline_step_id=step.id,
        error_message=error_message,
        attempt_count=step.attempt_count,
        resolved=False,)
     db.add(event)
     db.commit()
     return event

def resolve_dlq_events(db: Session, step_id: int) -> None:
    """Upon successful completion of the subsequent step, we close all open DLQ events for it."""
     
    (db.query(models.DeadLetterEvent)
        .filter(
            models.DeadLetterEvent.pipeline_step_id == step_id,
            models.DeadLetterEvent.resolved.is_(False),
        )
        .update({"resolved": True})
    )
    db.commit()