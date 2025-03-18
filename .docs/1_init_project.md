# Инициализация проекта

## Установка зависимостей

Для установки необходимых зависимостей, выполните следующую команду:

```bash
poetry add ruff pyright poethepoet pre-commit psycopg fastapi pydantic pydantic_settings sqlalchemy[async] alembic
```

Эта команда установит следующие библиотеки:

*   ruff
*   pyright
*   poethepoet
*   pre-commit
*   psycopg
*   fastapi
*   pydantic
*   sqlalchemy
*   alembic
*   pydantic-settings
  
## Создания базового конфига

```src/app/settings.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Пример настроек
    DB_URL: str = "postgresql+psycopg://postgres:postgres@db:5432/db"
    DB_ECHO: bool = False
    DEBUG: bool = False

    class Config:
        env_file = ".env"  # Указывает файл с переменными окружения


# Создаём экземпляр настроек
settings = Settings()
```