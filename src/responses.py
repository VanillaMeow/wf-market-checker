__all__ = ('ItemResponse', 'OrdersItemTopResponse')

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .models import Item, OrderWithUser


class BaseResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    api_version: str = Field(alias='apiVersion')
    data: Any | None = None
    error: dict[str, Any] | None = None


class ItemResponse(BaseResponse):
    data: Item | None = None


class OrdersItemTopData(BaseModel):
    sell: list[OrderWithUser]
    buy: list[OrderWithUser]


class OrdersItemTopResponse(BaseResponse):
    data: OrdersItemTopData | None = None
