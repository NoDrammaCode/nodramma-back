# Глобальное состояние и Dependency Injection в FastAPI: Избегаем проблем

В этой статье мы рассмотрим проблему глобального состояния в FastAPI приложениях и покажем, как использовать Dependency Injection (DI) для ее решения.

## Что такое глобальное состояние?

Глобальное состояние - это переменные, которые доступны из любой части приложения. В контексте FastAPI приложений, глобальным состоянием могут быть, например, движок SQLAlchemy и фабрика сессий.

## Проблема глобального состояния

Использование глобального состояния может привести к следующим проблемам:

*   **Конкурентный доступ:** Несколько запросов могут одновременно обращаться к глобальным переменным, что может привести к гонке данных, утечкам соединений и другим проблемам.
*   **Тестирование:** Глобальное состояние затрудняет тестирование, так как необходимо мокировать глобальные переменные.
*   **Поддержка:** Глобальное состояние может затруднить поддержку приложения, так как изменения в одной части кода могут повлиять на другие части.

## Пример проблемы глобального состояния

Рассмотрим следующий пример:

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.settings import settings

engine = create_async_engine(settings.DB_URL, echo=settings.DB_ECHO)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
```

В этом примере `engine` и `async_session` являются глобальными переменными. Это означает, что все запросы к базе данных будут использовать один и тот же движок и фабрику сессий.

## Пример состояния гонки

Предположим, у нас есть два endpoint, которые увеличивают счетчик в базе данных:

```python
from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Column, Integer
from sqlalchemy.orm import declarative_base

from app.db.pg_client import get_session, engine  # Используем глобальный engine

Base = declarative_base()

class Counter(Base):
    __tablename__ = "counter"
    id = Column(Integer, primary_key=True)
    value = Column(Integer, default=0)

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

app = FastAPI(dependencies=[Depends(create_tables)])


@app.post("/increment")
async def increment_counter(session: AsyncSession = Depends(get_session)):
    counter = await session.get(Counter, 1)
    if not counter:
        counter = Counter(id=1)
        session.add(counter)

    counter.value += 1
    await session.commit()
    return {"value": counter.value}


@app.get("/counter")
async def get_counter(session: AsyncSession = Depends(get_session)):
    counter = await session.get(Counter, 1)
    if not counter:
        return {"value": 0}
    return {"value": counter.value}
```

Если два пользователя одновременно вызовут `/increment`, то может возникнуть состояние гонки. Оба пользователя прочитают одно и то же значение счетчика, увеличат его на 1 и запишут в базу данных. В результате счетчик будет увеличен только на 1, а не на 2, как ожидалось.

## Решение: Dependency Injection для избежания состояния гонки

Чтобы избежать состояния гонки, необходимо использовать Dependency Injection для предоставления сессий в endpoints. Это позволит каждому запросу использовать свою собственную сессию, что предотвратит конкурентный доступ к базе данных.

Пример:

```python
from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Column, Integer
from sqlalchemy.orm import declarative_base

from app.db.pg_client import DatabaseClient, get_session  # Используем DatabaseClient и get_session

Base = declarative_base()

class Counter(Base):
    __tablename__ = "counter"
    id = Column(Integer, primary_key=True)
    value = Column(Integer, default=0)

async def create_tables():
    async with DatabaseClient(...)._engine.begin() as conn: #  Замените ... на параметры подключения к базе данных
        await conn.run_sync(Base.metadata.create_all)

app = FastAPI()


@app.post("/increment")
async def increment_counter(session: AsyncSession = Depends(get_session)):
    counter = await session.get(Counter, 1)
    if not counter:
        counter = Counter(id=1)
        session.add(counter)

    counter.value += 1
    await session.commit()
    return {"value": counter.value}


@app.get("/counter")
async def get_counter(session: AsyncSession = Depends(get_session)):
    counter = await session.get(Counter, 1)
    if not counter:
        return {"value": 0}
    return {"value": counter.value}
```

В этом примере мы используем `DatabaseClient` и `get_session` для предоставления сессий в endpoints. Это позволяет каждому запросу использовать свою собственную сессию, что предотвращает состояние гонки.

### Аналогия с фабрикой автомобилей

Представь, что `DatabaseClient` - это фабрика по производству автомобилей.

*   **Подход 1 (Глобальное состояние):** У тебя есть *одна* фабрика (глобальный `engine` и `async_session`). Все рабочие (корутины) используют эту фабрику для сборки автомобилей (сессий). Если два рабочих одновременно попытаются использовать один и тот же станок (соединение с базой данных), возникнет конфликт - состояние гонки.
*   **Подход 2 (Dependency Injection с `DatabaseClient`):** У тебя есть *много* маленьких фабрик (`DatabaseClient`). Каждый рабочий получает свою собственную фабрику для сборки автомобиля. Рабочие не мешают друг другу, так как каждый работает в своей собственной изолированной среде.

Dependency Injection (DI) - это шаблон проектирования, который позволяет отделить создание зависимостей от их использования. В FastAPI DI можно реализовать с помощью `Depends`.

Чтобы решить проблему глобального состояния, можно использовать DI для предоставления движка и фабрики сессий в функции endpoints.

### Шаги решения

1.  **Создать класс `DatabaseClient`:**

```python
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import AsyncGenerator, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
```

2.  **Создать функцию-зависимость для получения `DatabaseClient`:**

```python
from fastapi import Depends
from app.settings import settings

def get_database_client():
    client = DatabaseClient(settings.DB_URL, settings.DB_ECHO)
    return client
```

3.  **Изменить функцию `get_session`:**

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

async def get_session(db_client: DatabaseClient = Depends(get_database_client)) -> AsyncGenerator[AsyncSession, None]:
    async with db_client.session() as session:
        yield session
```

## Заключение

Использование Dependency Injection позволяет избежать проблемы глобального состояния и сделать ваше FastAPI приложение более надежным, тестируемым и поддерживаемым.