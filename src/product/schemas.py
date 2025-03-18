from pydantic import BaseModel


class ProductCreate(BaseModel):
    name: str
    description: str
    price: int


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price: int | None = None


class ProductResponse(BaseModel):
    id: int
    name: str
    description: str
    price: int

    class Config:
        from_attributes = True
