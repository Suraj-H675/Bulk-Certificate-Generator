from __future__ import annotations

from fastapi.testclient import TestClient

from bulk_certificate_generator.app import create_app
from bulk_certificate_generator.config import Settings
from bulk_certificate_generator.generator import PdfCertificateGenerator


class FailingGenerator(PdfCertificateGenerator):
    def generate(self, **kwargs) -> bytes:
        if kwargs["recipient_name"] == "Bob Example":
            raise RuntimeError("intentional generator failure")
        return super().generate(**kwargs)


def test_one_generation_failure_does_not_stop_siblings(tmp_path, valid_request):
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'test.db'}",
            artifact_dir=tmp_path / "certificates",
        ),
        certificate_generator=FailingGenerator(),
    )

    valid_request["recipients"] = [
        {"name": "Alice Example"},
        {"name": "Bob Example"},
        {"name": "Charlie Example"},
    ]

    with TestClient(app) as client:
        job_id = client.post("/api/jobs", json=valid_request).json()["id"]
        job = client.get(f"/api/jobs/{job_id}").json()
        items = client.get(f"/api/jobs/{job_id}/certificates").json()

        assert job["status"] == "COMPLETED_WITH_ERRORS"
        assert job["processed_count"] == 3
        assert job["success_count"] == 2
        assert job["failed_count"] == 1
        assert [item["status"] for item in items] == ["GENERATED", "FAILED", "GENERATED"]
        assert items[1]["error_message"] == "Certificate generation failed"
        assert client.get(items[0]["download_url"]).status_code == 200
        assert client.get(items[2]["download_url"]).status_code == 200
