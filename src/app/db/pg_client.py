from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import AsyncGenerator, Callable

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from app.settings import settings

SessionFactory = Callable[..., AbstractAsyncContextManager[AsyncSession]]


class DatabaseClient:
    def __init__(self, url: str, echo: bool = False) -> None:
        self._engine = create_async_engine(
            url,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_pre_ping=True,
            echo=echo,
        )
        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False, autocommit=False, autoflush=False
        )

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        session: AsyncSession = self._session_factory()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_database_client():
    client = DatabaseClient(settings.DB_URL, settings.DB_ECHO)
    return client


async def get_session(db_client: DatabaseClient = Depends(get_database_client)) -> AsyncGenerator[AsyncSession, None]:
    async with db_client.session() as session:
        yield session


class Base(DeclarativeBase):
    __abstract__ = True

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return f"{cls.__name__.lower()}s"

    id: Mapped[int] = mapped_column(primary_key=True)
