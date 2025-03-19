# Конкурентный доступ к базе данных в многоинстансных FastAPI приложениях

В этом документе описываются проблемы конкурентного доступа к базе данных в FastAPI приложениях, развернутых на нескольких инстансах, и предлагаются стратегии для смягчения этих проблем с конкретными примерами реализации в коде.

## Проблема: Конкурентный доступ

Когда FastAPI приложение развернуто на нескольких инстансах (например, в кластере Kubernetes или с использованием Docker Swarm), каждый инстанс работает независимо, но обычно подключается к одной и той же базе данных. Это может привести к нескольким проблемам, связанным с конкурентным доступом:

*   **Deadlock (Взаимная блокировка):** Инстансы могут блокировать друг друга, ожидая доступа к ресурсам базы данных, что приводит к остановке приложения.
*   **Гонка данных:** Одновременные попытки изменить одни и те же данные могут привести к потере данных или повреждению данных.
*   **Ограничения масштабирования:** База данных может стать узким местом, если она не может справиться с комбинированной нагрузкой от всех инстансов приложения.

## Стратегии для смягчения проблем и их реализация

### 1. Оптимизация запросов к базе данных

Убедитесь, что ваши запросы к базе данных эффективны и минимизируют потребление ресурсов.

*   **Индексирование:** Используйте соответствующие индексы для ускорения извлечения данных.
*   **Анализ запросов:** Проанализируйте производительность запросов и определите области для оптимизации.
*   **Избегайте полного сканирования таблиц:** Разрабатывайте запросы, чтобы избежать сканирования целых таблиц.

**Пример реализации индексирования:**

```python
from sqlalchemy import Column, Integer, String, Index
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True)  # Индексирование часто запрашиваемых полей
    email = Column(String, unique=True)
    full_name = Column(String)
    
    # Создание составного индекса
    __table_args__ = (
        Index('idx_user_email_name', email, full_name),
    )
```

**Пример оптимизированного запроса:**

```python
# Менее оптимальный запрос
users = db.query(User).filter(User.full_name.like("%Smith%")).all()

# Оптимизированный запрос с использованием индекса
users = db.query(User).filter(User.username == "jsmith").first()

# Запрос с выбором только нужных полей
usernames = db.query(User.username).filter(User.email.like("%@example.com")).all()
```

### 2. Пул соединений

Используйте пул соединений SQLAlchemy для повторного использования соединений с базой данных и снижения накладных расходов на установление новых соединений.

*   **Настройка размера пула:** Отрегулируйте размер пула в соответствии с ожидаемым уровнем параллелизма.
*   **Переполнение пула:** Установите разумный предел переполнения пула для обработки случайных всплесков трафика.
*   **Тайм-аут пула:** Настройте тайм-аут, чтобы предотвратить удержание соединений на неопределенный срок.

**Пример настройки пула соединений:**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://user:password@localhost/dbname"

