from datetime import datetime
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Source(StrictModel):
    repository: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    pull_request_number: int = Field(gt=0, strict=True)
    pull_request_url: str
    base_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    head_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    merge_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    merged_at: datetime

    @model_validator(mode="after")
    def validate_metadata(self):
        if self.pull_request_url != f"https://github.com/{self.repository}/pull/{self.pull_request_number}":
            raise ValueError("pull_request_url must identify the supplied repository and PR")
        if self.merged_at.tzinfo is None:
            raise ValueError("merged_at must include a timezone")
        return self


class Trigger(StrictModel):
    type: Literal["pull_request_merged"]
    actor: str = Field(min_length=1, max_length=100)


class SourceFile(StrictModel):
    # Source whitespace is evidence: never normalize code or unified patches.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    file_path: str = Field(min_length=1, max_length=4096)
    previous_file_path: str = Field(min_length=1, max_length=4096)
    status: Literal["added", "removed", "modified", "renamed", "copied", "changed", "unchanged"]
    additions: int = Field(ge=0, strict=True)
    deletions: int = Field(ge=0, strict=True)
    patch: str
    pr_head_content: str | None
    merged_content: str | None

    @model_validator(mode="after")
    def validate_file(self):
        if not self.file_path.strip() or not self.previous_file_path.strip():
            raise ValueError("Source paths must be nonempty")
        if self.status == "removed" and self.merged_content != "":
            raise ValueError("Removed files must have empty merged content")
        return self


class CodeSnapshot(StrictModel):
    head_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    merge_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    files: list[SourceFile] = Field(max_length=3000)

    @model_validator(mode="after")
    def validate_snapshot(self):
        if len({file.file_path for file in self.files}) != len(self.files):
            raise ValueError("Source snapshot contains duplicate paths")
        size = len(json.dumps(self.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":")).encode())
        if size > 10 * 1024 * 1024:
            raise ValueError("Code snapshot exceeds the 10 MiB integration limit")
        return self


class StartAnalysis(StrictModel):
    request_id: str = Field(min_length=1, max_length=200)
    attempt: int = Field(gt=0, strict=True)
    source: Source
    trigger: Trigger
    code_snapshot: CodeSnapshot

    @model_validator(mode="after")
    def validate_identity(self):
        if self.code_snapshot.head_sha != self.source.head_sha or self.code_snapshot.merge_commit_sha != self.source.merge_commit_sha:
            raise ValueError("Code snapshot must match the original PR head and merged commit")
        return self


class Decision(StrictModel):
    decision: Literal["approve", "deny", "create", "acknowledge"]
    proposal_version: str = Field(min_length=1, max_length=200)
    head_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    merge_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    actor: str = Field(min_length=1, max_length=100)
