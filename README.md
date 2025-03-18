# No-Dramma

Сервис для психологической поддержки.

## Требования

* Python 3.12 или выше
* [Poetry](https://python-poetry.org/) для управления зависимостями
* [Docker](https://www.docker.com/) (опционально, для контейнеризации)

## Установка

1. Клонируйте репозиторий:
```shell
git clone <your-repository-url>
cd no-dramma
```

2. Установите зависимости с помощью Poetry:
```shell
poetry install
```

## Инструменты разработки

### Линтер и форматтер

Проект использует [Ruff](https://github.com/astral-sh/ruff) для линтинга и форматирования кода. [Интеграция с редакторами](https://docs.astral.sh/ruff/editors/).

Запуск линтера:
```shell
# проверка кода
ruff check 

# проверка и исправление проблем
ruff check --fix 
```

Запуск форматтера:
```shell
ruff format
```

Запуск обоих инструментов:
```shell
poetry poe format
```

### Проверка типов

[Pyright](https://github.com/microsoft/pyright) используется для статической проверки типов. 

```shell
pyright
```

### Pre-commit хуки

Для установки pre-commit хуков:

```shell
pre-commit install
```

Запуск для всех файлов:
```shell
pre-commit run --all-files
```

### Миграции базы данных

Проект использует [Alembic](https://alembic.sqlalchemy.org/) для миграций.

```shell
# создание новой миграции
poetry poe db-revision --m "описание миграции"

# применение миграций
poetry poe db-upgrade

# откат миграции
poetry poe db-downgrade
```

### Тестирование

Проект использует pytest со следующими плагинами:
- pytest-asyncio для асинхронных тестов
- pytest-mock для моков
- pytest-env для управления переменными окружения

Запуск тестов:
```shell
poetry run pytest
```