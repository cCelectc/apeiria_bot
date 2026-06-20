from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy import func, select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

ModelT = TypeVar("ModelT")
CreateT = TypeVar("CreateT", bound=BaseModel)
ResponseT = TypeVar("ResponseT", bound=BaseModel)


class GenericAdminService(Generic[ModelT, CreateT, ResponseT]):
    model: type[ModelT]
    response_cls: type[ResponseT]
    pk_field: str
    create_cls: type[BaseModel] | None = None
    update_cls: type[BaseModel] | None = None
    allow_create: bool = True
    allow_update: bool = True
    allow_delete: bool = True
    allow_batch_delete: bool = False
    max_page_size: int = 200

    async def list(
        self,
        db: "AsyncSession",
        *,
        page: int = 1,
        size: int = 50,
    ) -> tuple[list[ResponseT], int]:
        base = select(self.model)
        total = await db.scalar(select(func.count()).select_from(self.model))
        total = total or 0
        query = base.offset((page - 1) * size).limit(min(size, self.max_page_size))
        result = await db.execute(query)
        return [
            self.response_cls.model_validate(row) for row in result.scalars()
        ], total

    async def get(
        self,
        db: "AsyncSession",
        pk_value: Any,
    ) -> ResponseT | None:
        row = await db.get(self.model, pk_value)
        if row is None:
            return None
        return self.response_cls.model_validate(row)

    async def create(
        self,
        db: "AsyncSession",
        data: CreateT,
    ) -> ResponseT:
        instance = self.model(**data.model_dump())
        db.add(instance)
        await db.flush()
        await db.refresh(instance)
        return self.response_cls.model_validate(instance)

    async def update(
        self,
        db: "AsyncSession",
        pk_value: Any,
        data: dict[str, Any],
    ) -> ResponseT | None:
        instance = await db.get(self.model, pk_value)
        if instance is None:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(instance, key, value)
        await db.flush()
        await db.refresh(instance)
        return self.response_cls.model_validate(instance)

    async def delete(
        self,
        db: "AsyncSession",
        pk_value: Any,
    ) -> bool:
        instance = await db.get(self.model, pk_value)
        if instance is None:
            return False
        await db.delete(instance)
        await db.flush()
        return True

    async def delete_batch(
        self,
        db: "AsyncSession",
        pk_values: list[Any],
    ) -> tuple[int, int]:
        deleted = 0
        failed = 0
        for pk_value in pk_values:
            try:
                instance = await db.get(self.model, pk_value)
                if instance is not None:
                    await db.delete(instance)
                    deleted += 1
                else:
                    failed += 1
            except Exception:  # noqa: BLE001, PERF203
                failed += 1
        await db.flush()
        return deleted, failed
