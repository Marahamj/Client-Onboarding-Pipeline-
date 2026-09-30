from  datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer,JSON ,String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class Client(Base):
    __tablename__='clients'
    id: Mapped[int] = mapped_column(Integer, primary_key=True,index=True)

    company_name: Mapped[str] = mapped_column(String(255),nullable=False)

    contact_name: Mapped[str | None] = mapped_column(String(255),nullable=True )

    email: Mapped[str] = mapped_column( String(255),nullable=False,index=True,)

    created_at: Mapped[datetime] = mapped_column(DateTime,default=datetime.utcnow,nullable=False,)
    onboardings: Mapped[list["Onboarding"]] = relationship(back_populates="client")

class Onboarding(Base):

    __tablename__ = "onboardings"
    id:Mapped[int] =mapped_column(Integer,primary_key=True,index=True)
    crm_deal_id: Mapped[str] = mapped_column( 
        String(255), unique=True,nullable=False, index=True) 
    client_id: Mapped[int]=mapped_column( ForeignKey("clients.id"), nullable=False)
    service_type: Mapped[str] = mapped_column(String(255), nullable=False)
    project_brief: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_team: Mapped[list[str]]=mapped_column(
        JSON, default = list, nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), default="received",nullable=False)
    current_step: Mapped[str | None] = mapped_column( String(100), nullable=True)
    contract_value: Mapped[int | None] = mapped_column(Integer,nullable=True,)
    currency: Mapped[str| None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False )
    updated_at: Mapped[datetime] = mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow,nullable=False, )

    client: Mapped["Client"] = relationship(back_populates="onboardings")

    steps: Mapped[list["PipelineStep"]] = relationship(back_populates="onboarding",cascade="all, delete-orphan",)

class PipelineStep(Base):

    __tablename__ = "pipeline_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    onboarding_id: Mapped[int] = mapped_column( ForeignKey("onboardings.id"), nullable=False)
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column( String(50), default="pending", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_url: Mapped[str | None] = mapped_column( String(500), nullable=True)
    error_message: Mapped[str | None] = mapped_column( Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,nullable=False,)
    onboarding: Mapped["Onboarding"] = relationship( back_populates="steps")
    __table_args__ = (
    UniqueConstraint(
        "onboarding_id",
        "step_name",
        name="uq_onboarding_step",
    ),
)

class DeadLetterEvent(Base):
    __tablename__ = "dead_letter_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True,index=True, )

    pipeline_step_id: Mapped[int] = mapped_column( ForeignKey("pipeline_steps.id"),nullable=False,)

    error_message: Mapped[str] = mapped_column(Text,nullable=False,)
    attempt_count: Mapped[int] = mapped_column(Integer,nullable=False,)
    resolved: Mapped[bool] = mapped_column(Boolean,default=False, nullable=False, )
    created_at: Mapped[datetime] = mapped_column( DateTime, default=datetime.utcnow,  nullable=False,)


