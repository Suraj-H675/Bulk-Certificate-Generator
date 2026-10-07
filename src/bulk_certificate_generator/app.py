from __future__ import annotations

from fastapi import FastAPI

from .api import build_router
from .config import Settings
from .db import Base, build_engine, build_session_factory
from .service import CertificateGenerator, JobProcessor, JobService
from .storage import LocalArtifactStorage


def create_app(
    settings: Settings | None = None,
    *,
    certificate_generator: CertificateGenerator | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.prepare_runtime_dirs()

    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    Base.metadata.create_all(engine)

    storage = LocalArtifactStorage(settings.artifact_dir)
    job_service = JobService(session_factory)
    processor = JobProcessor(session_factory, certificate_generator, storage)

    app = FastAPI(title="Bulk Certificate Generator", version="0.1.0")
    app.include_router(build_router(job_service, processor, storage))

    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.storage = storage
    app.state.job_service = job_service
    app.state.processor = processor
    return app
