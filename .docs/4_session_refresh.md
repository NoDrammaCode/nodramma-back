# Метод session.refresh() в SQLAlchemy

## Назначение метода

Метод `session.refresh(entity)` в SQLAlchemy выполняет обновление состояния объекта из базы данных, загружая актуальные данные. Это особенно важно после операций вставки или обновления данных.

В контексте нашего приложения, метод используется в репозиториях после выполнения операций изменения данных:

```python
# product/pg_repository.py

async def create_product(self, product: Product, session: AsyncSession) -> Product:
    session.add(product)
    await session.commit()
    await session.refresh(product)  # Обновление состояния объекта из БД
    return product
```

## Для чего используется

### Получение автогенерируемых данных

- **Идентификаторы (автоинкрементные ID)** - после вставки новой записи необходимо получить сгенерированный ID
- **Значения по умолчанию (default values)** - поля с дефолтными значениями, определёнными на уровне БД
- **Вычисляемые поля (computed columns)** - поля, значения которых вычисляются на основе других полей
- **Временные метки (created_at, updated_at)** - автоматически обновляемые метки времени

```python
# Пример модели с автогенерируемыми полями
class Product(Base):
    id: Mapped[int] = mapped_column(primary_key=True)  # Автоинкремент
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(default=func.now())  # Значение по умолчанию
    updated_at: Mapped[datetime] = mapped_column(onupdate=func.now())  # Автоматическое обновление
```

### Согласованность данных

- **Гарантирует актуальность данных** - объект в памяти отражает текущее состояние в БД
- **Загружает данные из триггеров** - учитывает изменения, внесенные триггерами БД
- **Повышает надежность приложения** - устраняет расхождения между памятью и БД

### Решение проблем в асинхронном контексте

В асинхронных приложениях обновление данных особенно важно:

- **Предотвращает race conditions** - гарантирует, что мы работаем с актуальными данными
- **Улучшает параллельную обработку** - важно при одновременном доступе к данным
- **Предотвращает ошибки сериализации** - особенно при преобразовании ORM-моделей в JSON

## Когда нужно использовать

Метод `session.refresh()` следует использовать в следующих случаях:

1. **После операции `commit()`**, если объект будет использоваться дальше:

```python
async def update_product(self, product_id: int, product: Product, session: AsyncSession) -> Product | None:
    existing_product = await self.get_product(product_id, session)
    if existing_product:
        existing_product.name = product.name
        existing_product.description = product.description
        existing_product.price = product.price
        await session.commit()
        await session.refresh(existing_product)  # Обновляем после изменений
        return existing_product
    return None
```

2. **Перед возвратом объекта из репозитория** - гарантирует, что API вернет актуальные данные
3. **При работе с полями, значения которых генерируются на стороне БД** - например, вычисляемые столбцы
4. **После массовых операций обновления** - когда изменялись связанные объекты

## Связь с другими настройками

### Параметр `expire_on_commit=False`

В нашем приложении при создании фабрики сессий используется параметр `expire_on_commit=False`:

```python
# app/db/pg_client.py
async_session = async_sessionmaker(engine, expire_on_commit=False)
```

Это важная настройка, которая влияет на жизненный цикл объектов:

- **При `expire_on_commit=True` (значение по умолчанию)** - все объекты, связанные с сессией, помечаются как "устаревшие" (expired) после `commit()`. При следующем доступе к их атрибутам SQLAlchemy автоматически выполнит запрос к БД для загрузки свежих данных.

- **При `expire_on_commit=False`** - объекты не помечаются как устаревшие после коммита, что улучшает производительность, но требует явного вызова `session.refresh()` для обновления данных.

### Преимущества отключения `expire_on_commit`

1. **Улучшение производительности** - меньше автоматических запросов к БД
2. **Более предсказуемое поведение** - данные обновляются только когда это явно запрошено
3. **Предотвращение проблем с lazy-loading** - особенно важно в асинхронных приложениях

