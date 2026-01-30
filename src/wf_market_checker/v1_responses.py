from __future__ import annotations

__all__ = ('StatisticsResponse',)

from pydantic import BaseModel, ConfigDict

from .v1_models import Statistics


class StatisticsResponse(BaseModel):
    """V1 API response for item statistics."""

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, validate_assignment=True
    )

    payload: Statistics
