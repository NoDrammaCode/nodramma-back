from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Пример настроек
    DB_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/db"
    DB_ECHO: bool = False
    DEBUG: bool = False

    class Config:
        env_file = ".env"  # Указывает файл с переменными окружения


# Создаём экземпляр настроек
settings = Settings()