### Недостатки отключения `expire_on_commit`

1. **Необходимость явного вызова refresh()** - требуется помнить о необходимости обновления данных
2. **Риск использования устаревших данных** - если забыть вызвать refresh()

## Рекомендации по использованию

### 1. Всегда вызывайте `session.refresh()` после операций изменения данных

Метод `session.refresh()` гарантирует актуальность данных в нескольких ключевых аспектах:

#### Технический процесс обновления данных

При вызове `session.refresh(entity)` SQLAlchemy выполняет следующие действия:
1. Формирует SQL-запрос SELECT для извлечения актуальных данных объекта из БД
2. Отправляет запрос к базе данных
3. Получает свежие данные
4. Обновляет все атрибуты объекта в памяти в соответствии с полученными данными

#### Обработка автогенерируемых данных

После операций `INSERT` или `UPDATE` база данных может генерировать или изменять значения:

```python
# Создание продукта
product = Product(name="Новый продукт", price=1000)
session.add(product)
await session.commit()

# В этот момент product.id может быть None в памяти, 
# хотя в БД уже сгенерирован ID

await session.refresh(product)
# Теперь product.id содержит сгенерированное значение из БД
print(f"Продукт создан с ID: {product.id}")
```

#### Синхронизация с триггерами БД

Если в базе данных настроены триггеры, они могут модифицировать данные:

```sql
-- Пример триггера PostgreSQL, который устанавливает цену со скидкой
CREATE OR REPLACE FUNCTION calculate_discount() RETURNS TRIGGER AS $$
BEGIN
    NEW.discounted_price := NEW.price * 0.9;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER apply_discount BEFORE INSERT OR UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION calculate_discount();
```

```python
# Без refresh() мы не увидим значение поля discounted_price
product = Product(name="Товар со скидкой", price=1000)
session.add(product)
await session.commit()
await session.refresh(product)
# Теперь product.discounted_price содержит значение, рассчитанное триггером
print(f"Цена: {product.price}, Цена со скидкой: {product.discounted_price}")
```

#### Когда особенно критично для согласованности данных

1. **При работе с высоконагруженными системами**:
   ```python
   # Пример конкурентного обновления счетчика
   product = await session.get(Product, product_id)
   product.view_count += 1
   await session.commit()
   await session.refresh(product)  # Получаем актуальное значение с учетом других параллельных изменений
   ```

2. **В случае вычисляемых полей**:
   ```python
   # Пример с товаром, у которого есть вычисляемое поле total = price * quantity
   product.price = new_price
   product.quantity = new_quantity
   await session.commit()
   await session.refresh(product)  # Получаем обновленное значение поля total
   ```

3. **При работе с полями, обновляемыми внешними системами**:
   ```python
   # Например, поле payment_status может обновляться внешней платежной системой
   order = await session.get(Order, order_id)
   await session.refresh(order)  # Получаем актуальный платежный статус
   if order.payment_status == "paid":
       await process_paid_order(order)
   ```

### 2. Используйте этот метод перед возвратом данных из репозитория
### 3. Обновляйте объекты после операций, затрагивающих автогенерируемые поля
### 4. Помните о влиянии `expire_on_commit=False` - в нашей конфигурации refresh особенно важен

## Пример использования в проекте

```python
# Создание нового продукта
async def create_product(self, product: Product, session: AsyncSession) -> Product:
    session.add(product)
    await session.commit()
    await session.refresh(product)  # Получаем ID и другие автогенерируемые поля
    return product

# Обновление существующего продукта
async def update_product(self, product_id: int, product: Product, session: AsyncSession) -> Product | None:
    existing_product = await self.get_product(product_id, session)
    if existing_product:
        existing_product.name = product.name
        existing_product.description = product.description
        existing_product.price = product.price
        await session.commit()
        await session.refresh(existing_product)  # Обновляем все поля, включая updated_at
        return existing_product
    return None
```
