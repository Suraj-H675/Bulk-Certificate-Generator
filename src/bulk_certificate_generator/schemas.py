from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import ItemStatus, JobStatus


class CertificateInfo(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=160)
    event_name: str = Field(min_length=1, max_length=200)
    issue_date: date


class RecipientInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def blank_email_is_none(cls, value: str | None) -> str | None:
        return value or None


class CreateJobRequest(BaseModel):
    certificate: CertificateInfo
    recipients: list[Any] = Field(min_length=1)


class CreateJobResponse(BaseModel):
    id: str
    status: JobStatus
    total_count: int
    processed_count: int
    success_count: int
    invalid_count: int
    failed_count: int


class JobResponse(CreateJobResponse):
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None


class CertificateItemResponse(BaseModel):
    id: str
    input_index: int
    recipient_name: str | None
    recipient_email: str | None
    status: ItemStatus
    error_message: str | None
    download_url: str | None
