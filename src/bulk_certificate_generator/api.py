from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import FileResponse

from .models import CertificateItem, GenerationJob, ItemStatus
from .schemas import (
    CertificateItemResponse,
    CreateJobRequest,
    CreateJobResponse,
    JobResponse,
)
from .service import JobProcessor, JobService
from .storage import LocalArtifactStorage


def build_router(
    job_service: JobService,
    processor: JobProcessor,
    storage: LocalArtifactStorage,
) -> APIRouter:
    router = APIRouter(prefix="/api/jobs", tags=["jobs"])

    @router.post("", response_model=CreateJobResponse, status_code=status.HTTP_202_ACCEPTED)
    def create_job(request: CreateJobRequest, background_tasks: BackgroundTasks) -> CreateJobResponse:
        job = job_service.create_job(request)
        background_tasks.add_task(processor.process_job, job.id)
        return _job_create_response(job)

    @router.get("/{job_id}", response_model=JobResponse)
    def get_job(job_id: str) -> JobResponse:
        job = job_service.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return JobResponse.model_validate(job, from_attributes=True)

    @router.get("/{job_id}/certificates", response_model=list[CertificateItemResponse])
    def list_certificates(job_id: str) -> list[CertificateItemResponse]:
        items = job_service.list_items(job_id)
        if items is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return [_item_response(item, job_id) for item in items]

    @router.get("/{job_id}/certificates/{certificate_id}/download")
    def download_certificate(job_id: str, certificate_id: str):
        item = job_service.get_item(job_id, certificate_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Certificate not found")
        if item.status != ItemStatus.GENERATED or not item.artifact_key:
            raise HTTPException(status_code=409, detail="Certificate is not available for download")

        path = storage.resolve(item.artifact_key)
        if path is None:
            raise HTTPException(status_code=404, detail="Certificate artifact not found")

        return FileResponse(
            path,
            media_type="application/pdf",
            filename=f"certificate-{item.id}.pdf",
        )

    return router


def _job_create_response(job: GenerationJob) -> CreateJobResponse:
    return CreateJobResponse(
        id=job.id,
        status=job.status,
        total_count=job.total_count,
        processed_count=job.processed_count,
        success_count=job.success_count,
        invalid_count=job.invalid_count,
        failed_count=job.failed_count,
    )


def _item_response(item: CertificateItem, job_id: str) -> CertificateItemResponse:
    download_url = None
    if item.status == ItemStatus.GENERATED:
        download_url = f"/api/jobs/{job_id}/certificates/{item.id}/download"
    return CertificateItemResponse(
        id=item.id,
        input_index=item.input_index,
        recipient_name=item.recipient_name,
        recipient_email=item.recipient_email,
        status=item.status,
        error_message=item.error_message,
        download_url=download_url,
    )
