from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from product.models import Product
from product.repositories import ProductRepositoryInterface
from product.schemas import ProductCreate, ProductUpdate


class ProductUseCases:
    def __init__(self, product_repo: ProductRepositoryInterface, session: AsyncSession):
        self.product_repo = product_repo
        self.session = session

    async def get_product(self, product_id: int) -> Product | None:
        return await self.product_repo.get_product(product_id, self.session)

    async def get_products(self) -> List[Product]:
        return await self.product_repo.get_products(self.session)

    async def create_product(self, product_data: ProductCreate) -> Product:
        product = Product(**product_data.model_dump())
        return await self.product_repo.create_product(product, self.session)

    async def update_product(self, product_id: int, product_data: ProductUpdate) -> Product | None:
        product = Product(**product_data.model_dump(exclude_unset=True))
        return await self.product_repo.update_product(product_id, product, self.session)

    async def delete_product(self, product_id: int) -> bool:
        return await self.product_repo.delete_product(product_id, self.session)
