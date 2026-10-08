# 💻 pattern-development-ensi.md

**Категория:** [PATTERNS]  
**Используется:** разработчиками на платформе ENSI  
**Версия:** 1.0  
**Статус:** Production-ready  
**Платформа:** ENSI (PHP 8.1/Swoole, OpenAPI-first, микросервисы)

---

## 📋 Описание

**Явный паттерн разработки для ENSI** — как разработчик пишет PHP/Swoole код на платформе ENSI с учётом специфики:

- OpenAPI-first архитектуры
- Микросервисной организации
- Swoole асинхронности
- PostgreSQL + Kafka
- Контрактов между сервисами

Разработчик **ДОЛЖЕН ВСЕГДА** следовать этим 8 шагам, специфичным для ENSI. Это расширение `pattern-development-flow.md` с ENSI-деталями.

---

## 🎯 8 обязательных шагов

### 1️⃣ ПОНИМАНИЕ — Контракты и API

**Что делать:**
- Прочитать OpenAPI спеку сервиса (если есть изменения)
- Понять входящие контракты (какиеDTO приходят?)
- Понять исходящие контракты (какие DTO уходят?)
- Проверить Kafka topics если есть pub/sub
- Понять зависимости от других микросервисов

**Процесс ENSI:**
```
КОНТРАКТ: Добавить поле `discountApplied: bool` в OrderDto

1. Прочитать OpenAPI спеку (apps/orders/api/openapi.yaml):
   ✅ OrderDto уже имеет структуру
   ✅ Понял: нужно добавить boolean field

2. Проверить upstream сервисы (кто отправляет OrderDto?):
   ✅ baskets-сервис отправляет
   ✅ Нужно обновить Basket -> Order маппер

3. Проверить downstream сервисы (кто читает OrderDto?):
   ✅ integration-сервис читает через customers-api-web
   ✅ Нужно убедиться что клиент сгенерируется правильно

4. Проверить Kafka (есть ли события?):
   ✅ OrderStatusChanged event публикуется
   ✅ Нужно добавить поле в event payload

✅ ПОНИМАНИЕ ЗАВЕРШЕНО: 
   - Спека обновлена (или нужна)
   - Маппер обновлён
   - Клиенты буду регенерироваться
   - Event payload обновлён
```

**Если не понял:**
- Спросить в своём микросервисе → архитектор сервиса
- Для кросс-сервисных вопросов → спросить ensi-architect
- Не гадать про контракты!

---

### 2️⃣ ПЛАН — Файлы и порядок (ENSI структура)

**Что делать:**
- Какие files в своём сервисе трогаем?
- Какие files в других сервисах (если нужно)?
- Какой порядок: спека → код → клиенты?
- Есть ли миграции БД (если PostgreSQL)?

**Процесс ENSI:**
```
Сервис: platform/ensi/apps/orders/baskets

Файлы в этом сервисе:
  1. api/openapi.yaml (спека) ← ПЕРВОЕ
     └─ Добавить OrderDto.discountApplied

  2. src/Domain/Basket/BasketItem.php (домен)
     └─ Свойство должно быть в модели

  3. src/Application/Dto/OrderDto.php (DTO)
     └─ Поле discountApplied

  4. src/Infrastructure/Mapper/BasketToOrderMapper.php (маппер)
     └─ Маппить basket.appliedDiscount → dto.discountApplied

  5. tests/Application/BasketServiceTest.php (тесты)
     └─ Проверить маппинг

Файлы в других сервисах (зависимости):
  ✅ platform/ensi/packages/baskets-client-php/
     └─ РЕГЕНЕРИРУЕТСЯ АВТОМАТИЧЕСКИ (openapi-generator)

  ✅ platform/integration/www/
     └─ Использует baskets-client-php
     └─ Тесты на интеграцию

Миграции:
  ✅ platform/ensi/apps/orders/database/migrations/
     └─ Если нужно менять schema

Порядок:
  1. OpenAPI спека (ВСЕГДА первое)
  2. Domain model (если нужны новые поля)
  3. DTO и маппер
  4. Тесты
  5. Клиенты регенерируются автоматически в CI
  6. Другие сервисы обновляют свои версии клиентов
```

---

### 3️⃣ КОД — Написание (ensi-code-style)

