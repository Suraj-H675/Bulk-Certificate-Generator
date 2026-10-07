from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bulk_certificate_generator.app import create_app
from bulk_certificate_generator.config import Settings


@pytest.fixture
def app(tmp_path: Path):
    database_path = tmp_path / "test.db"
    return create_app(
        Settings(
            database_url=f"sqlite:///{database_path}",
            artifact_dir=tmp_path / "certificates",
        )
    )


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def valid_request() -> dict:
    return {
        "certificate": {
            "title": "Certificate of Completion",
            "event_name": "Backend Workshop",
            "issue_date": "2026-10-08",
        },
        "recipients": [
            {"name": "Alice Example", "email": "alice@example.com"},
            {"name": "Bob Example", "email": "bob@example.com"},
        ],
    }
