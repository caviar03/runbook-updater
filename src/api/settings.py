import os
import json
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    token: str
    repository: str
    runbook_path: Path
    data_dir: Path
    runbook_paths: tuple[Path, ...] = ()
    qdrant_url: str | None = None

    def __post_init__(self):
        if len(self.token) < 24:
            raise ValueError("BACKEND_TOKEN must contain at least 24 characters")
        if not self.repository or self.repository.count("/") != 1:
            raise ValueError("Set SOURCE_REPOSITORY to the selected owner/repository")
        if not self.paths or any(path.suffix.lower() != ".docx" or not path.is_file() for path in self.paths):
            raise ValueError("Configure existing DOCX runbooks")
        if len({" ".join(path.name.split()).lower() for path in self.paths}) != len(self.paths):
            raise ValueError("Runbook file names must be unique")

    @property
    def paths(self):
        return self.runbook_paths or (self.runbook_path,)

    @property
    def retrieval_embedded(self):
        return not self.qdrant_url

    @property
    def retrieval_location(self):
        return self.qdrant_url or str(self.data_dir / "qdrant")

    @classmethod
    def from_env(cls):
        load_dotenv()
        configured = os.environ.get("RUNBOOK_PATHS")
        if configured:
            values = json.loads(configured)
            if not isinstance(values, list) or not values or any(not isinstance(value, str) or not value.strip() for value in values):
                raise ValueError("RUNBOOK_PATHS must be a nonempty JSON array of file paths")
            paths = tuple(Path(value).resolve() for value in values)
        elif os.environ.get("RUNBOOK_PATH"):
            paths = (Path(os.environ["RUNBOOK_PATH"]).resolve(),)
        else:
            paths = tuple(path.resolve() for path in sorted(Path("test_data/input").glob("*.docx")))
        if not paths:
            raise ValueError("No runbooks were configured")
        return cls(
            token=os.environ.get("BACKEND_TOKEN", ""),
            repository=os.environ.get("SOURCE_REPOSITORY", ""),
            runbook_path=paths[0],
            runbook_paths=paths,
            qdrant_url=os.environ.get("QDRANT_URL") or None,
            data_dir=Path(os.environ.get("BACKEND_DATA_DIR", ".data")).resolve(),
        )
