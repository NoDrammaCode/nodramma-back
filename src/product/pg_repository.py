from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from product.models import Product
from product.repositories import ProductRepositoryInterface


class ProductRepository(ProductRepositoryInterface):
    async def get_product(self, product_id: int, session: AsyncSession) -> Product | None:
        result = await session.get(Product, product_id)
        return result

    async def get_products(self, session: AsyncSession) -> List[Product]:
        result = await session.execute(select(Product))
        return list(result.scalars().all())

    async def create_product(self, product: Product, session: AsyncSession) -> Product:
        session.add(product)
        await session.commit()
        await session.refresh(product)
        return product

    async def update_product(
        self,
        product_id: int,
        product: Product,
        session: AsyncSession,
    ) -> Product | None:
        existing_product = await self.get_product(product_id, session)
        if existing_product:
            existing_product.name = product.name
            existing_product.description = product.description
            existing_product.price = product.price
            await session.commit()
            await session.refresh(existing_product)
            return existing_product
        return None

    async def delete_product(self, product_id: int, session: AsyncSession) -> bool:
        product = await self.get_product(product_id, session)
        if product:
            await session.delete(product)
            await session.commit()
            return True
        return False
