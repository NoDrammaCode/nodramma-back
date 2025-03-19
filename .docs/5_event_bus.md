# Внутренняя шина событий (EventBus)

## Концепция EventBus

Внутренняя шина событий (EventBus) — это паттерн проектирования, который позволяет компонентам приложения обмениваться сообщениями без прямой зависимости между ними. Это реализация принципа слабой связанности (loose coupling) и инверсии управления (IoC).

В контексте нашей архитектуры, EventBus можно интегрировать как связующее звено между слоями приложения:

```
     ┌───────────────┐
     │  API Layer    │
     └───────┬───────┘
             │
     ┌───────▼───────┐
     │  Use Cases    │───┐
     └───────┬───────┘   │
             │           │
┌────────────▼────────┐  │
│  Repository Layer   │  │
└────────────┬────────┘  │
             │           │
     ┌───────▼───────┐   │
     │  Data Layer   │   │
     └───────────────┘   │
                         │
                 ┌───────▼───────┐
                 │   EventBus    │
                 └───────┬───────┘
                         │
                 ┌───────▼───────┐
                 │  Subscribers  │
                 └───────────────┘
```

### Основные компоненты

1. **События (Events)** - иммутабельные объекты данных, представляющие факт, который произошел в системе
2. **Издатели (Publishers)** - компоненты, которые создают и отправляют события в шину
3. **Подписчики (Subscribers)** - компоненты, которые обрабатывают события
4. **Шина событий (EventBus)** - механизм, который доставляет события от издателей к подписчикам

## Реализация EventBus

### Синхронная реализация

Простая синхронная реализация для небольших приложений:

```python
from typing import Any, Callable, Dict, List, Type

class EventBus:
    def __init__(self):
        self._subscribers: Dict[Type[Any], List[Callable]] = {}
    
    def subscribe(self, event_type: Type[Any], handler: Callable) -> None:
        """Подписаться на событие определенного типа"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
    
    def publish(self, event: Any) -> None:
        """Опубликовать событие"""
        event_type = type(event)
        if event_type in self._subscribers:
            for handler in self._subscribers[event_type]:
                handler(event)
```

### Асинхронная реализация

Для высоконагруженных приложений предпочтительна асинхронная реализация:

```python
import asyncio
from typing import Any, Callable, Dict, List, Type

class AsyncEventBus:
    def __init__(self):
        self._subscribers: Dict[Type[Any], List[Callable]] = {}
    
    def subscribe(self, event_type: Type[Any], handler: Callable) -> None:
        """Подписаться на событие определенного типа"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
    
    async def publish(self, event: Any) -> None:
        """Асинхронно опубликовать событие"""
        event_type = type(event)
        if event_type in self._subscribers:
            # Создаем задачи для всех обработчиков
            tasks = [
                asyncio.create_task(handler(event)) 
                for handler in self._subscribers[event_type]
            ]
            # Ждем завершения всех задач
            await asyncio.gather(*tasks)
```

### Интеграция с DI-контейнером

Для соблюдения принципов чистой архитектуры и инверсии зависимостей, EventBus следует интегрировать через DI-контейнер:

```python
# app/services/events/factory.py
from app.services.events.interface import EventBusInterface
from app.services.events.implementations import AsyncEventBus

def get_event_bus() -> EventBusInterface:
    return AsyncEventBus()

# В настройках FastAPI
app = FastAPI()

event_bus = get_event_bus()

# Внедрение в API
async def get_product_use_cases(
    session: AsyncSession = Depends(get_session),
    event_bus: EventBusInterface = Depends(lambda: event_bus)
):
    product_repo = ProductRepository()
    return ProductUseCases(
        product_repo=product_repo, 
        session=session,
        event_bus=event_bus
    )
```

## Производительность EventBus

### Преимущества с точки зрения производительности

1. **Параллельная обработка** - асинхронная шина позволяет выполнять обработчики событий параллельно
2. **Снижение нагрузки на основной поток** - неблокирующие операции улучшают отзывчивость API
3. **Масштабируемость** - возможность масштабирования через распределенные очереди сообщений
4. **Буферизация** - возможность буферизации событий при пиковых нагрузках

### Потенциальные узкие места

1. **Накладные расходы на маршрутизацию** - дополнительные затраты на поиск соответствующих обработчиков
2. **Сериализация/десериализация** - при использовании внешних систем доставки сообщений
3. **Управление памятью** - при большом количестве событий в очереди
4. **Отладка и мониторинг** - сложнее отслеживать поток выполнения

### Оптимизация производительности

1. **Фильтрация событий** - отправка событий только заинтересованным подписчикам
2. **Групповая обработка** - объединение нескольких событий для уменьшения накладных расходов
3. **Приоритизация событий** - обработка критических событий в первую очередь
4. **Мониторинг** - отслеживание производительности шины и выявление узких мест

```python
# Пример оптимизированной шины событий с приоритетами
class PrioritizedEventBus:
    def __init__(self):
        self._subscribers = {}
        self._priorities = {}  # Приоритеты для типов событий
    
    def subscribe(self, event_type, handler, priority=0):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
            self._priorities[event_type] = []
        
        # Вставка с сохранением порядка приоритета
        index = 0
        while (index < len(self._priorities[event_type]) and 
               self._priorities[event_type][index] <= priority):
            index += 1
        
        self._subscribers[event_type].insert(index, handler)
        self._priorities[event_type].insert(index, priority)
```