**Что делать:**
- Следовать `ensi-code-style` скилу (PHP 8.1 features)
- Action классы для бизнес-логики
- Явные type hints везде
- Ранние returns, no deep nesting
- Комментарии только "ПОЧЕМУ", не "ЧТО"

**Процесс ENSI:**
```php
// ✅ ХОРОШО: следует ensi-code-style

// 1. явные type hints (PHP 8.1)
public function applyDiscount(
    BasketId $basketId,
    DiscountCode $code,
): void {
    // 2. ранний return на ошибку
    if (!$this->repository->exists($basketId)) {
        throw new BasketNotFoundException();
    }

    // 3. Action класс для бизнес-логики
    $action = new ApplyDiscountAction(
        basketId: $basketId,
        code: $code,
        discountService: $this->discountService,
    );
    
    $result = $action->execute();
    
    // 4. явное сохранение в БД
    $this->repository->save($result->basket);
    
    // 5. публикация события (Kafka)
    $this->dispatcher->dispatch($result->event);
}

// ❌ ПЛОХО:
public function applyDiscount($basketId, $code) {
    $basket = $this->repository->getBasket($basketId);
    if ($basket) {
        $discount = $this->discountService->calculate($code);
        if ($discount > 0) {
            $basket->discount = $discount;
            $this->repository->update($basket);
            // ... всё сложно вложено
        }
    }
}
```

**Правила ENSI:**
- Constructor promotion (PHP 8.0)
- No PHPDoc (типы — явные)
- Action классы > Service классы
- Repository pattern для Data Access
- Enum для констант (Order::Status::SHIPPED)
- Контрактно-driven: спека → DTO → код

---

### 4️⃣ OPENAPI & КЛИЕНТЫ — Регенерация

**Что делать:**
- Если менял HTTP endpoint → обнови openapi.yaml
- Если менял DTO → обнови components/schemas в openapi.yaml
- Все клиенты регенерируются автоматически в CI (openapi-generator)
- Проверить что версия клиента обновилась в других сервисах

**Процесс ENSI:**
```yaml
# platform/ensi/apps/orders/api/openapi.yaml

components:
  schemas:
    OrderDto:
      type: object
      required:
        - id
        - items
        - discountApplied  # ← НОВОЕ ПОЛЕ
      properties:
        id:
          type: string
          format: uuid
        items:
          type: array
          items:
            $ref: '#/components/schemas/OrderItemDto'
        discountApplied:  # ← НОВОЕ ПОЛЕ
          type: boolean
          description: "Применена ли скидка на заказ"
```

После коммита:
1. CI запускает openapi-generator
2. Генерирует `platform/ensi/packages/baskets-client-php/src/Model/OrderDto.php`
3. Версия клиента обновляется (patch версия)
4. Другие сервисы берут новую версию через composer update

```bash
# Проверить что клиент обновлён:
cd platform/ensi/packages/baskets-client-php
grep -A 5 "public bool \$discountApplied" src/Model/OrderDto.php
# Должен быть property с type bool
```

---

### 5️⃣ ТЕСТЫ — ENSI-специфика

**Что писать:**
- Unit tests для Action классов
- Integration tests для Service → DAO → DB
- Database tests для migrations (если трогал schema)
- Kafka tests (если публикуешь события)

**Процесс ENSI:**
```php
// 1. Unit test для Action класса
class ApplyDiscountActionTest extends TestCase
{
    // Используем фабрики из tests/Factories
    private BasketFactory $basketFactory;
    private DiscountServiceMock $discountService;
    
    public function setUp(): void
    {
        $this->basketFactory = new BasketFactory();
        $this->discountService = new DiscountServiceMock();
    }
    
    public function testApplyDiscount_ValidCode_UpdatesBasket(): void
    {
        // Arrange
        $basket = $this->basketFactory->create();
        $code = DiscountCode::fromString('SUMMER20');
        
        // Act
        $action = new ApplyDiscountAction(
            basketId: $basket->id,
            code: $code,
            discountService: $this->discountService,
        );
        $result = $action->execute();
        
        // Assert
        $this->assertTrue($result->basket->discountApplied);
        $this->assertTrue($result->event instanceof DiscountAppliedEvent);
    }
}

// 2. Integration test (Action + DAO + DB)
class ApplyDiscountIntegrationTest extends TestDatabaseCase
{
    public function testApplyDiscount_PersistsToDatabase(): void
    {
        // Arrange
        $basket = $this->basketFactory->create();
        $code = DiscountCode::fromString('SUMMER20');
        $repository = new BasketRepository($this->db);
        
        // Act
        $action = new ApplyDiscountAction(
            basketId: $basket->id,
            code: $code,
            discountService: $this->discountService,
        );
        $result = $action->execute();
        $repository->save($result->basket);
        
        // Assert
        $reloaded = $repository->getById($basket->id);
        $this->assertTrue($reloaded->discountApplied);
    }
}

// 3. Kafka test (если публикуешь)
class DiscountAppliedEventPublishTest extends TestCase
{
    public function testDiscountApplied_PublishesToKafka(): void
    {
        $kafka = new KafkaMock();
        $event = new DiscountAppliedEvent(
            basketId: BasketId::fromString(/* ... */),
            appliedAt: new DateTimeImmutable(),
        );
        
        $dispatcher = new EventDispatcher($kafka);
        $dispatcher->dispatch($event);
        
        $this->assertTrue($kafka->wasPublished('orders.discount_applied', $event));
    }
}
```

