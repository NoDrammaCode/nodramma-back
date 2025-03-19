# Структура проекта и управление сессиями

## Структура проекта

Проект построен на основе многослойной архитектуры (Layered Architecture), что обеспечивает разделение ответственности между компонентами:

```
src/
├── alembic/             # Миграции базы данных
├── app/                 # Общие компоненты приложения
│   ├── db/              # Настройки базы данных
│   │   ├── __init__.py
│   │   └── pg_client.py # Клиент PostgreSQL и базовый класс моделей
│   ├── __init__.py
│   └── settings.py      # Настройки приложения
└── product/             # Модуль для работы с продуктами
    ├── __init__.py
    ├── api.py           # Обработчики API-маршрутов
    ├── models.py        # SQLAlchemy модели
    ├── pg_repository.py # Реализация репозитория для PostgreSQL
    ├── repositories.py  # Интерфейсы репозиториев
    ├── schemas.py       # Pydantic схемы для валидации и сериализации
    └── use_cases.py     # Бизнес-логика
```

## Архитектурные слои

1. **API Layer (api.py)** - Обрабатывает HTTP-запросы, управляет маршрутизацией и ответами.
2. **Use Case Layer (use_cases.py)** - Бизнес-логика приложения, координирует работу с данными.
3. **Repository Layer (repositories.py, pg_repository.py)** - Абстракция работы с хранилищем данных.
4. **Data Layer (models.py)** - Определение структуры данных и взаимодействие с БД.

## Расширение архитектуры

При расширении приложения может потребоваться добавление новых слоев, таких как сервисный слой или слой утилит. Вот рекомендуемый подход для интеграции этих слоев, избегая циклических импортов:

### Добавление сервисного слоя

Сервисный слой может использоваться для абстрагирования внешних сервисов, таких как отправка email, интеграция с платежными системами или другие не связанные с основной бизнес-логикой функции.

#### Рекомендуемая структура:

```
src/
├── app/
│   ├── services/         # Сервисный слой
│   │   ├── __init__.py
│   │   ├── email.py      # Email сервис
│   │   ├── payment.py    # Платежный сервис
│   │   ├── interfaces.py # Интерфейсы сервисов
│   │   └── factory.py    # Фабрика для создания сервисов
└── product/
    ├── use_cases.py      # Использует сервисы
```

#### Предотвращение циклических импортов:

1. **Используйте инъекцию зависимостей для сервисов:**

```python
# app/services/interfaces.py
from abc import ABC, abstractmethod

class EmailServiceInterface(ABC):
    @abstractmethod
    async def send_email(self, to: str, subject: str, body: str) -> bool:
        pass
```

```python
# app/services/email.py
from app.services.interfaces import EmailServiceInterface

class SMTPEmailService(EmailServiceInterface):
    async def send_email(self, to: str, subject: str, body: str) -> bool:
        # Реализация отправки email
        return True
```

2. **Создайте фабрику для инициализации сервисов:**

```python
# app/services/factory.py
from app.services.interfaces import EmailServiceInterface
from app.services.email import SMTPEmailService

def get_email_service() -> EmailServiceInterface:
    return SMTPEmailService()
```

3. **Внедрение сервисов в Use Cases:**

```python
# product/use_cases.py
from app.services.interfaces import EmailServiceInterface

class ProductUseCases:
    def __init__(
        self, 
        product_repo: ProductRepositoryInterface, 
        session: AsyncSession,
        email_service: EmailServiceInterface
    ):
        self.product_repo = product_repo
        self.session = session
        self.email_service = email_service
        
    async def create_product(self, product_data: ProductCreate) -> Product:
        product = Product(**product_data.model_dump())
        result = await self.product_repo.create_product(product, self.session)
        # Уведомление о создании продукта
        await self.email_service.send_email(
            to="admin@example.com",
            subject="Новый продукт создан",
            body=f"Создан продукт: {result.name}"
        )
        return result
```

4. **Обновите фабрику для создания Use Cases:**

```python
# product/api.py
from app.services.factory import get_email_service

async def get_product_use_cases(session: AsyncSession = Depends(get_session)):
    product_repo = ProductRepository()
    email_service = get_email_service()
    return ProductUseCases(
        product_repo=product_repo, 
        session=session,
        email_service=email_service
    )
```

### Утилиты и вспомогательные функции

Для функций-утилит, которые используются в разных частях приложения, рекомендуется создать отдельный модуль:

```
src/
├── app/
│   ├── utils/           # Общие утилиты
│   │   ├── __init__.py
│   │   ├── date.py      # Функции для работы с датами
│   │   ├── text.py      # Функции для работы с текстом
│   │   └── validation.py # Вспомогательные функции валидации
```

#### Предотвращение циклических импортов:

1. **Размещайте утилиты в отдельном модуле без зависимостей от бизнес-кода:**

```python
# app/utils/date.py
from datetime import datetime, timedelta

def add_business_days(date: datetime, days: int) -> datetime:
    # Реализация функции
    return date + timedelta(days=days)
```

2. **Импортируйте только необходимые утилиты:**

