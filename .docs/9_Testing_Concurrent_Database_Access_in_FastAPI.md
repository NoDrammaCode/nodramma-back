# Тестирование конкурентного доступа к базе данных в FastAPI приложениях

В этом документе описываются методы и инструменты для тестирования многоинстансных FastAPI приложений на предмет корректной работы при конкурентном доступе к базе данных. Документ включает планы тестирования и практические рекомендации для проверки нагрузочной способности, устойчивости к гонкам данных, идемпотентности операций и соблюдения ACID-свойств.

## Зачем нужно специальное тестирование конкурентности?

Проблемы конкурентного доступа часто проявляются только при специфических условиях, которые трудно воспроизвести в обычных модульных или интеграционных тестах:

* Гонки данных возникают при определенных временных интервалах между операциями
* Проблемы масштабирования заметны только при высокой нагрузке
* Deadlocks случаются нерегулярно и при сложных паттернах доступа к данным
* Нарушения идемпотентности могут проявляться только при редких сценариях повторных запросов

Поэтому требуются специальные методы тестирования, нацеленные на выявление этих конкретных проблем.

## 1. Создание локальной среды для тестирования нескольких инстансов

Первый шаг — настройка локальной среды для запуска нескольких инстансов вашего приложения.

### Docker Compose для локального тестирования

```yaml
# docker-compose.yml
version: '3.8'

services:
  database:
    image: postgres:14
    environment:
      POSTGRES_USER: testuser
      POSTGRES_PASSWORD: testpass
      POSTGRES_DB: testdb
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U testuser -d testdb"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  app1:
    build: .
    environment:
      DATABASE_URL: postgresql://testuser:testpass@database:5432/testdb
      REDIS_URL: redis://redis:6379/0
      APP_INSTANCE: instance1
    ports:
      - "8001:8000"
    depends_on:
      database:
        condition: service_healthy
      redis:
        condition: service_healthy

  app2:
    build: .
    environment:
      DATABASE_URL: postgresql://testuser:testpass@database:5432/testdb
      REDIS_URL: redis://redis:6379/0
      APP_INSTANCE: instance2
    ports:
      - "8002:8000"
    depends_on:
      database:
        condition: service_healthy
      redis:
        condition: service_healthy

  app3:
    build: .
    environment:
      DATABASE_URL: postgresql://testuser:testpass@database:5432/testdb
      REDIS_URL: redis://redis:6379/0
      APP_INSTANCE: instance3
    ports:
      - "8003:8000"
    depends_on:
      database:
        condition: service_healthy
      redis:
        condition: service_healthy

  loadbalancer:
    image: nginx:alpine
    ports:
      - "8000:80"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
    depends_on:
      - app1
      - app2
      - app3

volumes:
  postgres_data:
```

### Nginx конфигурация для балансировки нагрузки

```nginx
# nginx.conf
upstream fastapi_app {
    server app1:8000;
    server app2:8000;
    server app3:8000;
}

server {
    listen 80;
    
    location / {
        proxy_pass http://fastapi_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 2. Тестирование нагрузки и производительности

### Инструменты для нагрузочного тестирования

1. **Locust** — открытый инструмент для нагрузочного тестирования с веб-интерфейсом

```python
# locustfile.py
from locust import HttpUser, task, between

class APIUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(3)
    def get_items(self):
        self.client.get("/items/")
    
    @task
    def create_item(self):
        self.client.post("/items/", json={
            "name": "Test Item",
            "description": "Created during load test"
        })
    
    @task
    def update_item(self):
        # Обновление существующих элементов
        # Тестирует конкурентное обновление
        items = self.client.get("/items/").json()
        if items:
            item_id = items[0]['id']
            self.client.put(f"/items/{item_id}", json={
                "name": "Updated Item",
                "description": "Updated during load test"
            })