**Структура тестов в ENSI:**
```
platform/ensi/apps/orders/
├── tests/
│   ├── Factories/          (фабрики для тестов)
│   ├── Unit/               (unit tests, no DB)
│   ├── Integration/        (Action + service + DB)
│   ├── Database/           (только migrations + schema)
│   └── Kafka/              (publisher/subscriber тесты)
```

**Запуск тестов:**
```bash
cd platform/ensi/apps/orders

# Все тесты
composer test

# Только unit
composer test tests/Unit

# Только integration
composer test tests/Integration

# С coverage
composer test:coverage
# Target: >80% coverage
```

---

### 6️⃣ SECURITY — ENSI-специфичные уязвимости

**Что проверять:**
- SQL Injection → используй параметризованные запросы (queryBuilder или ORM)
- XSS → все пользовательские данные проходят через DTO (type-safe)
- Secrets → нет hardcoded DB password, API keys
- CORS → настроена ли для внешних клиентов?
- Логирование → не логируем sensitive данные (PII)
- Kafka message validation → контракт совпадает?

**Процесс ENSI:**
```php
// ❌ ПЛОХО: SQL injection risk
$query = "SELECT * FROM baskets WHERE user_id = $userId";
$result = $db->query($query);

// ✅ ХОРОШО: параметризованный запрос
$result = $this->db->query(
    'SELECT * FROM baskets WHERE user_id = ?',
    [$userId]
);

// Или через query builder
$result = Basket::where('user_id', $userId)->get();

// ✅ ХОРОШО: type-safe DTO (no XSS через type system)
public function createOrder(CreateOrderDto $dto): OrderId
{
    // $dto->itemIds уже INTS (не строки, не executable code)
    // $dto->address уже STRING (не влезет в SQL/HTML)
    return $this->orderService->create($dto);
}

// ❌ ПЛОХО: secrets в коде
const DB_PASSWORD = 'pass123';
const API_KEY = 'sk_live_abc123def456';

// ✅ ХОРОШО: из env
$dbPassword = env('DB_PASSWORD');
$apiKey = env('API_KEY');

// ✅ ХОРОШО: не логируем PII
logger()->info('Order created', [
    'orderId' => $order->id,
    'itemCount' => count($order->items),
    // ❌ ПЛОХО: 'customerEmail' => $order->customer->email,
    // ✅ ХОРОШО: 'customerId' => $order->customerId->value,
]);

// ✅ ХОРОШО: Kafka message валидация
$event = DiscountAppliedEvent::fromArray($message);
// fromArray() проверяет что все required поля есть и правильного типа
$this->dispatcher->dispatch($event);
```

**Чеклист безопасности:**
- ✅ Параметризованные запросы везде
- ✅ Type-safe DTO на входе (никаких raw $_GET/$_POST)
- ✅ Secrets не в коде (только env vars)
- ✅ No PII в логах (только ID и non-sensitive данные)
- ✅ Kafka контракты валидированы (fromArray with validation)
- ✅ CORS конфиг правильный (не `*` для prod)
- ✅ No SQL errors на экран (только логировать)

---

### 7️⃣ ИНТЕГРАЦИЯ — Cross-service контракты

**Что делать:**
- Если меняешь output DTO → обновляют ли его upstream сервисы?
- Если вызываешь другой сервис → есть ли fallback на ошибку?
- Kafka контракты → sync между сервисами через schema registry?
- Версионирование → backward-compatibility?

