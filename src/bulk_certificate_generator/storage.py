from __future__ import annotations

import os
from pathlib import Path


class LocalArtifactStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def write(self, job_id: str, certificate_id: str, content: bytes) -> str:
        directory = self.root / job_id
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / f"{certificate_id}.pdf"
        temporary = destination.with_suffix(".pdf.tmp")

        try:
            temporary.write_bytes(content)
            os.replace(temporary, destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

        return f"{job_id}/{certificate_id}.pdf"

    def resolve(self, artifact_key: str) -> Path | None:
        candidate = (self.root / artifact_key).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError:
            return None
        return candidate if candidate.is_file() else None