```

2. **k6** — современный инструмент нагрузочного тестирования от Grafana

```javascript
// script.js для k6
import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  stages: [
    { duration: '30s', target: 20 },   // Постепенное увеличение до 20 VUs
    { duration: '1m', target: 20 },    // Поддержание 20 VUs в течение 1 минуты
    { duration: '30s', target: 50 },   // Увеличение до 50 VUs
    { duration: '2m', target: 50 },    // Поддержание 50 VUs
    { duration: '30s', target: 0 },    // Снижение до 0 VUs
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'], // 95% запросов должны выполняться быстрее 500 мс
    'http_req_duration{staticAsset:yes}': ['p(95)<100'], // Статические ресурсы быстрее 100 мс
  },
};

export default function() {
  // GET запрос - чтение данных
  let getResponse = http.get('http://localhost:8000/items/');
  check(getResponse, { 'status was 200': (r) => r.status == 200 });
  
  // POST запрос - создание новых данных
  let postResponse = http.post('http://localhost:8000/items/', JSON.stringify({
    name: 'Test Item',
    description: 'Created during k6 test'
  }), {
    headers: { 'Content-Type': 'application/json' },
  });
  check(postResponse, { 'status was 201': (r) => r.status == 201 });
  
  sleep(1);
}
```

3. **Apache JMeter** — классический инструмент для нагрузочного тестирования

### Сценарии нагрузочного тестирования

1. **Постоянная нагрузка** — проверка работы системы при стабильной нагрузке
2. **Ступенчатое увеличение** — постепенное увеличение количества пользователей
3. **Стресс-тестирование** — кратковременное пиковое увеличение нагрузки
4. **Тест на выносливость** — длительное тестирование для выявления утечек ресурсов

### Метрики для мониторинга

- Latency (время отклика) — p50, p95, p99 перцентили
- Throughput (пропускная способность) — запросов в секунду
- Error rate (частота ошибок) — процент неудачных запросов
- Database connection usage (использование соединений базы данных)
- CPU, Memory, Disk I/O — использование системных ресурсов

## 3. Тестирование на гонки данных (Race Conditions)

### Pytest для тестирования конкурентности

```python
# test_race_conditions.py
import pytest
import asyncio
import httpx
from concurrent.futures import ThreadPoolExecutor