**Процесс ENSI:**
```php
// Сценарий: Добавил поле discountApplied в OrderDto

// 1. UPSTREAM: baskets-сервис отправляет OrderDto
// файл: platform/ensi/apps/orders/src/Domain/Order/OrderDto.php
public class OrderDto {
    public BasketId $id;
    public array $items;
    public bool $discountApplied;  // ← НОВОЕ
}

// 2. DOWNSTREAM: integration-сервис читает через клиент
// файл: platform/integration/www/routes/checkout.php
$ordersClient = new OrdersApiClient();
$order = $ordersClient->getOrder($orderId);

// Старые версии integration:
// ✅ работают (клиент генерируется с новым полем)
// ✅ если не читают discountApplied → просто игнорируют

// 3. KAFKA контракт: Если публикуешь OrderCreated event
// Старые subscribers:
// ✅ не видят discountApplied (есть required validation?)
// ⚠️ если discountApplied required → старые versions падают!
// ✅ решение: discountApplied nullable или с default

// ✅ ХОРОШО: новое поле nullable (backward-compatible)
class OrderCreatedEvent {
    public OrderId $orderId;
    public array $items;
    public ?bool $discountApplied = null;  // nullable
}

// Или через версионирование Kafka topic
// orders.order_created.v2 — для новых subscribers
// orders.order_created.v1 — для старых (без discountApplied)
```

**Интеграционные тесты:**
```php
// Test: новое поле не ломает старые сервисы
class BackwardCompatibilityTest extends TestCase
{
    public function testNewOrderDtoField_IsNullableForOldSubscribers(): void
    {
        // Симулируем старого subscriber который не знает про discountApplied
        $eventJson = json_encode([
            'orderId' => '123',
            'items' => [/* ... */],
            // НЕ отправляем discountApplied
        ]);
        
        // Новый OrderCreatedEvent должен работать
        $event = OrderCreatedEvent::fromJson($eventJson);
        
        $this->assertNull($event->discountApplied);
        $this->assertNotNull($event->orderId);  // существенные поля есть
    }
}
```

---

### 8️⃣ КОММИТ И MR — ENSI process

**Что делать:**
- Коммит сообщение (что изменилось и почему)
- Тесты должны пройти (>80% coverage)
- MR description (для кого это, какие риски)
- Запросить ревью у архитектора сервиса (если major change)

**Процесс ENSI:**
```bash
# 1. Коммит: фокус на ЧТО и ПОЧЕМУ
git add platform/ensi/apps/orders/api/openapi.yaml
git add platform/ensi/apps/orders/src/Domain/Basket/BasketItem.php
git add platform/ensi/apps/orders/src/Application/Dto/OrderDto.php
git add platform/ensi/apps/orders/tests/

git commit -m "feat(baskets): add discountApplied field to OrderDto

Adds tracking of whether discount was applied to order.
- New field: OrderDto.discountApplied (boolean)
- Updated OpenAPI schema
- Added to BasketToOrderMapper
- Backward-compatible: nullable for old Kafka subscribers
- Tests: +3 integration tests for discount application flow

This allows Integration service to track which orders had
discounts applied, needed for analytics pipeline.

Related: OPSOMN002-100"

# 2. Запушить branch
git push origin feat/order-discount-tracking

# 3. Создать MR
# Title: feat(baskets): add discountApplied field to OrderDto
# Description:

# ## What
# - Tracking whether discount was applied to order
# - New field: OrderDto.discountApplied (boolean)

# ## Why
# Analytics pipeline needs to know which orders had discounts
# to calculate correct customer LTV and discount ROI

# ## Testing
# - 3 new integration tests
# - Manual test on stage: POST /checkout with discount code
# - Coverage: 85% (was 82%)

# ## Breaking Changes
# - NONE (field nullable, backward-compatible with Kafka)

# ## Checklist
# - [ ] OpenAPI спека обновлена
# - [ ] Клиенты будут регенерированы в CI
# - [ ] Tests покрывают новую логику (>80%)
# - [ ] Security: нет secrets, no SQL injection, no XSS
# - [ ] CLAUDE.md обновлён (если нужно архитектурные изменения)
# - [ ] Stage протестирован (если можно)

# Assign: @ensi-architect (если сложное)
# Request review: @platform-lead
```

