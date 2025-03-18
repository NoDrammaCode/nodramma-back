from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.db.pg_client import Base


class Product(Base):
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(1000))
    price: Mapped[int] = mapped_column(Integer)  # Цена в копейках/центах
