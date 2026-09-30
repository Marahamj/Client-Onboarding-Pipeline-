from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.database import check_database_connection, get_db
from app.schemas import DealWonRequest, DealWonResponse
from app.services.orchestrator import run_onboarding, run_step
from app.constants import ONBOARDING_STEPS


app = FastAPI(title="Client Onboarding API")


DbSession = Annotated[Session, Depends(get_db)]

@app.get("/")
def home():
    return {
        "message": "Client Onboarding API is running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }


@app.get("/health/db")
def database_health_check():
    database_is_connected = check_database_connection()

    if not database_is_connected:
        return JSONResponse(
            status_code=503,
            content={
                "api": "healthy",
                "database": "disconnected",
            },
        )

    return {
        "api": "healthy",
        "database": "connected",
    }


@app.get("/health/db-session")
def database_session_check(db: DbSession):
    return {
        "database_session": "created"
    }

@app.get("/onboardings")
def list_onboardings(db:DbSession):
    onboardings = (db.query(models.Onboarding).order_by(models.Onboarding.id.desc()).all())
    result=[]
    for o in onboardings:
        steps = (
            db.query(models.PipelineStep).filter(models.PipelineStep.onboarding_id == o.id)
            .order_by(models.PipelineStep.id)
            .all()
        )
        result.append(
            {
                "id": o.id,
                "crm_deal_id": o.crm_deal_id,
                "status": o.status,
                "current_step": o.current_step,
                "steps": [
                    {
                        "step_name": s.step_name,
                        "status": s.status,
                        "attempt_count": s.attempt_count,
                        "error_message": s.error_message,
                    }
                    for s in steps
                ],
            }
        )
    return result


@app.get("/dlq")
def list_dlq(db: DbSession):
    events = (db.query(models.DeadLetterEvent).filter(models.DeadLetterEvent.resolved.is_(False))
        .order_by(models.DeadLetterEvent.id.desc()).all()
    )
    result = []
    for e in events:
        step = (db.query(models.PipelineStep).filter(models.PipelineStep.id == e.pipeline_step_id).first())
        result.append({
            "id": e.id,
            "onboarding_id": step.onboarding_id if step else None,
            "step_name": step.step_name if step else None,
            "error_message": e.error_message,
            "attempt_count": e.attempt_count,
        })
    return result
    
    
    
    
    
    
@app.post(
    "/webhooks/crm-deal-won",
    response_model=DealWonResponse,
)
def deal_won(payload: DealWonRequest, db: DbSession):
    try:
        # 1. Prevent duplicate onboarding for the same CRM deal
        existing_onboarding = (
            db.query(models.Onboarding)
            .filter(
                models.Onboarding.crm_deal_id
                == payload.crm_deal_id
            )
            .first()
        )

        if existing_onboarding:
            return DealWonResponse(
                onboarding_id=existing_onboarding.id,
                crm_deal_id=existing_onboarding.crm_deal_id,
                status=existing_onboarding.status,
                current_step=existing_onboarding.current_step,
            )

        # 2. Find an existing client by email
        client = (
            db.query(models.Client)
            .filter(
                models.Client.email == payload.client_email
            )
            .first()
        )

        # 3. Create the client if it does not exist
        if not client:
            client = models.Client(
                company_name=payload.company_name,
                contact_name=payload.client_name,
                email=payload.client_email,
            )

            db.add(client)
            db.flush()

        # 4. Create onboarding
        onboarding = models.Onboarding(
            crm_deal_id=payload.crm_deal_id,
            client_id=client.id,
            service_type=payload.service_type,
            contract_value=payload.contract_value,
            currency=payload.currency,
            project_brief=payload.project_brief,
            assigned_team=payload.assigned_team,
            status="received",
            current_step="contract",
        )

        db.add(onboarding)
        db.flush()

        # 5. Create the seven pipeline steps
        pipeline_steps = []

        for step_name in ONBOARDING_STEPS:
            step = models.PipelineStep(
                onboarding_id=onboarding.id,
                step_name=step_name,
                status="pending",
                attempt_count=0,
                idempotency_key=f"{payload.crm_deal_id}:{step_name}",
            )

            pipeline_steps.append(step)

        db.add_all(pipeline_steps)

        # 6. Save everything
        db.commit()

        return DealWonResponse(
            onboarding_id=onboarding.id,
            crm_deal_id=onboarding.crm_deal_id,
            status=onboarding.status,
            current_step=onboarding.current_step,
        )

    except IntegrityError:
        db.rollback()

        existing_onboarding = (
            db.query(models.Onboarding)
            .filter(
                models.Onboarding.crm_deal_id
                == payload.crm_deal_id
            )
            .first()
        )

        if existing_onboarding:
            return DealWonResponse(
                onboarding_id=existing_onboarding.id,
                crm_deal_id=existing_onboarding.crm_deal_id,
                status=existing_onboarding.status,
                current_step=existing_onboarding.current_step,
            )

        raise HTTPException(
            status_code=409,
            detail="Could not create onboarding because of a duplicate record.",
        )

    except Exception as error:
        db.rollback()
        print(f"Webhook error: {error}")
        raise HTTPException(
            status_code=500,
            detail="Failed to create onboarding.",
        )
    
@app.post(
    "/onboardings/{onboarding_id}/run-step/{step_name}"
    )
def run_onboarding_step(
    onboarding_id: int,
    step_name: str,
    db: DbSession,
):
    onboarding = (
        db.query(models.Onboarding)
        .filter(models.Onboarding.id == onboarding_id)
        .first()
    )

    if onboarding is None:
        raise HTTPException(
            status_code=404,
            detail="Onboarding not found",
        )
        
    return run_step(
        db=db,
        onboarding_id=onboarding.id,
        crm_deal_id=onboarding.crm_deal_id,
        step_name=step_name,
    )
@app.post("/onboardings/{onboarding_id}/run")
def run_full_onboarding(onboarding_id: int, db: DbSession):
    result=run_onboarding(db=db, onboarding_id=onboarding_id)
    if result["status"]=="error":
        raise HTTPException(status_code=404,detail=result["message"])
    return result

      