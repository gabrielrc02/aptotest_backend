import os
import tempfile
from pathlib import Path

# La variable debe existir antes de importar la aplicación, porque la base de
# datos se configura al cargar el módulo database.
TEST_DATABASE = Path(tempfile.gettempdir()) / "aptotest_backend_regression_tests.sqlite"
if TEST_DATABASE.exists():
    TEST_DATABASE.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DATABASE.as_posix()}"
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_placeholder")

import pytest
from fastapi.testclient import TestClient

import main
import models
from database import engine


@pytest.fixture(autouse=True)
def clean_database():
    """Evita que cada prueba dependa de los datos de otra."""
    models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)
    yield
    models.Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture()
def db():
    session = main.SessionLocal()
    try:
        yield session
    finally:
        session.close()
