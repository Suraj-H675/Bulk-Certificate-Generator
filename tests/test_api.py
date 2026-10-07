from __future__ import annotations

from sqlalchemy import select

from bulk_certificate_generator.models import GenerationJob


def test_create_bulk_job_persists_job_and_items(client, app, valid_request):
    response = client.post("/api/jobs", json=valid_request)

    assert response.status_code == 202
    payload = response.json()
    assert payload["total_count"] == 2
    assert payload["id"]

    with app.state.session_factory() as session:
        job = session.scalar(
            select(GenerationJob).where(GenerationJob.id == payload["id"])
        )
        assert job is not None
        assert len(job.items) == 2

    status = client.get(f"/api/jobs/{payload['id']}")
    assert status.status_code == 200
    assert status.json()["status"] == "COMPLETED"
    assert status.json()["processed_count"] == 2
    assert status.json()["success_count"] == 2
    assert status.json()["invalid_count"] == 0
    assert status.json()["failed_count"] == 0


def test_top_level_validation_rejects_unusable_requests(client, valid_request):
    assert client.post("/api/jobs", json={}).status_code == 422

    wrong_recipient_shape = dict(valid_request)
    wrong_recipient_shape["recipients"] = "Alice Example"
    assert client.post("/api/jobs", json=wrong_recipient_shape).status_code == 422

    no_recipients = dict(valid_request)
    no_recipients["recipients"] = []
    assert client.post("/api/jobs", json=no_recipients).status_code == 422

    missing_certificate = {"recipients": valid_request["recipients"]}
    assert client.post("/api/jobs", json=missing_certificate).status_code == 422


def test_recipient_invalidity_does_not_block_valid_siblings(client, valid_request):
    valid_request["recipients"] = [
        {"name": "Alice Example"},
        {"name": "   "},
        {"name": "Charlie Example"},
    ]

    created = client.post("/api/jobs", json=valid_request).json()
    job_id = created["id"]
    job = client.get(f"/api/jobs/{job_id}").json()
    items = client.get(f"/api/jobs/{job_id}/certificates").json()

    assert job["status"] == "COMPLETED_WITH_ERRORS"
    assert job["processed_count"] == 3
    assert job["success_count"] == 2
    assert job["invalid_count"] == 1
    assert job["failed_count"] == 0
    assert [item["status"] for item in items] == ["GENERATED", "INVALID", "GENERATED"]
    assert items[1]["error_message"].startswith("Invalid recipient:")


def test_generated_certificate_can_be_retrieved(client, valid_request):
    job_id = client.post("/api/jobs", json=valid_request).json()["id"]
    items = client.get(f"/api/jobs/{job_id}/certificates").json()
    certificate = items[0]

    response = client.get(certificate["download_url"])

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert b"Alice Example" in response.content


def test_unknown_and_non_generated_downloads_are_predictable(client, valid_request):
    assert client.get("/api/jobs/not-a-job").status_code == 404

    valid_request["recipients"] = [{"name": ""}]
    job_id = client.post("/api/jobs", json=valid_request).json()["id"]
    item = client.get(f"/api/jobs/{job_id}/certificates").json()[0]

    assert (
        client.get(f"/api/jobs/{job_id}/certificates/{item['id']}/download").status_code
        == 409
    )
    assert client.get(f"/api/jobs/{job_id}/certificates/not-an-item/download").status_code == 404
