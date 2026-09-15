"""Canonical error taxonomy and the standard error envelope.

Every error returned by the API uses the shape:

    {"error": {"code": ..., "message": ..., "request_id": ..., "details": {...}}}

Codes follow the Backend PRD (UPPER_SNAKE). Never leak stack traces.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVAL_INVALID = "APPROVAL_INVALID"
    POLICY_DENIED = "POLICY_DENIED"
    TOOL_NOT_ALLOWED = "TOOL_NOT_ALLOWED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    RECOVERY_EXHAUSTED = "RECOVERY_EXHAUSTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


_STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.CONFLICT: 409,
    ErrorCode.INVALID_STATE_TRANSITION: 409,
    ErrorCode.APPROVAL_REQUIRED: 409,
    ErrorCode.APPROVAL_INVALID: 409,
    ErrorCode.POLICY_DENIED: 403,
    ErrorCode.TOOL_NOT_ALLOWED: 403,
    ErrorCode.EXECUTION_FAILED: 500,
    ErrorCode.VERIFICATION_FAILED: 409,
    ErrorCode.RECOVERY_EXHAUSTED: 409,
    ErrorCode.CANCELLED: 409,
    ErrorCode.EXPIRED: 409,
    ErrorCode.INTERNAL_ERROR: 500,
}


class AppError(Exception):
    """Base application error carrying a canonical code + optional details."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.status_code = status_code or _STATUS_BY_CODE.get(code, 400)

    def to_envelope(self, request_id: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code.value, "message": self.message}
        if request_id:
            payload["request_id"] = request_id
        if self.details:
            payload["details"] = self.details
        return {"error": payload}


# Convenience constructors -------------------------------------------------


def not_found(resource: str, resource_id: str | None = None) -> AppError:
    msg = f"{resource} not found" + (f": {resource_id}" if resource_id else "")
    return AppError(ErrorCode.NOT_FOUND, msg)


def forbidden(message: str = "You do not have permission to perform this action.") -> AppError:
    return AppError(ErrorCode.FORBIDDEN, message)


def unauthenticated(message: str = "Authentication required.") -> AppError:
    return AppError(ErrorCode.UNAUTHENTICATED, message)


def conflict(message: str, *, details: dict[str, Any] | None = None) -> AppError:
    return AppError(ErrorCode.CONFLICT, message, details=details)


def invalid_transition(from_state: str, to_state: str) -> AppError:
    return AppError(
        ErrorCode.INVALID_STATE_TRANSITION,
        f"Cannot transition from {from_state} to {to_state}.",
        details={"from": from_state, "to": to_state},
    )


def approval_invalid(message: str, *, details: dict[str, Any] | None = None) -> AppError:
    return AppError(ErrorCode.APPROVAL_INVALID, message, details=details)


def policy_denied(message: str, *, details: dict[str, Any] | None = None) -> AppError:
    return AppError(ErrorCode.POLICY_DENIED, message, details=details)


def validation_error(message: str, *, details: dict[str, Any] | None = None) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, message, details=details)