# Настройка пула соединений
engine = create_engine(
    DATABASE_URL,
    pool_size=20,  # Начальный размер пула
    max_overflow=10,  # Допустимое количество дополнительных соединений
    pool_timeout=30,  # Тайм-аут ожидания соединения (секунды)
    pool_recycle=1800,  # Переиспользование соединений каждые 30 минут
    pool_pre_ping=True  # Проверка соединения перед использованием
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Зависимость для FastAPI с правильной обработкой сессий
def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()  # Откат при ошибке
        raise
    finally:
        db.close()  # Всегда закрываем сессию
```

### 3. Управление транзакциями

Используйте транзакции для группировки нескольких операций базы данных в одну атомарную единицу.

*   **ACID свойства:** Убедитесь, что транзакции соответствуют свойствам ACID (Атомарность, Согласованность, Изолированность, Долговечность).
*   **Уровни изоляции:** Выберите соответствующий уровень изоляции транзакций для балансировки параллелизма и согласованности данных.

**Пример управления транзакциями с разными уровнями изоляции:**

```python
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException

# Стандартная транзакция
def create_user(db: Session, user_data: dict):
    try:
        user = User(**user_data)
        db.add(user)
        db.commit()
        return user
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Ошибка создания пользователя: {str(e)}")

# Транзакция с настройкой уровня изоляции
def transfer_funds(db: Session, from_user_id: int, to_user_id: int, amount: float):
    # Установка уровня изоляции для этой транзакции
    db.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
    
    try:
        # Находим пользователей и блокируем их записи
        from_user = db.query(User).filter(User.id == from_user_id).with_for_update().first()
        to_user = db.query(User).filter(User.id == to_user_id).with_for_update().first()
        
        if not from_user or not to_user:
            raise ValueError("Пользователь не найден")
        
        if from_user.balance < amount:
            raise ValueError("Недостаточно средств")
        
        # Выполняем перевод
        from_user.balance -= amount
        to_user.balance += amount
        
        # Записываем транзакцию
        transaction = Transaction(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            amount=amount
        )
        db.add(transaction)
        
        db.commit()
        return transaction
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

### 3.1 Идемпотентность транзакций

Идемпотентность — важное свойство операций, при котором многократное выполнение одной и той же операции приводит к тому же результату, что и однократное. В контексте многоинстансных приложений это особенно важно, так как:

* Сетевые ошибки могут вызывать повторные запросы
* При сбоях могут происходить автоматические повторные попытки
* Пользователи могут случайно дублировать запросы (например, многократное нажатие кнопки)

**Стратегии обеспечения идемпотентности:**

1. **Идентификаторы идемпотентности**
2. **Условные операции**
3. **Проверка перед выполнением**
4. **Использование природных идемпотентных операций**

**Пример с идентификатором идемпотентности:**

```python
import uuid
from fastapi import FastAPI, Header, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, Float, DateTime, func
from datetime import datetime

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(String, primary_key=True)
    idempotency_key = Column(String, unique=True, index=True)  # Ключ идемпотентности
    amount = Column(Float)
    created_at = Column(DateTime, default=func.now())
    status = Column(String)

# В FastAPI маршруте
@app.post("/payments/")
async def create_payment(
    payment_data: PaymentCreate,
    idempotency_key: str = Header(...),  # Обязательный заголовок
    db: Session = Depends(get_db)
):
    # Проверяем, существует ли операция с таким ключом идемпотентности
    existing_payment = db.query(Payment).filter(
        Payment.idempotency_key == idempotency_key
    ).first()
    
    # Если операция с таким ключом уже существует, просто возвращаем её
    if existing_payment:
        return {
            "id": existing_payment.id,
            "amount": existing_payment.amount,
            "status": existing_payment.status,
            "created_at": existing_payment.created_at,
            "idempotency_applied": True  # Флаг, что это повторный запрос
        }
    
    # Создаем новую операцию
    payment_id = str(uuid.uuid4())
    new_payment = Payment(
        id=payment_id,
        idempotency_key=idempotency_key,
        amount=payment_data.amount,
        status="completed"
    )
    
    try:
        db.add(new_payment)
        db.commit()
        db.refresh(new_payment)
        return {
            "id": new_payment.id,
            "amount": new_payment.amount,
            "status": new_payment.status,
            "created_at": new_payment.created_at,
            "idempotency_applied": False
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Ошибка создания платежа: {str(e)}")
```

**Пример условной операции:**

```python
from sqlalchemy.exc import IntegrityError

def create_order_idempotent(db: Session, order_data: dict, order_reference: str):
    """Идемпотентное создание заказа с использованием природного ключа"""
    
    # Проверяем существование заказа по референсу
    existing_order = db.query(Order).filter(Order.reference == order_reference).first()
    
    if existing_order:
        # Заказ уже существует, возвращаем его
        return existing_order, True
    
    # Создаем новый заказ
    new_order = Order(
        reference=order_reference,
        **order_data
    )
    
    try:
        db.add(new_order)
        db.commit()
        db.refresh(new_order)
        return new_order, False
    except IntegrityError:
        # На случай гонки данных - другой инстанс мог успеть создать заказ
        # между нашей проверкой и вставкой
        db.rollback()
        existing_order = db.query(Order).filter(Order.reference == order_reference).first()
        if existing_order:
            return existing_order, True
        else:
            # Если заказ всё-таки не найден, это какая-то другая ошибка
            raise
```

**Пример использования ON CONFLICT при вставке:**

```python
from sqlalchemy.dialects.postgresql import insert

def upsert_product(db: Session, product_data: dict):
    """Идемпотентное обновление продукта с использованием UPSERT"""
    
    # Создаем выражение вставки
    stmt = insert(Product).values(
        sku=product_data['sku'],
        name=product_data['name'],
        price=product_data['price']
    )
    
    # Добавляем DO UPDATE SET для обновления существующей записи
    # Используем clause ON CONFLICT для обработки нарушения уникальности
    stmt = stmt.on_conflict_do_update(
        index_elements=['sku'],  # Уникальный индекс
        set_={
            'name': product_data['name'],
            'price': product_data['price'],
            'updated_at': func.now()
        }
    )
    
    db.execute(stmt)
    db.commit()
    
    # Возвращаем обновленный/вставленный продукт
    return db.query(Product).filter(Product.sku == product_data['sku']).first()
```

**Использование транзакционных блокировок для идемпотентности:**

```python
def process_order_idempotent(db: Session, order_id: int, idempotency_key: str):
    """Идемпотентная обработка заказа с блокировкой"""
    
    # Начинаем транзакцию с высоким уровнем изоляции
    db.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
    
    try:
        # Проверяем, была ли уже обработка с таким ключом идемпотентности
        processed = db.query(OrderProcessingLog).filter(
            OrderProcessingLog.idempotency_key == idempotency_key
        ).with_for_update().first()
        
        if processed:
            # Операция уже выполнялась
            db.commit()
            return {"status": "already_processed", "order_id": order_id}
        
        # Блокируем запись заказа
        order = db.query(Order).filter(Order.id == order_id).with_for_update().first()
        if not order:
            db.rollback()
            raise ValueError(f"Заказ {order_id} не найден")
        
        # Выполняем основную бизнес-логику
        process_result = process_order_logic(db, order)
        
        # Логируем факт обработки с ключом идемпотентности
        log_entry = OrderProcessingLog(
            order_id=order_id,
            idempotency_key=idempotency_key,
            result=process_result
        )
        db.add(log_entry)
        
        db.commit()
        return {"status": "processed", "order_id": order_id, "result": process_result}
    except Exception as e:
        db.rollback()
        raise
```

**Рекомендации по идемпотентности в API:**

1. **Используйте HTTP идемпотентные методы правильно:**
   - GET, HEAD, PUT, DELETE — идемпотентны по своей природе
   - POST — не идемпотентен, требует дополнительных механизмов

2. **Принимайте ключи идемпотентности для всех изменяющих операций:**
   - Клиент генерирует UUID для каждого запроса
   - Сервер проверяет, был ли запрос с таким ключом уже обработан

3. **Ограничивайте время хранения информации об идемпотентности:**
   - Храните историю ключей идемпотентности ограниченное время
   - Используйте TTL для автоматической очистки

4. **Документируйте поведение при повторных запросах:**
   - Явно указывайте в документации API, как система обрабатывает повторные запросы
   - Опишите требования к заголовкам идемпотентности

### 4. Механизмы блокировки

Используйте механизмы блокировки для защиты критических ресурсов базы данных от одновременного изменения.

*   **Пессимистическая блокировка:** Получите блокировки перед доступом к ресурсам, чтобы предотвратить одновременное изменение. Используйте с осторожностью, чтобы избежать взаимных блокировок.
*   **Оптимистическая блокировка:** Проверьте наличие изменений данных перед фиксацией изменений. Если обнаружен конфликт, повторите операцию.

**Пример пессимистической блокировки с SELECT FOR UPDATE:**

```python
def update_inventory(db: Session, product_id: int, quantity_change: int):
    # Блокировка записи на время транзакции
    product = db.query(Product).with_for_update().filter(Product.id == product_id).first()
    if not product:
        raise ValueError("Товар не найден")
    
    # Запись заблокирована для других транзакций
    new_quantity = product.quantity + quantity_change
    
    if new_quantity < 0:
        db.rollback()
        raise ValueError("Недостаточное количество товара")
    
    product.quantity = new_quantity
    db.commit()
    return product
```

**Пример оптимистической блокировки с версионностью:**

```python
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm.exc import StaleDataError

class Item(Base):
    __tablename__ = "items"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(String)
    version = Column(Integer, default=1)  # Версия для оптимистической блокировки
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

def update_item(db: Session, item_id: int, item_data: dict, version: int):
    # Проверяем, не изменилась ли запись с момента чтения
    result = db.query(Item).filter(
        Item.id == item_id, 
        Item.version == version
    ).update(
        {**item_data, "version": Item.version + 1},
        synchronize_session=False
    )
    
    if result == 0:
        # Версия не совпала - кто-то уже изменил запись
        raise StaleDataError("Кто-то уже изменил эту запись. Пожалуйста, обновите данные и попробуйте снова.")
    
    db.commit()
    return db.query(Item).filter(Item.id == item_id).first()
```

**Пример распределенной блокировки с Redis:**

```python
import redis
import uuid
from fastapi import HTTPException

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def acquire_lock(lock_name: str, expire_seconds: int = 10) -> str:
    """Получение распределенной блокировки"""
    lock_id = str(uuid.uuid4())
    # Пытаемся установить блокировку с уникальным ID
    acquired = redis_client.set(f"lock:{lock_name}", lock_id, nx=True, ex=expire_seconds)
    if not acquired:
        raise HTTPException(status_code=423, detail="Ресурс заблокирован, попробуйте позже")
    return lock_id

def release_lock(lock_name: str, lock_id: str) -> bool:
    """Освобождение блокировки (только если это наша блокировка)"""
    # Используем Lua-скрипт для атомарной проверки и удаления
    script = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    """
    result = redis_client.eval(script, 1, f"lock:{lock_name}", lock_id)
    return result == 1

# Использование в маршруте
async def critical_operation(resource_id: int):
    lock_id = acquire_lock(f"resource:{resource_id}")
    try:
        # Выполняем критическую операцию
        result = process_resource(resource_id)
        return result
    finally:
        release_lock(f"resource:{resource_id}", lock_id)
```

### 5. Масштабирование базы данных

Если база данных становится узким местом, рассмотрите возможность масштабирования инфраструктуры базы данных.

*   **Вертикальное масштабирование:** Увеличьте ресурсы (ЦП, память, хранилище) сервера базы данных.
*   **Горизонтальное масштабирование:** Распределите нагрузку базы данных между несколькими серверами с использованием репликации или шардирования.

**Пример настройки маршрутизации запросов для чтения и записи:**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Настройка подключений к основной и реплике БД
master_engine = create_engine("postgresql://user:password@master-host/dbname", pool_size=10)
replica_engine = create_engine("postgresql://user:password@replica-host/dbname", pool_size=20)

# Создание сессий
MasterSession = sessionmaker(bind=master_engine)
ReplicaSession = sessionmaker(bind=replica_engine)

# Зависимости для FastAPI
def get_write_db():
    db = MasterSession()
    try:
        yield db
    finally:
        db.close()

def get_read_db():
    db = ReplicaSession()
    try:
        yield db
    finally:
        db.close()

# Маршруты с использованием разных подключений
@app.post("/users/", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_write_db)):
    # Запись всегда идет в мастер
    return crud.create_user(db=db, user=user)