## Границы применения EventBus

### Когда использовать EventBus

1. **Слабое связывание между компонентами** - когда необходимо минимизировать зависимости
2. **События в домене (Domain Events)** - для отражения изменений состояния домена
3. **Асинхронная обработка** - когда результат действия не требуется немедленно
4. **Многоэтапная обработка** - последовательность действий в ответ на одно событие
5. **Интеграция с внешними системами** - уведомления, аналитика, логирование и т.д.

```python
# Пример использования для доменных событий
class ProductCreated:
    def __init__(self, product_id: int, name: str, price: int):
        self.product_id = product_id
        self.name = name
        self.price = price
        self.timestamp = datetime.now()

class ProductUseCases:
    def __init__(self, product_repo, session, event_bus):
        self.product_repo = product_repo
        self.session = session
        self.event_bus = event_bus
    
    async def create_product(self, product_data: ProductCreate) -> Product:
        product = Product(**product_data.model_dump())
        result = await self.product_repo.create_product(product, self.session)
        
        # Публикация события о создании продукта
        await self.event_bus.publish(ProductCreated(
            product_id=result.id,
            name=result.name,
            price=result.price
        ))
        
        return result
```

### Когда НЕ использовать EventBus

1. **Простые приложения** - излишнее усложнение для небольших проектов
2. **Требуется немедленный результат** - когда нужна синхронная обработка и гарантированный результат
3. **Критичный по времени код** - когда производительность является приоритетом
4. **Последовательные операции с зависимостями** - когда каждый следующий шаг зависит от результата предыдущего
5. **Требуется строгая консистентность данных** - когда важна целостность транзакций

## Примеры интеграции с нашей архитектурой

### Регистрация обработчиков событий

```python
# app/services/events/handlers.py
from app.services.events.events import ProductCreated
from app.services.email import EmailService

class ProductEventHandlers:
    def __init__(self, email_service: EmailService):
        self.email_service = email_service
    
    async def notify_admin_about_new_product(self, event: ProductCreated):
        """Уведомляет администраторов о создании нового продукта"""
        await self.email_service.send_email(
            to="admin@example.com",
            subject=f"Новый продукт: {event.name}",
            body=f"Создан новый продукт:\nID: {event.product_id}\nНазвание: {event.name}\nЦена: {event.price}"
        )
    
    async def update_analytics(self, event: ProductCreated):
        """Обновляет аналитические данные о продуктах"""
        # Логика обновления аналитики
        pass

# Регистрация обработчиков при инициализации приложения
def register_event_handlers(event_bus, email_service):
    handlers = ProductEventHandlers(email_service)
    
    event_bus.subscribe(
        ProductCreated,
        handlers.notify_admin_about_new_product
    )
    
    event_bus.subscribe(
        ProductCreated,
        handlers.update_analytics
    )
```

### Конфигурация в приложении

```python
# main.py
from fastapi import FastAPI
from app.services.events.factory import get_event_bus
from app.services.events.handlers import register_event_handlers
from app.services.email.factory import get_email_service

app = FastAPI()

# Инициализация сервисов
event_bus = get_event_bus()
email_service = get_email_service()

# Регистрация обработчиков событий
register_event_handlers(event_bus, email_service)

# При необходимости можно предоставить доступ к шине через зависимости
app.dependency_overrides[get_event_bus] = lambda: event_bus
```

## Заключение и рекомендации

1. **Начинайте с простой реализации** - усложняйте только при необходимости
2. **Выбирайте подходящую модель доставки** - синхронную или асинхронную в зависимости от требований
3. **Не злоупотребляйте событиями** - используйте для значимых действий в домене
4. **Следите за производительностью** - мониторьте и оптимизируйте при необходимости
5. **Соблюдайте идемпотентность обработчиков** - они должны корректно работать при повторной обработке
6. **Документируйте события** - четко определяйте контракт каждого события
7. **Тестируйте шину и обработчики** - как в изоляции, так и интеграционно

### Рекомендуемые инструменты для расширенной реализации

- **Redis Pub/Sub** - для более масштабируемой версии EventBus
- **RabbitMQ** - для сложных сценариев маршрутизации сообщений
- **Apache Kafka** - для высоконагруженных систем с большим объемом событий
- **Dramatiq/Celery** - для фоновой обработки тяжелых задач

```python
# Пример интеграции с Redis Pub/Sub
import redis.asyncio as redis
import json

class RedisEventBus:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self._handlers = {}
    
    async def subscribe(self, event_type: str, handler: Callable):
        if event_type not in self._handlers:
            self._handlers[event_type] = []
            # Запускаем прослушивание канала в фоне
            asyncio.create_task(self._listen_channel(event_type))
        
        self._handlers[event_type].append(handler)
    
    async def publish(self, event_type: str, event_data: dict):
        await self.redis.publish(event_type, json.dumps(event_data))
    
    async def _listen_channel(self, channel: str):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)
        
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                if channel in self._handlers:
                    tasks = [
                        asyncio.create_task(handler(data))
                        for handler in self._handlers[channel]
                    ]
                    await asyncio.gather(*tasks)
``` 