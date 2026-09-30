import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, get_db
from sqlalchemy.pool import StaticPool

# قاعدة بيانات مؤقتة بالذاكرة فقط (تختفي بعد كل اختبار)
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine)


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=engine)   # أنشئي كل الجداول من جديد
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)  # اهدمي كل الجداول بعد الاختبار


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
    


@pytest.fixture()
def sample_payload():
    return {
        "crm_deal_id": "DEAL-TEST-001",
        "client_name": "Test Client",
        "client_email": "test@example.com",
        "company_name": "Test Co",
        "service_type": "Web Development",
        "contract_value": 1000,
        "currency": "USD",
        "project_brief": "A test project.",
        "assigned_team": ["a@example.com"],
    }
    

    