@app.get("/users/", response_model=List[UserResponse])
def list_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_read_db)):
    # Чтение может идти из реплики
    return crud.get_users(db=db, skip=skip, limit=limit)
```

### 6. Стратегии кэширования

Внедрите кэширование, чтобы снизить нагрузку на базу данных.

*   **Кэширование в памяти:** Кэшируйте часто используемые данные в памяти приложения.
*   **Распределенное кэширование:** Используйте распределенный кэш (например, Redis, Memcached) для обмена кэшированными данными между несколькими инстансами.
*   **CDN кэширование:** Кэшируйте статические ресурсы с помощью сети доставки контента (CDN).

**Пример кэширования с помощью Redis:**

```python
import json
import redis
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

# Клиент Redis для кэширования
redis_client = redis.Redis(host='localhost', port=6379, db=0)

# Функция для получения данных с кэшированием
async def get_cached_items(db: Session = Depends(get_db)):
    # Пробуем получить из кэша
    cache_key = "all_items"
    cached_data = redis_client.get(cache_key)
    
    if cached_data:
        # Данные есть в кэше
        return json.loads(cached_data)
    
    # Данных нет в кэше - получаем из БД
    items = db.query(Item).all()
    items_data = [{"id": item.id, "name": item.name} for item in items]
    
    # Сохраняем в кэш на 5 минут
    redis_client.setex(cache_key, 300, json.dumps(items_data))
    
    return items_data

# Функция для инвалидации кэша при изменениях
def invalidate_items_cache():
    redis_client.delete("all_items")

# Маршрут с использованием кэша
@app.get("/items/")
async def read_items():
    return await get_cached_items()

# Маршрут, который изменяет данные и инвалидирует кэш
@app.post("/items/")
def create_item(item: ItemCreate, db: Session = Depends(get_db)):
    db_item = Item(**item.dict())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    
    # Инвалидируем кэш после изменения данных
    invalidate_items_cache()
    
    return db_item
```

### 7. Асинхронная обработка тяжелых операций

Используйте асинхронную обработку для операций, которые могут занять много времени или ресурсов базы данных.

**Пример с использованием Taskiq:**

```python
from taskiq import TaskiqScheduler, AsyncBroker, Context, ZeroMQBroker
from taskiq.brokers.asyncio_broker import AsyncioBroker
from taskiq.schedule_sources import LabelScheduleSource
from fastapi import FastAPI, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta

# Создаем брокер для задач
# Можно использовать разные брокеры: Redis, ZeroMQ, RabbitMQ, или даже простой AsyncioBroker
broker = AsyncioBroker()
# Для распределенной системы лучше использовать сетевой брокер:
# broker = ZeroMQBroker(url="tcp://127.0.0.1:5555")
# broker = RedisBroker(redis_url="redis://localhost:6379/0")

# Регистрируем асинхронную задачу
@broker.task(retry_policy={
    "max_retries": 3,
    "delay": timedelta(seconds=5),
    "backoff": 2.0,
})
async def process_heavy_task(data_id: int, ctx: Context):
    """
    Асинхронная обработка тяжелой задачи с базой данных
    """
    # Инициализация подключения к БД
    async_session = get_async_session()
    
    async with async_session() as session:
        try:
            # Выполнение тяжелой операции с базой данных
            # Например, обработка аналитических данных, генерация сложных отчетов и т.д.
            data = await process_large_data_set(session, data_id)
            
            # Например, обновляем статус задачи в БД
            await update_task_status(session, data_id, "completed", data)
            
            # Фиксируем транзакцию
            await session.commit()
            
            return {"status": "success", "result": data}
        except Exception as e:
            await session.rollback()
            # Логируем ошибку
            logger.error(f"Ошибка при обработке задачи {data_id}: {str(e)}")
            # Помечаем как требующую повторной попытки
            raise

# Пример настройки планировщика задач
scheduler = TaskiqScheduler(
    broker=broker,
    sources=[
        LabelScheduleSource(broker),
    ],
)

# Пример регулярной задачи, которая запускается каждый день в полночь
@broker.task(
    label="daily-cleanup",
    cron="0 0 * * *"  # Каждый день в 00:00
)
async def cleanup_old_data():
    """Очистка старых данных из базы"""
    # Реализация очистки

# Интеграция с FastAPI
app = FastAPI()

# Маршрут для запуска асинхронной задачи
@app.post("/process-data/{data_id}")
async def start_processing(data_id: int):
    # Отправляем задачу на асинхронное выполнение
    task_id = await process_heavy_task.kiq(data_id)
    
    # Возвращаем ID задачи для последующей проверки статуса
    return {"task_id": str(task_id), "status": "processing"}

# Маршрут для проверки статуса задачи
@app.get("/task-status/{task_id}")
async def check_task_status(task_id: str):
    # Получаем результат задачи из хранилища результатов
    task_result = await broker.result_backend.get_result(task_id)
    
    if not task_result:
        return {"task_id": task_id, "status": "pending"}
    
    return {
        "task_id": task_id,
        "status": "completed" if task_result.is_success else "failed",
        "result": task_result.return_value if task_result.is_success else None,
        "error": str(task_result.exception) if task_result.exception else None,
    }

# Маршрут с использованием FastAPI BackgroundTasks (для легких задач в рамках одного инстанса)
async def simple_background_task(item_id: int, db: AsyncSession):
    # Код фоновой задачи
    await process_item_async(db, item_id)

@app.post("/items/{item_id}/process")
async def process_item(
    item_id: int, 
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db)
):
    # Планируем фоновую задачу в рамках текущего запроса
    # Подходит для легких задач, не требующих повторных попыток
    background_tasks.add_task(simple_background_task, item_id, db)
    return {"status": "processing started"}

# При старте приложения запускаем планировщик задач
@app.on_event("startup")
async def start_scheduler():
    await scheduler.start()

# При завершении приложения останавливаем брокер и планировщик
@app.on_event("shutdown")
async def shutdown_broker():
    await scheduler.stop()
    await broker.shutdown()
```

Преимущества Taskiq по сравнению с Celery:

1. **Полностью асинхронный (async/await)** - построен с учетом современных паттернов асинхронного программирования Python
2. **Типизация** - поддержка подсказок типов для более безопасного кода
3. **Более простой API** - интуитивный интерфейс, меньше шаблонного кода
4. **Модульное строение** - можно заменять компоненты (брокеры, хранилища результатов) независимо
5. **Встроенная поддержка ретраев** - гибкие политики повторных попыток с экспоненциальной задержкой
6. **Интеграция с FastAPI** - удобно использовать в экосистеме FastAPI

Taskiq хорошо подходит для микросервисных архитектур и особенно эффективен в окружениях, где используется асинхронный Python.

## Вывод

Управление конкурентным доступом к базе данных в многоинстансных FastAPI приложениях требует сочетания тщательного проектирования базы данных, эффективной оптимизации запросов и соответствующих механизмов управления параллелизмом. Реализуя стратегии, изложенные в этом документе, вы можете создавать масштабируемые и надежные приложения, которые могут обрабатывать высокие уровни параллелизма.

Ключевые моменты для успешного управления конкурентностью:

1. **Используйте подходящие индексы** и оптимизируйте запросы к базе данных
2. **Правильно настраивайте пул соединений** с учетом ожидаемой нагрузки
3. **Применяйте транзакции** с соответствующими уровнями изоляции
4. **Выбирайте правильный механизм блокировки** (оптимистический или пессимистический)
5. **Кэшируйте часто запрашиваемые данные** для снижения нагрузки на базу данных
6. **Выносите тяжелые операции** в асинхронные задачи
7. **Масштабируйте базу данных** при необходимости с разделением чтения и записи