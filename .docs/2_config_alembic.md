## Делаем ассинхронную конфигурацию алебика в соотвесвии с:
https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic

```bash
(.venv) am@am-computer:~/projects/01_personal/04_nodramma/nodramma-back/src$ alembic init -t async alembic
```
## Делаем корректное название миграций
расскомментируем строку
```src/alembic.ini
...
file_template = %%(year)d_%%(month).2d_%%(day).2d_%%(hour).2d%%(minute).2d-%%(rev)s_%%(slug)s
...
```
## Устанавливаем Создаем Base metada для всех SQLAlchemy моделей.

```python:src/app/db/pg_client.py
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class Base(DeclarativeBase):
    __abstract__ = True

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return f"{cls.__name__.lower()}s"

    id: Mapped[int] = mapped_column(primary_key=True)
```

## Указываем Base как target metadata в src/alembic/env.py

```python:src/alembic/env.py
from app.db.pg_client import Base  # noqa

target_metadata = Base.metadata
```

## Указываем  URL подключения для SQLAlchemy в алембик
```python:src/alembic/env.py
config.set_main_option("sqlalchemy.url", settings.DB_URL)
```

## Проверяем миграции
```bash
alembic revision --autogenerate -m "Create product"
```

## Накатываем миграции
Для применения созданных миграций выполните следующую команду:

```bash
alembic upgrade head
```