"""Shared project-level exception types."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for domain-level failures."""


class ResourceNotFoundError(DomainError):
    """Raised when a requested resource does not exist."""


class PermissionDeniedError(DomainError):
    """Raised when an operation is not allowed."""


class ProtectedPluginError(DomainError):
    """Raised when a protected plugin cannot be disabled."""
