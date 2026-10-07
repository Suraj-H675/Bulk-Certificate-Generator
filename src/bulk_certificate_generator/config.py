from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///./var/bcg.db"
    artifact_dir: Path = Path("./var/certificates")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.getenv("BCG_DATABASE_URL", cls.database_url),
            artifact_dir=Path(os.getenv("BCG_ARTIFACT_DIR", str(cls.artifact_dir))),
        )

    def prepare_runtime_dirs(self) -> None:
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        prefix = "sqlite:///./"
        if self.database_url.startswith(prefix):
            Path(self.database_url.removeprefix(prefix)).parent.mkdir(
                parents=True, exist_ok=True
            )
