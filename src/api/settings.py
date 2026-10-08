import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    token: str
    repository: str
    runbook_path: Path
    data_dir: Path

    def __post_init__(self):
        if len(self.token) < 24:
            raise ValueError("BACKEND_TOKEN must contain at least 24 characters")
        if not self.repository or self.repository.count("/") != 1:
            raise ValueError("Set SOURCE_REPOSITORY to the selected owner/repository")
        if self.runbook_path.suffix.lower() != ".docx" or not self.runbook_path.is_file():
            raise ValueError("RUNBOOK_PATH must identify an existing DOCX file")

    @classmethod
    def from_env(cls):
        load_dotenv()
        return cls(
            token=os.environ.get("BACKEND_TOKEN", ""),
            repository=os.environ.get("SOURCE_REPOSITORY", ""),
            runbook_path=Path(os.environ.get("RUNBOOK_PATH", "")).resolve(),
            data_dir=Path(os.environ.get("BACKEND_DATA_DIR", ".data")).resolve(),
        )
