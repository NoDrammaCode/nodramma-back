from abc import ABC, abstractmethod
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from product.models import Product


class ProductRepositoryInterface(ABC):
    @abstractmethod
    async def get_product(self, product_id: int, session: AsyncSession) -> Product | None:
        raise NotImplementedError

    @abstractmethod
    async def get_products(self, session: AsyncSession) -> List[Product]:
        raise NotImplementedError

    @abstractmethod
    async def create_product(self, product: Product, session: AsyncSession) -> Product:
        raise NotImplementedError

    @abstractmethod
    async def update_product(self, product_id: int, product: Product, session: AsyncSession) -> Product | None:
        raise NotImplementedError

    @abstractmethod
    async def delete_product(self, product_id: int, session: AsyncSession) -> bool:
        raise NotImplementedError
