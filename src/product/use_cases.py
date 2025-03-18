from typing import List

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.pg_client import get_session
from product.models import Product
from product.repositories import ProductRepositoryInterface
from product.schemas import ProductCreate, ProductUpdate


class ProductUseCases:
    def __init__(self, product_repo: ProductRepositoryInterface):
        self.product_repo = product_repo

    async def get_product(self, product_id: int, session: AsyncSession = Depends(get_session)) -> Product | None:
        async with session:
            return await self.product_repo.get_product(product_id, session)

    async def get_products(self, session: AsyncSession = Depends(get_session)) -> List[Product]:
        async with session:
            return await self.product_repo.get_products(session)

    async def create_product(
        self, product_data: ProductCreate, session: AsyncSession = Depends(get_session)
    ) -> Product:
        async with session:
            product = Product(**product_data.model_dump())
            return await self.product_repo.create_product(product, session)

    async def update_product(
        self, product_id: int, product_data: ProductUpdate, session: AsyncSession = Depends(get_session)
    ) -> Product | None:
        async with session:
            product = Product(**product_data.model_dump(exclude_unset=True))
            return await self.product_repo.update_product(product_id, product, session)

    async def delete_product(self, product_id: int, session: AsyncSession = Depends(get_session)) -> bool:
        async with session:
            return await self.product_repo.delete_product(product_id, session)