**Правила MR:**
- ✅ Только один коммит на MR (или логически связанные)
- ✅ Title следует conventional commits: `feat()`, `fix()`, `refactor()`
- ✅ Description структурирована: What, Why, Testing, Breaking changes
- ✅ Ссылка на задачу (OPSOMN002-xxx)
- ✅ Если touch openapi.yaml → clients будут регенерированы в CI
- ✅ Если touch migrations → DBA должен знать (comment)

---

## 🔒 Полный чеклист разработки на ENSI

```markdown
## Перед тем как писать код

- [ ] Прочитал spec/requirement (ЧТО?)
- [ ] Определил сервисы (ГДЕ?)
- [ ] Проверил OpenAPI spikes если нужны (КОНТРАКТЫ?)
- [ ] Спросил о Kafka topics если нужны (СОБЫТИЯ?)

## Написание кода

- [ ] Следую ensi-code-style (PHP 8.1, типы, Action классы)
- [ ] Обновил OpenAPI spec (если новый endpoint/DTO)
- [ ] Написал тесты (unit + integration, >80% coverage)
- [ ] Проверил SQL injection (параметризованные запросы)
- [ ] Не логирую PII (только ID, не email/phone)
- [ ] Нет secrets в коде (всё из env)

## Перед MR

- [ ] Все тесты проходят (`composer test`)
- [ ] Coverage >80% (`composer test:coverage`)
- [ ] Code style ок (`composer lint`)
- [ ] Static analysis проходит (if есть)
- [ ] Коммит сообщение ясное (feat/fix/refactor)
- [ ] Нет закомментированного кода

## MR description

- [ ] Объяснил ЧТО меняется
- [ ] Объяснил ПОЧЕМУ нужно (связь с requirement)
- [ ] Указал Testing (какие тесты)
- [ ] Указал Breaking changes (есть ли?)
- [ ] Линкнул на задачу
- [ ] Указал reviewer'а

## После merge

- [ ] Проверил что stage деплоится
- [ ] Если OpenAPI → проверил что клиенты обновились
- [ ] Если Kafka → проверил что messages в staging Kafka есть
```

---

## 📊 Комментарии в коде ENSI

Используй style из `.claude/rules/code-comments.md`:

```php
// ✅ ХОРОШО: Почему так, а не очевидным способом
// Вычисляем скидку ПОСЛЕ применения tax (не раньше)
// потому что tax считается от base price, а скидка от tax
$basePrice = $item->price * $quantity;
$tax = $basePrice * TAX_RATE;
$discount = calculateDiscount($basePrice); // ← на base, не на tax
$total = $basePrice + $tax - $discount;

// ✅ ХОРОШО: Реальная опасность
// Откат бонусов один раз на заказ: повторный вызов вернёт их дважды
// если запрос retry-ится, должна быть идемпотентность
public function applyBonus(OrderId $orderId, BonusAmount $amount): void
{
    // проверяем что не применили уже
    if ($this->bonusRepository->exists($orderId)) {
        return;  // идемпотентно
    }
    // ...
}

// ✅ ХОРОШО: Внешний контракт, которого нет в коде
// CDEK API возвращает null для carrier_name если неизвестный перевозчик
// поэтому используем fallback на id (связь через tracking_id)
// см. https://docs.cdek.ru/tracking-api.html#_get_courier_info
$carrierName = $response->carrier_name ?? ("CDEK-{$response->carrier_id}");
```

---

## 🎯 Примеры реальных сценариев

### Сценарий 1: Добавить новый endpoint для витрины

```
1. ПОНИМАНИЕ
   - Что: GET /api/v1/products/{id}/reviews?sort=rating
   - Где: catalog-сервис, public API
   - Как: unit тесты + integration тесты
   
2. ПЛАН
   - api/openapi.yaml: добавить /products/{id}/reviews endpoint
   - src/Application/Service/ReviewService.php: sort logic
   - src/Infrastructure/Persistence/ReviewRepository.php: WHERE clause
   - tests/Integration/ReviewEndpointTest.php
   
3. КОД
   - Следуем ensi-code-style
   - Action класс для бизнеса (ReviewFetcher)
   - Repository для персистенции
   
4. SECURITY
   - No SQL injection: используем queryBuilder
   - No XSS: DTO с type hints
   - CORS: проверить что конфиг позволяет витрине
   
5. ТЕСТЫ
   - Unit: ReviewFetcher.sort() правильно сортирует
   - Integration: GET /api/v1/products/123/reviews?sort=rating возвращает правильный порядок
   - Database: есть индекс на (product_id, rating)?
   
6. OPENAPI
   - Обновили спеку → клиент витрины сгенерируется автоматически
   
7. ИНТЕГРАЦИЯ
   - Витрина тянет через gj-ng-front/libs/data-access/
   - Старые версии витрины тоже работают (field не required)
   
8. MR
   - Title: feat(catalog): add reviews sorting endpoint
   - Description: Why (какой usecase), Testing, Breaking changes
```