```python
# product/use_cases.py
from app.utils.date import add_business_days

class ProductUseCases:
    # ...
    async def schedule_delivery(self, product_id: int, delivery_days: int) -> Delivery:
        product = await self.get_product(product_id)
        delivery_date = add_business_days(datetime.now(), delivery_days)
        # ...
```

### Общие принципы предотвращения циклических импортов

1. **Следуйте принципу зависимости инверсии (DIP):** 
   - Модули высокого уровня не должны зависеть от модулей низкого уровня
   - Оба должны зависеть от абстракций

2. **Используйте интерфейсы и абстрактные классы:**
   - Определяйте интерфейсы в core/shared/domain модулях
   - Реализации интерфейсов размещайте в infrastructure/implementation модулях

3. **Организуйте иерархическую структуру импортов:**
   - Общие абстракции и модели → Репозитории → Сервисы → Use Cases → API

4. **Отложенный импорт (если все другие подходы не работают):**
   - Импортируйте типы при использовании TYPE_CHECKING
   - Используйте строковые аннотации типов

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from product.models import Product  # Только для проверки типов

class ProductService:
    async def process_product(self, product: "Product") -> None:
        # ...
```

5. **Внедрение зависимостей через параметры функций:**
   - Передавайте зависимости как параметры функций
   - Используйте конструкторы классов для инициализации зависимостей

## Работа с сессиями базы данных

В проекте реализован паттерн внедрения зависимостей (Dependency Injection) для управления сессиями базы данных. Этот паттерн позволяет получать сессию базы данных в точке входа (API-эндпоинты) и передавать ее ниже по стеку вызовов, не создавая тесной связи между компонентами.

## Dependency Injection в проекте

Dependency Injection (DI) - это паттерн проектирования, при котором зависимости объекта передаются извне, а не создаются внутри самого объекта. В данном проекте DI используется на нескольких уровнях:

### 1. Внедрение сессии базы данных

**Где используется:** В обработчиках API-маршрутов через механизм `Depends` от FastAPI.

```python
# В файле product/api.py
async def get_product_use_cases(session: AsyncSession = Depends(get_session)):
    # ...
```

**Что внедряется:** Сессия базы данных (`AsyncSession`), которая создается функцией `get_session`.

**Почему это DI:** Вместо создания сессии внутри функции, она получается снаружи через механизм зависимостей.

### 2. Внедрение бизнес-логики (Use Cases)

**Где используется:** В обработчиках API-маршрутов.

```python
# В файле product/api.py
@router.get("/", response_model=List[ProductResponse])
async def get_products(product_use_cases: ProductUseCases = Depends(get_product_use_cases)):
    # ...
```

**Что внедряется:** Объект бизнес-логики (`ProductUseCases`), который создается в зависимости `get_product_use_cases`.

**Почему это DI:** Обработчик не создает экземпляр бизнес-логики сам, а получает его извне.

### 3. Внедрение репозитория

**Где используется:** В функции `get_product_use_cases`, которая создает бизнес-логику.

```python
# В файле product/api.py
async def get_product_use_cases(session: AsyncSession = Depends(get_session)):
    product_repo = ProductRepository()
    return ProductUseCases(product_repo=product_repo, session=session)
```

**Что внедряется:** Репозиторий (`ProductRepository`) внедряется в бизнес-логику (`ProductUseCases`).

**Почему это DI:** Бизнес-логика не создает репозиторий сама, а получает его через конструктор.

### 4. Конструкторная инъекция в бизнес-логике

**Где используется:** В классе `ProductUseCases`.

```python
# В файле product/use_cases.py
class ProductUseCases:
    def __init__(self, product_repo: ProductRepositoryInterface, session: AsyncSession):
        self.product_repo = product_repo
        self.session = session
```

**Что внедряется:** Репозиторий и сессия базы данных.

**Почему это DI:** Зависимости передаются через конструктор, а не создаются внутри класса.

### 5. Инверсия зависимости через интерфейсы

**Где используется:** Использование интерфейса `ProductRepositoryInterface` вместо конкретной реализации.

```python
# В файле product/use_cases.py
def __init__(self, product_repo: ProductRepositoryInterface, session: AsyncSession):
    # ...
```

**Что внедряется:** Любая реализация интерфейса `ProductRepositoryInterface`.

**Почему это DI:** Бизнес-логика зависит от абстракции, а не от конкретной реализации, что позволяет легко заменить реализацию репозитория без изменения бизнес-логики.

### 6. Цепочка внедрения зависимостей

FastAPI использует систему зависимостей, которая поддерживает иерархию внедрения:

1. `Depends(get_session)` создает сессию базы данных
2. Сессия внедряется в `get_product_use_cases`, которая создаёт репозиторий и бизнес-логику
3. `Depends(get_product_use_cases)` внедряет бизнес-логику в обработчики API

Эта цепочка зависимостей обеспечивает правильное создание и инициализацию всех компонентов.

### 1. Определение сессии в pg_client.py

В файле `app/db/pg_client.py` определяется создание и управление сессиями:

```python
# Создание асинхронного движка и фабрики сессий
engine = create_async_engine(settings.DB_URL, echo=settings.DB_ECHO)
async_session = async_sessionmaker(engine, expire_on_commit=False)

