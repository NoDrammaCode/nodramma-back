from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.pg_client import get_session
from product.models import Product
from product.pg_repository import ProductRepository
from product.schemas import ProductCreate, ProductUpdate
from product.use_cases import ProductUseCases

router = APIRouter(prefix="/products", tags=["products"])


async def get_product_use_cases(session: AsyncSession = Depends(get_session)):
    product_repo = ProductRepository()
    return ProductUseCases(product_repo=product_repo)


@router.get("/", response_model=List[Product])
async def get_products(product_use_cases: ProductUseCases = Depends(get_product_use_cases)):
    return await product_use_cases.get_products()


@router.get("/{product_id}", response_model=Product)
async def get_product(product_id: int, product_use_cases: ProductUseCases = Depends(get_product_use_cases)):
    product = await product_use_cases.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("/", response_model=Product, status_code=201)
async def create_product(
    product_data: ProductCreate, product_use_cases: ProductUseCases = Depends(get_product_use_cases)
):
    return await product_use_cases.create_product(product_data)


@router.put("/{product_id}", response_model=Product)
async def update_product(
    product_id: int, product_data: ProductUpdate, product_use_cases: ProductUseCases = Depends(get_product_use_cases)
):
    product = await product_use_cases.update_product(product_id, product_data)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.delete("/{product_id}", status_code=204)
async def delete_product(product_id: int, product_use_cases: ProductUseCases = Depends(get_product_use_cases)):
    deleted = await product_use_cases.delete_product(product_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Product not found")
    return