@pytest.mark.asyncio
async def test_concurrent_item_creation():
    """Тест на параллельное создание элементов с одинаковым уникальным ключом"""
    # Создаем 10 клиентов, которые одновременно создают запись с одинаковым sku
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # Подготовка одинаковых данных для всех запросов
        same_data = {
            "sku": "UNIQUE-123",
            "name": "Test Product",
            "price": 99.99
        }
        
        # Функция для выполнения одной попытки создания
        async def create_product():
            return await client.post("/products/", json=same_data)
        
        # Запускаем задачи параллельно
        tasks = [create_product() for _ in range(10)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Анализ результатов
        success_count = sum(1 for r in responses if not isinstance(r, Exception) and r.status_code == 201)
        conflict_count = sum(1 for r in responses if not isinstance(r, Exception) and r.status_code == 409)
        
        # Проверяем, что только один запрос успешен, остальные получают ошибку конфликта
        assert success_count == 1, f"Ожидался 1 успешный запрос, получено {success_count}"
        assert conflict_count == 9, f"Ожидалось 9 конфликтов, получено {conflict_count}"

@pytest.mark.asyncio
async def test_concurrent_updates():
    """Тест на параллельное обновление одной и той же записи"""
    # Создаем тестовый элемент
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        product_data = {"sku": "UPDATE-TEST", "name": "Original", "price": 100.0}
        create_resp = await client.post("/products/", json=product_data)
        assert create_resp.status_code == 201
        product_id = create_resp.json()["id"]
        
        # Функция для одновременного увеличения цены на 10
        async def increment_price():
            # Получаем текущую версию
            get_resp = await client.get(f"/products/{product_id}")
            current = get_resp.json()
            
            # Обновляем с указанием версии
            update_data = {
                "price": current["price"] + 10,
                "name": current["name"],
                "version": current["version"]
            }
            return await client.put(f"/products/{product_id}", json=update_data)
        
        # Запускаем 5 параллельных обновлений
        tasks = [increment_price() for _ in range(5)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Проверяем успешные и конфликтующие обновления
        success_count = sum(1 for r in responses if not isinstance(r, Exception) and r.status_code == 200)
        conflict_count = sum(1 for r in responses if not isinstance(r, Exception) and r.status_code == 409)
        
        # Проверяем, что сумма успешных и конфликтующих обновлений равна 5
        assert success_count + conflict_count == 5
        
        # Проверяем финальное значение
        final_resp = await client.get(f"/products/{product_id}")
        final_price = final_resp.json()["price"]
        
        # Из-за оптимистической блокировки, цена должна увеличиться только success_count раз
        assert final_price == 100.0 + (10 * success_count)
```

### Chaos Engineering для тестирования устойчивости

1. **Chaostoolkit** — фреймворк для тестирования устойчивости систем

```python
# experiment.py для chaostoolkit
from chaoslib.types import Experiment

# Эксперимент с внезапным отключением инстанса приложения
experiment = Experiment(
    title="Sudden instance termination during concurrent operations",
    description="Terminate an instance while handling concurrent database operations",
    tags=["database", "concurrency"],
    steady_state_hypothesis={
        "title": "System is stable",
        "probes": [
            {
                "name": "api-health",
                "type": "probe",
                "tolerance": True,
                "provider": {
                    "type": "http",
                    "url": "http://localhost:8000/health",
                    "timeout": 1
                }
            }
        ]
    },
    method=[
        {
            "name": "generate-load",
            "type": "action",
            "provider": {
                "type": "process",
                "path": "locust",
                "arguments": ["-f", "locustfile.py", "--headless", "-u", "20", "-r", "5", "--run-time", "60s"]
            },
            "background": True
        },
        {
            "name": "kill-app-instance",
            "type": "action",
            "provider": {
                "type": "process",
                "path": "docker",
                "arguments": ["kill", "myapp_app2_1"]
            },
            "pauses": {
                "after": 5
            }
        }
    ],
    rollbacks=[]
)
```

## 4. Тестирование идемпотентности

### Конфигурация Pytest для тестирования идемпотентности

```python
# test_idempotency.py
import pytest
import uuid
import httpx

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
        
        # Проверяем, что в базе данных только одна запись
        count_response = await client.get("/payments/count")
        assert count_response.json()["count"] == 1

@pytest.mark.asyncio
async def test_changing_data_with_same_idempotency_key():
    """Тест запросов с одинаковым ключом, но разными данными (должен вернуть первый результат)"""
    idempotency_key = str(uuid.uuid4())
    
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # Первый запрос
        first_data = {"amount": 50.00, "currency": "USD", "description": "First payment"}
        headers = {"Idempotency-Key": idempotency_key}
        first_response = await client.post("/payments/", json=first_data, headers=headers)
        assert first_response.status_code == 201
        first_result = first_response.json()
        
        # Второй запрос с измененными данными, но тем же ключом
        second_data = {"amount": 75.00, "currency": "EUR", "description": "Changed payment"}
        second_response = await client.post("/payments/", json=second_data, headers=headers)
        second_result = second_response.json()
        
        # Проверяем, что результат соответствует первому запросу, а не второму
        assert second_result["amount"] == 50.00
        assert second_result["currency"] == "USD"
        assert second_result.get("idempotency_applied") == True
```

## 5. Тестирование ACID-свойств транзакций

### Скрипты для проверки ACID-свойств

```python
# test_acid.py
import pytest
import asyncio
import httpx
import random
from concurrent.futures import ThreadPoolExecutor

@pytest.mark.asyncio
async def test_atomicity():
    """Тест атомарности - транзакция должна выполниться полностью или не выполниться совсем"""
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # Создаем пользователей для тестирования
        from_user = await client.post("/users/", json={"name": "From User", "balance": 100.0})
        to_user = await client.post("/users/", json={"name": "To User", "balance": 0.0})
        
        from_id = from_user.json()["id"]
        to_id = to_user.json()["id"]
        
        # Попытка перевода слишком большой суммы (должна вызвать ошибку)
        transfer_response = await client.post("/transfers/", json={
            "from_user_id": from_id,
            "to_user_id": to_id,
            "amount": 200.0  # больше чем доступно
        })
        
        assert transfer_response.status_code == 400  # Ожидаем ошибку
        
        # Проверяем, что балансы не изменились (атомарность)
        from_user_after = await client.get(f"/users/{from_id}")
        to_user_after = await client.get(f"/users/{to_id}")
        
        assert from_user_after.json()["balance"] == 100.0
        assert to_user_after.json()["balance"] == 0.0

@pytest.mark.asyncio
async def test_consistency():
    """Тест согласованности - сумма должна сохраняться при переводе"""
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # Создаем пользователей для тестирования
        from_user = await client.post("/users/", json={"name": "User A", "balance": 100.0})
        to_user = await client.post("/users/", json={"name": "User B", "balance": 50.0})
        
        total_before = 100.0 + 50.0
        
        from_id = from_user.json()["id"]
        to_id = to_user.json()["id"]
        
        # Выполняем перевод
        await client.post("/transfers/", json={
            "from_user_id": from_id,
            "to_user_id": to_id,
            "amount": 30.0
        })
        
        # Проверяем балансы после перевода
        from_user_after = await client.get(f"/users/{from_id}")
        to_user_after = await client.get(f"/users/{to_id}")
        
        from_balance = from_user_after.json()["balance"]
        to_balance = to_user_after.json()["balance"]
        total_after = from_balance + to_balance
        
        # Общая сумма должна остаться той же
        assert total_before == total_after

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

@pytest.mark.asyncio
async def test_durability():
    """Тест долговечности - данные должны сохраняться после перезапуска сервиса"""
    # Создаем уникальный идентификатор для теста
    test_reference = f"durability-test-{random.randint(1000, 9999)}"
    
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # Создаем тестовую запись
        create_response = await client.post("/durable-records/", json={
            "reference": test_reference,
            "value": "test data"
        })
        assert create_response.status_code == 201
        record_id = create_response.json()["id"]
    
    # Перезапускаем сервис через Docker
    import subprocess
    subprocess.run(["docker-compose", "restart", "app1", "app2", "app3"])
    
    # Ждем перезапуска
    await asyncio.sleep(10)
    
    # Проверяем, что данные сохранились
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        retrieve_response = await client.get(f"/durable-records/{record_id}")
        assert retrieve_response.status_code == 200
        assert retrieve_response.json()["reference"] == test_reference
        assert retrieve_response.json()["value"] == "test data"
```

## 6. Мониторинг и анализ производительности базы данных

### Инструменты мониторинга

1. **pgHero** — Простой интерфейс для мониторинга PostgreSQL

```bash
# установка через Docker
docker run -p 8080:8080 \
  -e DATABASE_URL=postgres://user:password@host:5432/dbname \
  ankane/pghero
```

2. **Prometheus + Grafana** — Комплексное решение для мониторинга и визуализации

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'fastapi'
    scrape_interval: 5s
    static_configs:
      - targets: ['app1:8000', 'app2:8000', 'app3:8000']
```

3. **pg_stat_statements** — Расширение PostgreSQL для анализа запросов

```sql
-- Включение модуля
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Запрос для нахождения самых медленных запросов
SELECT query, calls, total_time, mean_time, rows 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;
```

## 7. План тестирования конкурентности

### Подготовка

1. Создайте Docker Compose конфигурацию с несколькими инстансами приложения
2. Настройте общую базу данных и Redis для распределенных блокировок
3. Реализуйте тесты для каждого типа проверки (нагрузка, гонки, идемпотентность, ACID)

### Пошаговое тестирование

1. **Базовое функциональное тестирование**
   - Убедитесь, что все API работают корректно с одним инстансом

2. **Тесты на идемпотентность**
   - Запустите тесты, проверяющие обработку дублирующих запросов
   - Сымитируйте сетевые ошибки и повторные запросы

3. **Тесты на гонки данных**
   - Проверьте конкурентное создание/обновление одних и тех же ресурсов
   - Убедитесь, что механизмы блокировки работают правильно

4. **Нагрузочное тестирование**
   - Начните с низкой нагрузки и постепенно увеличивайте
   - Отслеживайте метрики базы данных во время тестов
   - Выявите максимальную пропускную способность системы

5. **Тестирование отказоустойчивости**
   - Имитируйте падение одного из инстансов во время нагрузки
   - Проверьте, что система продолжает работать корректно
   - Убедитесь, что происходит корректное освобождение ресурсов

6. **Тестирование ACID-свойств**
   - Выполняйте сложные транзакции при высокой конкурентности
   - Проверьте сохранение данных при перезапуске сервисов

### Автоматизация и CI/CD интеграция

```yaml
# Пример GitHub Actions workflow для автоматизации тестов
name: Concurrency Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Docker Compose
        run: docker-compose -f docker-compose.test.yml up -d
      
      - name: Wait for services to be ready
        run: sleep 30
      
      - name: Run functional tests
        run: pytest tests/functional/
      
      - name: Run concurrency tests
        run: pytest tests/concurrency/
      
      - name: Run idempotency tests
        run: pytest tests/idempotency/
      
      - name: Run load test
        run: k6 run tests/load/script.js
      
      - name: Export test results
        run: |
          mkdir -p test-results
          docker-compose logs > test-results/docker-logs.txt
          
      - name: Upload test results
        uses: actions/upload-artifact@v2
        with:
          name: test-results
          path: test-results/
```

## 8. Бюджетные и открытые решения для тестирования

### Нагрузочное тестирование
- **Locust** — бесплатный, с открытым исходным кодом
- **k6** — бесплатный для основного использования
- **Apache JMeter** — полностью бесплатный

### Тестирование гонок данных
- **Pytest** с asyncio — бесплатный
- **Apache JMeter** с Thread Groups — бесплатный

### Мониторинг
- **Prometheus + Grafana** — открытый исходный код
- **pgHero** — открытый исходный код
- **pg_stat_statements** — встроен в PostgreSQL

### Вспомогательные инструменты
- **pgbench** — встроенный инструмент PostgreSQL для бенчмаркинга
- **wrk** — легковесный инструмент для HTTP бенчмаркинга
- **hey** — простой инструмент для генерации нагрузки

## 9. Чеклист для проверки конкурентного доступа

- [ ] **Проверка пула соединений**
  - Установлены оптимальные значения pool_size и max_overflow
  - Настроен pool_timeout для предотвращения бесконечного ожидания
  - Включен pool_pre_ping для проверки соединений

- [ ] **Проверка блокировок**
  - Реализована оптимистическая или пессимистическая блокировка
  - Тесты показывают корректное поведение при конкурентном обновлении
  - Отсутствуют deadlocks при высокой нагрузке

- [ ] **Проверка идемпотентности**
  - API принимает и обрабатывает ключи идемпотентности
  - Повторные запросы с тем же ключом дают тот же результат
  - Обработка ошибок не нарушает идемпотентность

- [ ] **Проверка транзакций**
  - Транзакции соблюдают ACID-свойства
  - Уровни изоляции настроены оптимально
  - Длительные транзакции не блокируют систему

- [ ] **Производительность**
  - Система выдерживает ожидаемую нагрузку
  - Время отклика остается в пределах нормы при высокой конкурентности
  - Нет утечек ресурсов при длительной работе

## Заключение

Тестирование конкурентного доступа к базе данных — критически важный аспект разработки многоинстансных FastAPI приложений. Используя описанные в этом документе инструменты и методики, вы можете создавать надежные системы, устойчивые к проблемам конкурентности, и быть уверенными в их корректной работе даже при высоких нагрузках.

Главное помнить, что некоторые проблемы конкурентности могут проявляться только в редких случаях или при определенных условиях, поэтому важно проводить комплексное тестирование с различными сценариями и уровнями нагрузки. 