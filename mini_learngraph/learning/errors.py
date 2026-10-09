"""Safe domain errors; neither validation inputs nor provider errors are exposed."""

from collections.abc import Mapping, Sequence
from typing import Any

from .schemas import Issue


class DomainError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        expected_revision: int | None = None,
        current_revision: int | None = None,
        failure_reason: str | None = None,
        issues: Sequence[Issue | Mapping[str, Any]] | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.expected_revision = expected_revision
        self.current_revision = current_revision
        self.failure_reason = failure_reason
        self.issues = list(issues or [])
        self.retryable = retryable

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": {
                "resource_type": self.resource_type,
                "resource_id": self.resource_id,
                "expected_revision": self.expected_revision,
                "current_revision": self.current_revision,
                "failure_reason": self.failure_reason,
                "issues": [
                    (issue if isinstance(issue, Issue) else Issue.model_validate(dict(issue))).model_dump(mode="json")
                    for issue in self.issues
                ],
            },
            "retryable": self.retryable,
        }
