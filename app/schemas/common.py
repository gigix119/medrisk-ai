"""Schemas shared across multiple endpoints: structured errors and pagination."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

ItemT = TypeVar("ItemT")


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class Page(BaseModel, Generic[ItemT]):
    items: list[ItemT]
    total: int
    limit: int
    offset: int


class HealthStatus(BaseModel):
    status: str
    service: str
    database: str | None = None


class ReadinessResponse(BaseModel):
    status: str
    dependencies: dict[str, str]