# Функция-зависимость для получения сессии
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
```

Здесь важно отметить:
- Создается асинхронный движок SQLAlchemy с настройками из конфигурации
- Фабрика сессий настроена с `expire_on_commit=False` для предотвращения повторных запросов после коммита
- Функция `get_session` использует генератор для управления жизненным циклом сессии

### 2. Передача сессии через Dependency Injection

FastAPI использует систему зависимостей (Depends) для внедрения сессии в нужные компоненты:

#### 2.1. На уровне фабрики зависимостей в API (product/api.py)

```python
async def get_product_use_cases(session: AsyncSession = Depends(get_session)):
    product_repo = ProductRepository()
    return ProductUseCases(product_repo=product_repo, session=session)
```

Эта функция:
- Получает сессию через Depends(get_session)
- Создает экземпляр репозитория
- Создает экземпляр бизнес-логики, передавая в него репозиторий и сессию
- Возвращает полученный объект для использования в эндпоинтах

#### 2.2. На уровне обработчиков маршрутов (product/api.py)

```python
@router.get("/", response_model=List[ProductResponse])
async def get_products(product_use_cases: ProductUseCases = Depends(get_product_use_cases)):
    return await product_use_cases.get_products()

@router.post("/", response_model=ProductResponse, status_code=201)
async def create_product(
    product_data: ProductCreate, product_use_cases: ProductUseCases = Depends(get_product_use_cases)
):
    return await product_use_cases.create_product(product_data)
```

Обработчики маршрутов:
- Получают настроенный объект `product_use_cases` через зависимость
- Не управляют напрямую сессией БД, а делегируют это бизнес-логике
- Фокусируются только на обработке HTTP-запросов и трансформации данных

### 3. Использование сессии в Use Cases

Use Cases (бизнес-логика) получают сессию в конструкторе (product/use_cases.py):

```python
class ProductUseCases:
    def __init__(self, product_repo: ProductRepositoryInterface, session: AsyncSession):
        self.product_repo = product_repo
        self.session = session

    async def get_product(self, product_id: int) -> Product | None:
        return await self.product_repo.get_product(product_id, self.session)

    async def create_product(self, product_data: ProductCreate) -> Product:
        product = Product(**product_data.model_dump())
        return await self.product_repo.create_product(product, self.session)
    
    # ... другие методы
```

На этом уровне:
- Сессия хранится как атрибут класса
- Используется для передачи в методы репозитория
- Use Cases не управляют транзакциями напрямую, а делегируют это репозиторию

### 4. Операции с базой данных в репозитории

Репозиторий использует переданную сессию для выполнения операций (product/pg_repository.py):

```python
class ProductRepository(ProductRepositoryInterface):
    async def get_product(self, product_id: int, session: AsyncSession) -> Product | None:
        result = await session.get(Product, product_id)
        return result

    async def create_product(self, product: Product, session: AsyncSession) -> Product:
        session.add(product)
        await session.commit()
        await session.refresh(product)
        return product
        
    # ... другие методы
```

В репозитории:
- Каждый метод принимает сессию как параметр
- Выполняются операции чтения (get, execute) и записи (add, commit)
- Управление транзакцией (commit) происходит на уровне репозитория

### 5. Полный поток управления сессией

Пример полного потока для создания нового продукта:

1. Клиент отправляет POST-запрос на `/products/`
2. FastAPI вызывает обработчик `create_product`
3. Через `Depends(get_session)` создается сессия БД
4. Сессия передается в `get_product_use_cases`
5. Создается `ProductUseCases` с этой сессией
6. Вызывается `product_use_cases.create_product(product_data)` 
7. Use Case создает объект продукта и вызывает `product_repo.create_product(product, self.session)`
8. Репозиторий добавляет продукт в сессию, выполняет коммит и обновляет объект
9. После завершения обработчика сессия автоматически закрывается

## Преимущества такого подхода

1. **Разделение ответственности** - каждый слой имеет четкие обязанности
2. **Тестируемость** - легко заменить реальный репозиторий на мок для тестирования
3. **Инверсия управления** - зависимости предоставляются извне
4. **Управление транзакциями** - сессия БД создается на верхнем уровне и передается вниз
5. **Асинхронность** - все операции с БД выполняются асинхронно, без блокировок
6. **Автоматическое управление ресурсами** - сессия автоматически закрывается после завершения обработчика
7. **Изоляция от конкретной СУБД** - репозиторий скрывает детали работы с базой данных

## Особенности реализации

- Запросы к БД выполняются через SQLAlchemy Core (select)
- Изменения в БД выполняются через SQLAlchemy ORM (session.add, commit)
- Используется асинхронная сессия (AsyncSession) для неблокирующих операций
- Управление жизненным циклом сессии осуществляется через FastAPI Depends
- Абстракция репозитория позволяет легко заменить конкретную реализацию хранилища
- Использование контекстного менеджера (`async with`) в `get_session` гарантирует правильное закрытие ресурсов
