from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import date, datetime, timezone
from typing import Protocol
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from .generator import PdfCertificateGenerator
from .models import CertificateItem, GenerationJob, ItemStatus, JobStatus
from .schemas import CreateJobRequest, RecipientInput
from .storage import LocalArtifactStorage

logger = logging.getLogger(__name__)


class CertificateGenerator(Protocol):
    def generate(
        self,
        *,
        title: str,
        event_name: str,
        issue_date: date,
        recipient_name: str,
        certificate_id: str,
    ) -> bytes: ...


class JobService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def create_job(self, request: CreateJobRequest) -> GenerationJob:
        job = GenerationJob(
            id=str(uuid4()),
            status=JobStatus.PENDING,
            certificate_title=request.certificate.title,
            event_name=request.certificate.event_name,
            issue_date=request.certificate.issue_date,
            total_count=len(request.recipients),
        )

        invalid_count = 0
        for index, raw_recipient in enumerate(request.recipients):
            item = CertificateItem(
                id=str(uuid4()),
                job_id=job.id,
                input_index=index,
                status=ItemStatus.PENDING,
            )
            try:
                recipient = RecipientInput.model_validate(raw_recipient)
                item.recipient_name = recipient.name
                item.recipient_email = recipient.email
            except ValidationError as exc:
                invalid_count += 1
                item.status = ItemStatus.INVALID
                item.error_message = _validation_message(exc)
            job.items.append(item)

        job.invalid_count = invalid_count
        job.processed_count = invalid_count

        with self.session_factory() as session:
            session.add(job)
            session.commit()
        return job

    def get_job(self, job_id: str) -> GenerationJob | None:
        with self.session_factory() as session:
            return session.get(GenerationJob, job_id)

    def list_items(self, job_id: str) -> Sequence[CertificateItem] | None:
        with self.session_factory() as session:
            if session.get(GenerationJob, job_id) is None:
                return None
            return list(
                session.scalars(
                    select(CertificateItem)
                    .where(CertificateItem.job_id == job_id)
                    .order_by(CertificateItem.input_index)
                )
            )

    def get_item(self, job_id: str, item_id: str) -> CertificateItem | None:
        with self.session_factory() as session:
            return session.scalar(
                select(CertificateItem).where(
                    CertificateItem.id == item_id,
                    CertificateItem.job_id == job_id,
                )
            )


class JobProcessor:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        generator: CertificateGenerator | None,
        storage: LocalArtifactStorage,
    ) -> None:
        self.session_factory = session_factory
        self.generator = generator or PdfCertificateGenerator()
        self.storage = storage

    def process_job(self, job_id: str) -> None:
        try:
            item_ids = self._start_job(job_id)
            for item_id in item_ids:
                self._process_item(job_id, item_id)
            self._finish_job(job_id)
        except Exception:
            logger.exception("Job %s failed unexpectedly", job_id)
            self._mark_job_failed(job_id)

    def _start_job(self, job_id: str) -> list[str]:
        with self.session_factory() as session:
            job = session.get(GenerationJob, job_id)
            if job is None:
                raise LookupError(f"Unknown job {job_id}")
            job.status = JobStatus.PROCESSING
            job.started_at = datetime.now(timezone.utc)
            item_ids = list(
                session.scalars(
                    select(CertificateItem.id)
                    .where(
                        CertificateItem.job_id == job_id,
                        CertificateItem.status == ItemStatus.PENDING,
                    )
                    .order_by(CertificateItem.input_index)
                )
            )
            session.commit()
            return item_ids

    def _process_item(self, job_id: str, item_id: str) -> None:
        with self.session_factory() as session:
            item = session.get(CertificateItem, item_id)
            job = session.get(GenerationJob, job_id)
            if item is None or job is None or item.job_id != job.id:
                raise LookupError(f"Invalid job/item pair {job_id}/{item_id}")

            item.status = ItemStatus.PROCESSING
            session.commit()
            title = job.certificate_title
            event_name = job.event_name
            issue_date = job.issue_date
            recipient_name = item.recipient_name

        if recipient_name is None:
            self._record_item_failure(job_id, item_id, "Recipient name is unavailable")
            return

        try:
            pdf = self.generator.generate(
                title=title,
                event_name=event_name,
                issue_date=issue_date,
                recipient_name=recipient_name,
                certificate_id=item_id,
            )
            artifact_key = self.storage.write(job_id, item_id, pdf)
        except Exception:
            logger.exception("Certificate generation failed for item %s", item_id)
            self._record_item_failure(job_id, item_id, "Certificate generation failed")
            return

        with self.session_factory() as session:
            item = session.get(CertificateItem, item_id)
            if item is None:
                raise LookupError(f"Unknown certificate item {item_id}")
            item.status = ItemStatus.GENERATED
            item.artifact_key = artifact_key
            item.error_message = None
            self._refresh_counts(session, job_id)
            session.commit()

    def _record_item_failure(self, job_id: str, item_id: str, message: str) -> None:
        with self.session_factory() as session:
            item = session.get(CertificateItem, item_id)
            if item is None:
                raise LookupError(f"Unknown certificate item {item_id}")
            item.status = ItemStatus.FAILED
            item.error_message = message
            self._refresh_counts(session, job_id)
            session.commit()

    def _finish_job(self, job_id: str) -> None:
        with self.session_factory() as session:
            job = session.get(GenerationJob, job_id)
            if job is None:
                raise LookupError(f"Unknown job {job_id}")
            self._refresh_counts(session, job_id)
            if job.processed_count != job.total_count:
                raise RuntimeError("Job finished with inconsistent progress counts")
            job.status = (
                JobStatus.COMPLETED_WITH_ERRORS
                if job.invalid_count or job.failed_count
                else JobStatus.COMPLETED
            )
            job.completed_at = datetime.now(timezone.utc)
            session.commit()

    def _mark_job_failed(self, job_id: str) -> None:
        try:
            with self.session_factory() as session:
                job = session.get(GenerationJob, job_id)
                if job is None:
                    return
                self._refresh_counts(session, job_id)
                job.status = JobStatus.FAILED
                job.error_message = "Job processing failed unexpectedly"
                job.completed_at = datetime.now(timezone.utc)
                session.commit()
        except Exception:
            logger.exception("Unable to record failure state for job %s", job_id)

    @staticmethod
    def _refresh_counts(session: Session, job_id: str) -> None:
        job = session.get(GenerationJob, job_id)
        if job is None:
            raise LookupError(f"Unknown job {job_id}")

        counts = dict(
            session.execute(
                select(CertificateItem.status, func.count(CertificateItem.id))
                .where(CertificateItem.job_id == job_id)
                .group_by(CertificateItem.status)
            ).all()
        )
        job.success_count = counts.get(ItemStatus.GENERATED, 0)
        job.invalid_count = counts.get(ItemStatus.INVALID, 0)
        job.failed_count = counts.get(ItemStatus.FAILED, 0)
        job.processed_count = job.success_count + job.invalid_count + job.failed_count


def _validation_message(exc: ValidationError) -> str:
    error = exc.errors(include_url=False)[0]
    location = ".".join(str(part) for part in error["loc"])
    prefix = f"{location}: " if location else ""
    return f"Invalid recipient: {prefix}{error['msg']}"
