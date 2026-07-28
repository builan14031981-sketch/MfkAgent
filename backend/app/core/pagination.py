from pydantic import BaseModel
from typing import TypeVar, Generic, List, Optional
from sqlalchemy.orm import Query


T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = 1
    limit: int = 20


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    limit: int
    pages: int


def paginate(query: Query, page: int = 1, limit: int = 20):
    total = query.count()
    pages = (total + limit - 1) // limit
    items = query.offset((page - 1) * limit).limit(limit).all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }
