# PostgreSQL и оптимизация баз данных в FastAPI приложениях

Этот документ объединяет информацию о PostgreSQL, индексах и оптимизации доступа к базам данных из всех предыдущих документов проекта. Здесь собраны ключевые техники, стратегии и рекомендации для работы с базами данных в многоинстансных FastAPI приложениях.

## 1. Индексы PostgreSQL

Индексы — это специальные структуры данных, которые улучшают производительность запросов к базе данных. Основная цель индексов — обеспечить быстрый доступ к строкам таблицы.

### 1.1. Типы индексов в PostgreSQL

PostgreSQL предлагает несколько типов индексов, каждый из которых оптимизирован для определенных сценариев:

1. **B-tree индексы** (по умолчанию)
   - Наиболее распространенный тип индекса
   - Подходят для сравнений с операторами `=`, `<`, `>`, `<=`, `>=`
   - Эффективны для упорядоченных данных и запросов с `ORDER BY`

2. **GiST индексы** (Generalized Search Tree)
   - Подходят для геопространственных данных
   - Используются для полнотекстового поиска
   - Хорошо работают с пользовательскими типами данных

3. **GIN индексы** (Generalized Inverted Index)
   - Оптимизированы для составных типов данных (массивы, jsonb)
   - Эффективны для поиска элементов внутри массивов
   - Занимают больше места, но обеспечивают быстрый поиск

4. **BRIN индексы** (Block Range Index)
   - Подходят для очень больших таблиц с естественной сортировкой
   - Хранят метаданные о диапазонах блоков
   - Компактнее B-tree, но менее точные

5. **Hash индексы**
   - Подходят только для проверки на равенство (`=`)
   - Быстрее B-tree для точного совпадения
   - Не поддерживают упорядочивание

### 1.2. Создание индексов

```sql
-- Простой индекс на одно поле
CREATE INDEX idx_user_email ON users(email);

-- Уникальный индекс (также гарантирует уникальность)
CREATE UNIQUE INDEX idx_user_username ON users(username);

-- Составной индекс (несколько полей)
CREATE INDEX idx_first_last_name ON users(first_name, last_name);

-- Частичный индекс (только для активных пользователей)
CREATE INDEX idx_active_users ON users(email) WHERE active = true;

-- Функциональный индекс (для поиска без учета регистра)
CREATE INDEX idx_lower_email ON users(lower(email));

-- GIN индекс для поиска в JSONB
CREATE INDEX idx_data_json ON documents USING GIN (data);

-- Индекс с включенными полями (для покрытых запросов)
CREATE INDEX idx_user_id_include_name ON users(id) INCLUDE (first_name, last_name);
```

### 1.3. Когда создавать индексы

Индексы следует создавать в следующих случаях:

- На полях, часто используемых в условиях `WHERE`
- На полях, используемых в операциях соединения (`JOIN`)
- На полях, используемых в условиях сортировки (`ORDER BY`)
- На полях, используемых в условиях группировки (`GROUP BY`)
- На полях с ограничением уникальности (`UNIQUE`)

### 1.4. Когда индексы могут быть вредны

- На очень маленьких таблицах, где полное сканирование может быть быстрее
- На часто обновляемых полях, так как каждое изменение данных требует обновления индекса
- При создании избыточных индексов, которые редко используются
- На таблицах, где преобладают операции вставки/обновления над операциями чтения

### 1.5. Анализ использования индексов

```sql
-- Проверка планов выполнения запросов
EXPLAIN ANALYZE SELECT * FROM users WHERE email = 'user@example.com';

-- Статистика использования индексов
SELECT
    indexrelname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- Неиспользуемые индексы
SELECT
    indexrelname,
    relname,
    idx_scan
FROM pg_stat_user_indexes
JOIN pg_stat_user_tables ON idx_stat.relid = pg_stat_user_tables.relid
WHERE idx_scan = 0 AND pg_stat_user_tables.n_live_tup > 0;
```

### 1.6. Оптимизация индексов

- **Покрытые индексы**: Включайте дополнительные поля с помощью `INCLUDE`, чтобы избежать обращения к таблице
- **Периодическая перестройка**: Используйте `REINDEX` для оптимизации фрагментированных индексов
- **Частичные индексы**: Создавайте индексы только для подмножества данных, если запросы часто фильтруют по определенному условию
- **Параллельное создание**: Используйте `CREATE INDEX CONCURRENTLY`, чтобы не блокировать операции записи

## 2. Оптимизация запросов к базе данных

### 2.1. Оптимизация SQL запросов в SQLAlchemy

В SQLAlchemy следует использовать оптимальные подходы для формирования запросов:

```python
# Выбор только необходимых полей
query = session.query(User.id, User.username).filter(User.active == True)

# Использование индексов
query = session.query(User).filter(User.email == 'user@example.com')

# Избегание полного сканирования таблиц
query = session.query(User).filter(User.id.in_([1, 2, 3]))

# Загрузка связанных объектов через joinedload для уменьшения количества запросов
query = session.query(User).options(joinedload(User.posts)).filter(User.id == 1)

# Оптимизация пагинации для больших наборов данных
query = session.query(User).filter(User.id > last_id).order_by(User.id).limit(100)
```

### 2.2. Мониторинг и анализ производительности запросов

PostgreSQL предлагает несколько инструментов для мониторинга производительности:

```sql
-- Включение расширения для анализа запросов
CREATE EXTENSION pg_stat_statements;

-- Получение статистики по запросам
SELECT 
    query, 
    calls, 
    total_time, 
    mean_time, 
    rows
FROM pg_stat_statements
ORDER BY total_time DESC
LIMIT 10;

-- Анализ блокировок в базе данных
SELECT 
    blocked_locks.pid AS blocked_pid,
    blocking_locks.pid AS blocking_pid,
    blocked_activity.usename AS blocked_user,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query AS blocked_statement,
    blocking_activity.query AS blocking_statement
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.DATABASE IS NOT DISTINCT FROM blocked_locks.DATABASE
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
    AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
    AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
    AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.GRANTED;
```

### 2.3. Инструменты мониторинга

- **pg_stat_statements** — Расширение PostgreSQL для анализа запросов
- **pgHero** — Веб-интерфейс для мониторинга PostgreSQL
- **Prometheus + Grafana** — Комплексное решение для мониторинга и визуализации

## 3. Пул соединений

Правильная настройка пула соединений критически важна для многоинстансных приложений.

### 3.1. Настройка пула соединений в SQLAlchemy

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://user:password@localhost/dbname"

# Настройка пула соединений
engine = create_engine(
    DATABASE_URL,
    pool_size=20,  # Начальный размер пула
    max_overflow=10,  # Дополнительные соединения при пиковой нагрузке
    pool_timeout=30,  # Тайм-аут ожидания соединения (секунды)
    pool_recycle=1800,  # Переиспользование соединений каждые 30 минут
    pool_pre_ping=True  # Проверка соединения перед использованием
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

### 3.2. Рекомендации по настройке пула

- **pool_size**: Размер пула должен учитывать количество одновременных запросов и сервисов
- **max_overflow**: Должен покрывать кратковременные пики нагрузки
- **pool_timeout**: Устанавливайте разумные тайм-ауты для предотвращения бесконечного ожидания
- **pool_recycle**: Периодически переустанавливайте соединения для избежания проблем с "протухшими" соединениями
- **pool_pre_ping**: Проверяйте соединения перед использованием, чтобы избежать ошибок с недействительными соединениями

### 3.3. Распределение нагрузки между репликами

Для масштабирования чтения можно использовать репликацию PostgreSQL:

```python
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
@app.post("/users/")
def create_user(user: UserCreate, db: Session = Depends(get_write_db)):
    # Запись всегда идет в мастер
    return crud.create_user(db=db, user=user)

@app.get("/users/")
def list_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_read_db)):
    # Чтение может идти из реплики
    return crud.get_users(db=db, skip=skip, limit=limit)
```

## 4. Управление транзакциями

### 4.1. Основы управления транзакциями в SQLAlchemy

```python
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException

def create_user(db: Session, user_data: dict):
    try:
        user = User(**user_data)
        db.add(user)
        db.commit()
        return user
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Ошибка создания пользователя: {str(e)}")
```

### 4.2. Уровни изоляции транзакций

PostgreSQL поддерживает различные уровни изоляции транзакций:

1. **READ UNCOMMITTED** — транзакции могут видеть незафиксированные изменения (в PostgreSQL эквивалентен READ COMMITTED)
2. **READ COMMITTED** — транзакция видит только зафиксированные изменения на момент начала каждого запроса
3. **REPEATABLE READ** — транзакция видит зафиксированные изменения на момент начала транзакции
4. **SERIALIZABLE** — самый строгий уровень, гарантирует полную изоляцию транзакций

```python
# Установка уровня изоляции
def transfer_funds(db: Session, from_user_id: int, to_user_id: int, amount: float):
    # Установка уровня изоляции для этой транзакции
    db.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
    
    try:
        # Бизнес-логика перевода
        # ...
        
        db.commit()
        return transaction
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
```

### 4.3. ACID свойства

Транзакции должны соответствовать свойствам ACID:

- **Атомарность (Atomicity)**: Транзакция выполняется полностью или не выполняется совсем
- **Согласованность (Consistency)**: База данных переходит из одного согласованного состояния в другое
- **Изолированность (Isolation)**: Транзакции изолированы друг от друга
- **Долговечность (Durability)**: Результаты зафиксированной транзакции сохраняются даже при сбоях

## 5. Механизмы блокировки

### 5.1. Пессимистическая блокировка

Пессимистическая блокировка предотвращает одновременное изменение данных, блокируя записи на время транзакции:

```python
def update_inventory(db: Session, product_id: int, quantity_change: int):
    # SELECT FOR UPDATE блокирует запись для других транзакций
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

### 5.2. Оптимистическая блокировка

Оптимистическая блокировка позволяет нескольким транзакциям работать одновременно, проверяя при фиксации, не были ли данные изменены:

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

### 5.3. Распределенная блокировка с Redis

Для блокировки на уровне нескольких инстансов часто используется Redis:

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

## 6. Идемпотентность транзакций

Идемпотентность гарантирует, что многократное выполнение одной и той же операции приводит к тому же результату, что и однократное.

### 6.1. Реализация идемпотентности с ключами

```python
import uuid
from fastapi import FastAPI, Header, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, Float, DateTime, func

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(String, primary_key=True)
    idempotency_key = Column(String, unique=True, index=True)  # Ключ идемпотентности
    amount = Column(Float)
    created_at = Column(DateTime, default=func.now())
    status = Column(String)

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

### 6.2. Использование UPSERT для идемпотентных операций

PostgreSQL поддерживает операцию `INSERT ... ON CONFLICT ... DO UPDATE` (UPSERT):

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

## 7. Кэширование для снижения нагрузки на базу данных

### 7.1. Кэширование с Redis

Redis эффективен для кэширования часто запрашиваемых данных:

```python
import json
import redis
from fastapi import Depends
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
```

### 7.2. Стратегии кэширования

- **Кэширование на основе времени** (TTL): простой подход, но может возвращать устаревшие данные
- **Инвалидация кэша при изменениях**: актуальные данные, но требует явного управления инвалидацией
- **Кэширование после записи** (write-through): данные записываются одновременно в БД и кэш
- **Кэширование с отложенной записью** (write-behind): данные записываются сначала в кэш, потом в БД

## 8. Тестирование работы с базой данных

### 8.1. Тестирование уровня изоляции транзакций

```python
@pytest.mark.asyncio
async def test_isolation():
    """Тест изоляции - транзакции не должны видеть промежуточных состояний других транзакций"""
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # Создаем общий счет
        account = await client.post("/accounts/", json={"name": "Shared Account", "balance": 1000.0})
        account_id = account.json()["id"]
        
        # Функция для одновременного снятия со счета
        async def withdraw(amount):
            return await client.post("/accounts/withdraw", json={
                "account_id": account_id,
                "amount": amount
            })
        
        # Запускаем 10 параллельных снятий по 100 единиц
        tasks = [withdraw(100.0) for _ in range(10)]
        responses = await asyncio.gather(*tasks)
        
        # Подсчитываем успешные снятия
        successful_withdrawals = sum(1 for r in responses if r.status_code == 200)
        
        # Проверяем финальный баланс
        account_after = await client.get(f"/accounts/{account_id}")
        final_balance = account_after.json()["balance"]
        
        # Баланс должен уменьшиться на сумму успешных снятий
        assert final_balance == 1000.0 - (100.0 * successful_withdrawals)
```

### 8.2. Тестирование идемпотентности

```python
@pytest.mark.asyncio
async def test_payment_idempotency():
    """Тест идемпотентности создания платежа"""
    idempotency_key = str(uuid.uuid4())
    payment_data = {
        "amount": 100.50,
        "currency": "USD",
        "description": "Test payment"
    }
    
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # Первый запрос
        headers = {"Idempotency-Key": idempotency_key}
        first_response = await client.post("/payments/", json=payment_data, headers=headers)
        assert first_response.status_code == 201
        first_result = first_response.json()
        
        # Повторяем тот же запрос с тем же ключом идемпотентности
        second_response = await client.post("/payments/", json=payment_data, headers=headers)
        assert second_response.status_code == 200  # Должен вернуть тот же результат, но с кодом 200
        second_result = second_response.json()
        
        # Проверяем, что ID платежа одинаковый
        assert first_result["id"] == second_result["id"]
        
        # Проверяем, что во втором ответе есть флаг идемпотентности
        assert second_result.get("idempotency_applied") == True
```

### 8.3. Инструменты для тестирования базы данных

- **pytest-asyncio** — для асинхронных тестов
- **httpx** — HTTP клиент для асинхронных запросов
- **Locust** — для нагрузочного тестирования
- **chaostoolkit** — для chaos engineering
- **pgHero** — для мониторинга PostgreSQL во время тестов

## 9. Общие рекомендации и выводы

1. **Используйте индексы эффективно**:
   - Создавайте индексы на полях, часто используемых в запросах
   - Избегайте избыточных индексов
   - Регулярно анализируйте производительность запросов

2. **Оптимизируйте пул соединений**:
   - Настраивайте размер пула в соответствии с ожидаемой нагрузкой
   - Используйте проверку соединений перед использованием (pool_pre_ping)
   - Периодически переустанавливайте соединения (pool_recycle)

3. **Выбирайте подходящие уровни изоляции транзакций**:
   - Используйте более низкие уровни для повышения производительности
   - Используйте более высокие уровни для критических операций

4. **Обеспечивайте идемпотентность операций**:
   - Используйте ключи идемпотентности для всех изменяющих операций
   - Проверяйте наличие дубликатов перед выполнением операций
   - Документируйте поведение API при повторных запросах

5. **Используйте блокировки осмотрительно**:
   - Предпочитайте оптимистическую блокировку, когда возможно
   - Используйте пессимистическую блокировку для критических ресурсов
   - Разделяйте блокировки на чтение и запись для повышения производительности

6. **Кэшируйте часто запрашиваемые данные**:
   - Используйте Redis или другие распределенные кэши
   - Инвалидируйте кэш при изменении данных
   - Устанавливайте разумные TTL для автоматической инвалидации

7. **Регулярно тестируйте производительность и конкурентность**:
   - Проводите нагрузочное тестирование
   - Тестируйте сценарии гонок данных
   - Проверяйте правильность реализации ACID-свойств

Эти стратегии в сочетании позволяют создавать надежные, масштабируемые и производительные FastAPI приложения с эффективным доступом к PostgreSQL базам данных. 