### Сценарий 2: Опубликовать новый Kafka event

```
1. ПОНИМАНИЕ
   - Что: OrderShippedEvent (заказ отправлен до покупателя)
   - Где: orders-сервис публикует в Kafka
   - Где: integration-сервис слушает и обновляет витрину
   
2. ПЛАН
   - src/Domain/Event/OrderShippedEvent.php: контракт события
   - src/Infrastructure/EventDispatcher: отправка в Kafka
   - api/openapi.yaml: не нужно (это событие, не HTTP endpoint)
   - tests/Integration/OrderShippedEventTest.php
   
3. КОД
   - Enum для типов событий
   - Strongly typed event объект
   - Serializer для Kafka (обычно JSON)
   
4. SECURITY
   - Не включаем PII в event (customer email, phone)
   - Только: OrderId, timestamp, new status
   
5. ТЕСТЫ
   - Kafka mock: проверяем что event публикуется
   - Integration: подписчик получает и обрабатывает
   
6. ИНТЕГРАЦИЯ
   - integration-сервис подписан на этот event?
   - Если нет topics для этого → создать в staging Kafka
   - Версионирование: если поле required → может быть breaking
   
7. ДОКУМЕНТАЦИЯ
   - Обновить docs/events-catalog.md (если есть)
```

---

## ✨ Резюме: 8 Шагов ENSI разработки

| Шаг | Фокус | Артефакты |
|-----|-------|-----------|
| 1️⃣ ПОНИМАНИЕ | Контракты и API | OpenAPI спека, DTO, Kafka topics |
| 2️⃣ ПЛАН | Файлы и порядок | List файлов, порядок имплементации |
| 3️⃣ КОД | ensi-code-style | PHP 8.1, типы, Action классы |
| 4️⃣ OPENAPI | Спека + клиенты | openapi.yaml, автоген-клиенты в CI |
| 5️⃣ ТЕСТЫ | Unit + Integration | >80% coverage, Kafka tests |
| 6️⃣ SECURITY | Уязвимости | SQL injection, XSS, secrets, PII |
| 7️⃣ ИНТЕГРАЦИЯ | Cross-service | Backward-compat, Kafka версионирование |
| 8️⃣ MR | Коммит + review | Понятный title, Testing, Breaking changes |

---

## 📚 Связанные скилы и документация

- `ensi-code-style/SKILL.md` — детальный код-стайл
- `ensi-api-design/SKILL.md` — OpenAPI дизайн
- `ensi-elc-operations/SKILL.md` — локальная разработка (elc)
- `ensi-kafka/SKILL.md` — Kafka pub/sub patterns
- `ensi-models/SKILL.md` — domain models
- `ensi-tests/SKILL.md` — тестирование ENSI
- `CLAUDE.md` — архитектура платформы
- `.claude/rules/code-comments.md` — комментарии в коде

---

## 🎯 ВСЕГДА помни

1. **OpenAPI-first** — спека ПЕРЕД кодом, не после
2. **Action классы** — бизнес-логика в Action, не в Service
3. **Type-safe** — тип-система защищает от ошибок (no XSS через типы)
4. **Контракты** — между сервисами через DTO и Kafka (не в коде)
5. **Тесты >80%** — coverage мерится для каждого коммита
6. **Нет secrets** — все из env vars, никогда не в коде
7. **Backward-compatible** — новые поля nullable, новые events версионированы
8. **Один коммит** — одна фича, одна логическая единица

---

**Версия:** 1.0  
**Дата:** 2026-10-06  
**Статус:** ✅ Production-ready  
**Платформа:** ENSI (PHP 8.1/Swoole)  
**Автор:** Claude Haiku 4.5 + Antonov Aleksandr (Outsource)

**ВСЕГДА СЛЕДОВАТЬ ЭТИМ 8 ШАГАМ!**
