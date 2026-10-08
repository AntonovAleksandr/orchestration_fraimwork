---
name: pattern-development-integration
version: 1.0.0
layer: generic
platform: Integration
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---

# 💻 pattern-development-integration.md

**Категория:** [PATTERNS] — Integration Platform  
**Платформа:** Integration Service (PHP/Lumen)  
**Используется:** разработчиками Integration  
**Версия:** 1.0  
**Статус:** Production-ready  
**Дата:** 2026-10-06

---

## 📋 Описание

**Явный паттерн разработки для Integration** — как разработчик пишет PHP/Lumen код в Integration Service по постановке.

Интеграционный сервис — это **критическая BFF** между фронтенд (сайт/мобила) и backend-платформы (ENSI, OMS, OTS). Поэтому разработка требует повышенной **тщательности по контрактам API, безопасности, и кроссплатформной совместимости**.

Разработчик **ДОЛЖЕН ВСЕГДА** следовать этим **Integration-специфичным 7 шагам**. Основа — shared `pattern-development-flow`, дополнение — Integration реалии.

---

## 🎯 7 шагов для Integration

### 1️⃣ ПОНИМАНИЕ (Understanding) — Integration Edition

**Что делать:**
- Прочитать постановку: ЧТО (API, cron-task, библиотека?), ГДЕ (HTTP route, scheduler, shared lib?), КАК (sync/async, RPC/event-driven?), РИСКИ
- Понять контракт: API схема (OpenAPI или контракт с ENSI/OMS/OTS), версии
- Понять направление: фронт → BFF → backend или backend → BFF → фронт?
- Понять роль доставки данных: синхронный HTTP, асинхронный Kafka/RabbitMQ, outbox pattern?
- Понять миграцию: нужны ли миграции базы (особенно outbox для msq-client)?

**Integration-специфичные вопросы:**
```
1. API или cron task? → route в www/ или job в www/app/Jobs/?
2. Ходит ли это в ENSI/OMS/OTS? → какой контракт/версия API?
3. Фронт это видит? → нужен ли контракт с сайтом/мобилой?
4. Асинхронно? → нужны ли Kafka/RabbitMQ/outbox обработчики?
5. Могут ли быть race-условия? → лок в БД? idempotency key?
6. Нужна ли логирование для трассировки? → logger-lib с контекстом?
7. [NB] Есть ли [BLOCKER] вопросы перед кодом?
```

**Примеры:**

**Сценарий A: новый route для checkout**
```
ЧТО? "Добавить POST /checkout/confirm для финализации заказа"
ГДЕ? "Integration route + handler, вызывает OMS order.confirm()"
КАК? "Синхронный HTTP к OMS, фронт ждёт response"
РИСКИ? Нет [BLOCKER], но надо обработать таймауты OMS

✅ ПОНИМАНИЕ: это route, идёт в OMS, sync, нужны retry + timeout
```

**Сценарий B: новый cron-task для синка остатков**
```
ЧТО? "Каждый час синить остатки из 1С в витрину"
ГДЕ? "cron-task в integration-cron контейнере"
КАК? "Асинхронно ночью, может упасть — нужна retry-логика"
РИСКИ? [NB] "Какой приоритет при конфликте — локальный БД или 1С?"

✅ ПОНИМАНИЕ: это cron, external sync, async, нужна idempotency + retry
```

---

### 2️⃣ ПЛАН (Planning) — Integration Edition

**Что делать:**
- Какие файлы в Integration трогаем? (route, handler, job, middleware, library?)
- Какие файлы в других платформах трогаем? (ENSI-клиент, OMS-клиент, контракт с сайтом?)
- Порядок имплементации (сначала контракты, потом вызывающий код, потом обработчики ошибок)
- Зависимости (между компонентами Internal, между сервисами)
- Есть ли [NB] вопросы, которые не решены в постановке?

**Integration-типичные файлы:**
```
platform/integration/www/
├── app/Http/Routes/          # Lumen route definitions
│   ├── delivery-update.php    # пример: синк статусов доставки
│   ├── checkout.php           # пример: чекаут-роуты
│   └── customer.php           # пример: профиль покупателя
├── app/Http/Controllers/      # Lumen HTTP controllers
│   ├── CheckoutController.php
│   ├── DeliveryController.php
│   └── CustomerController.php
├── app/Http/Middleware/       # Middleware (auth, logging, rate-limit)
│   ├── AuthenticateCustomer.php
│   ├── TraceIdMiddleware.php  # X-Trace-Id пробрасывание
│   └── ValidateCustomer.php
├── app/Jobs/                  # Async jobs (если используем queue)
│   ├── SyncDeliveryStatusJob.php
│   └── SyncInventoryJob.php
├── app/Listeners/             # Event listeners (Kafka, RabbitMQ)
│   ├── OrderConfirmedListener.php
│   └── PaymentStatusListener.php
├── app/Models/                # DB models (Eloquent)
│   ├── Order.php
│   ├── OrderLine.php
│   └── Outbox.php             # outbox pattern для async
├── database/migrations/       # DB миграции
│   ├── CreateOrdersTable.php
│   └── CreateOutboxTable.php
└── tests/
    ├── Feature/               # integration tests
    │   ├── CheckoutTest.php
    │   └── DeliveryTest.php
    └── Unit/                  # unit tests
        ├── CheckoutRequestValidatorTest.php
        └── PaymentMapperTest.php
```

**Процесс планирования:**
```
Задача: "Добавить API /checkout/confirm для финализации заказа"

Файлы (в порядке):
1. platform/integration/www/app/Http/Controllers/CheckoutController.php (создать новый метод)
2. platform/integration/www/app/Http/Requests/ConfirmCheckoutRequest.php (валидация)
3. platform/integration/www/routes/api.php (добавить route)
4. platform/integration/www/app/Services/CheckoutService.php (бизнес-логика)
5. Клиент OMS: использовать generated OMS-client (или создать если нет)
6. Тесты: Feature/CheckoutTest.php, Unit/CheckoutServiceTest.php
7. Миграции: если нужно сохранять state в БД Integration

Порядок реализации:
Step 1: Написать ConfirmCheckoutRequest (валидация контракта)
Step 2: Написать CheckoutService (вызов OMS order.confirm)
Step 3: Написать CheckoutController (оркестрировать Service + обработать ошибки)
Step 4: Добавить route
Step 5: Написать тесты
Step 6: Проверить логирование (trace-id, context)

Зависимости:
- OMS API версия? (check current ENSI/OMS API)
- Фронт контракт? (какой JSON schema ожидаем от сайта/мобилы?)
- Миграции БД? (нужны ли таблицы для state?)
- Библиотеки: используем logger-lib, msq-client, health-lib?

[NB] вопросы:
- Может ли заказ быть подтверждён дважды? → idempotency key
- Что если OMS таймаут? → retry logic, exponential backoff
- Нужен ли webhook-callback от OMS? → listener + async processing
```

---

### 3️⃣ КОД (Implementation) — Integration Edition

**Что делать:**
- Писать PHP/Lumen код по плану
- Следовать shared-code-style (PHP имена, phpstan, комментарии)
- Использовать Lumen conventions (routes, controllers, services, models, requests)
- Комментарии только "ПОЧЕМУ", не "ЧТО"
- Использовать типизацию (strict_types=1, type hints на аргументы и return)

**Integration-специфичные соглашения:**

#### Структура Controllers
```php
<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Http\Requests\ConfirmCheckoutRequest;
use App\Services\CheckoutService;
use Illuminate\Http\JsonResponse;
use Psr\Log\LoggerInterface;

class CheckoutController
{
    public function __construct(
        private CheckoutService $checkoutService,
        private LoggerInterface $logger
    ) {
    }

    public function confirm(ConfirmCheckoutRequest $request): JsonResponse
    {
        $customerId = auth('api')->id() ?? null;
        
        // Логируем с контекстом (X-Trace-Id пробрасывается автоматически)
        $this->logger->info('checkout.confirm', [
            'customerId' => $customerId,
            'basketId' => $request->input('basketId'),
            'deliveryType' => $request->input('deliveryType'),
        ]);

        try {
            $order = $this->checkoutService->confirm(
                customerId: $customerId,
                basketId: $request->input('basketId'),
                deliveryType: $request->input('deliveryType'),
                // idempotency key для безопасного retry
                idempotencyKey: $request->header('Idempotency-Key')
            );

            return response()->json([
                'success' => true,
                'orderId' => $order['id'],
                'status' => $order['status'],
            ], 201);
        } catch (\Throwable $e) {
            $this->logger->error('checkout.confirm.failed', [
                'error' => $e->getMessage(),
                'code' => $e->getCode(),
            ]);
            
            // Маппировать ошибки OMS на HTTP codes
            return response()->json([
                'success' => false,
                'error' => $this->mapError($e),
            ], $this->statusCode($e));
        }
    }

    private function mapError(\Throwable $e): string
    {
        // Контракт: какие ошибки от OMS и как мы их маппируем фронту
        return match (get_class($e)) {
            'OmsOrderAlreadyConfirmedException' => 'order_already_confirmed',
            'OmsInvalidBasketException' => 'invalid_basket',
            'OmsTimeoutException' => 'backend_timeout',
            default => 'internal_error',
        };
    }

    private function statusCode(\Throwable $e): int
    {
        return match (get_class($e)) {
            'OmsOrderAlreadyConfirmedException' => 409, // Conflict
            'OmsInvalidBasketException' => 400, // Bad Request
            'OmsTimeoutException' => 503, // Service Unavailable
            default => 500,
        };
    }
}
```

#### Структура Services (бизнес-логика)
```php
<?php

declare(strict_types=1);

namespace App\Services;

use App\Repositories\OutboxRepository;
use OMS\Client\OrderClient;
use ENSI\Client\BasketClient;
use Psr\Log\LoggerInterface;

class CheckoutService
{
    public function __construct(
        private OrderClient $omsOrderClient,
        private BasketClient $ensiBasketClient,
        private OutboxRepository $outbox,
        private LoggerInterface $logger
    ) {
    }

    /**
     * Подтвердить заказ в OMS
     * 
     * Идемпотентна через idempotency_key: повторный вызов с теми же 
     * параметрами вернёт результат из БД, не пересоздаст заказ.
     */
    public function confirm(
        ?int $customerId,
        string $basketId,
        string $deliveryType,
        ?string $idempotencyKey = null
    ): array {
        // Проверить idempotency: если уже обработано, вернуть кешированный результат
        if ($idempotencyKey) {
            $cached = $this->outbox->findByIdempotencyKey($idempotencyKey);
            if ($cached) {
                $this->logger->info('checkout.confirm.idempotent_hit', [
                    'idempotencyKey' => $idempotencyKey,
                    'orderId' => $cached['order_id'],
                ]);
                return $cached['result'];
            }
        }

        // Получить basket данные из ENSI
        $basket = $this->ensiBasketClient->getCurrent($customerId, $basketId);
        if (!$basket) {
            throw new \InvalidArgumentException('Basket not found');
        }

        // Создать заказ в OMS
        $order = $this->omsOrderClient->create([
            'customerId' => $customerId,
            'basketId' => $basketId,
            'items' => $basket['items'],
            'deliveryType' => $deliveryType,
            'shippingAddress' => $basket['shippingAddress'],
            'totalPrice' => $basket['totalPrice'],
        ]);

        $result = [
            'id' => $order['orderId'],
            'status' => $order['status'],
            'createdAt' => $order['createdAt'],
        ];

        // Сохранить в outbox для идемпотентности и async processing
        if ($idempotencyKey) {
            $this->outbox->create([
                'idempotency_key' => $idempotencyKey,
                'order_id' => $order['orderId'],
                'result' => json_encode($result),
                'status' => 'confirmed',
            ]);
        }

        // Отправить событие (async): корзина тратится → витрина/рекомендации обновить
        $this->outbox->create([
            'topic' => 'order.confirmed',
            'event_type' => 'OrderConfirmed',
            'payload' => json_encode([
                'orderId' => $order['orderId'],
                'customerId' => $customerId,
                'totalPrice' => $basket['totalPrice'],
            ]),
            'status' => 'pending',
        ]);

        return $result;
    }
}
```

#### Структура Requests (валидация)
```php
<?php

declare(strict_types=1);

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;

class ConfirmCheckoutRequest extends FormRequest
{
    public function authorize(): bool
    {
        // Авторизована ли корзина этому пользователю?
        return auth('api')->check();
    }

    public function rules(): array
    {
        return [
            'basketId' => ['required', 'string', 'uuid'],
            'deliveryType' => ['required', 'string', 'in:courier,pickup,express'],
            'shippingAddress' => ['required', 'array'],
            'shippingAddress.street' => ['required', 'string', 'max:255'],
            'shippingAddress.city' => ['required', 'string', 'max:100'],
            'shippingAddress.postalCode' => ['required', 'string', 'regex:/^\d{6}$/'],
        ];
    }

    public function messages(): array
    {
        return [
            'basketId.uuid' => 'Basket ID должен быть UUID',
            'deliveryType.in' => 'Delivery type должен быть: courier, pickup или express',
            'shippingAddress.postalCode.regex' => 'Postal code должен быть 6 цифр',
        ];
    }
}
```

#### Структура Tests (Feature)
```php
<?php

declare(strict_types=1);

namespace Tests\Feature;

use Illuminate\Foundation\Testing\DatabaseTransactions;
use Tests\TestCase;

class CheckoutTest extends TestCase
{
    use DatabaseTransactions;

    /**
     * @test
     * Успешное подтверждение заказа
     */
    public function confirmOrderSuccess(): void
    {
        // Given: авторизованный пользователь с basket
        $customerId = 123;
        $this->actingAs($this->createCustomer($customerId));

        $basket = $this->createBasket($customerId, 'b-uuid-1', [
            'items' => [
                ['sku' => 'SKU-001', 'qty' => 2, 'price' => 100.0],
            ],
            'totalPrice' => 200.0,
        ]);

        // When: POST /checkout/confirm
        $response = $this->postJson('/api/checkout/confirm', [
            'basketId' => $basket['id'],
            'deliveryType' => 'courier',
            'shippingAddress' => [
                'street' => 'ul. Pushkina 42',
                'city' => 'Moscow',
                'postalCode' => '123456',
            ],
        ], [
            'Idempotency-Key' => 'idem-key-123',
        ]);

        // Then: заказ создан в OMS, возвращён в ответе
        $response->assertStatus(201);
        $response->assertJsonStructure([
            'success',
            'orderId',
            'status',
        ]);
        $this->assertTrue($response->json('success'));
        
        // Проверить что outbox записался для идемпотентности
        $this->assertDatabaseHas('outbox', [
            'idempotency_key' => 'idem-key-123',
            'status' => 'confirmed',
        ]);
    }

    /**
     * @test
     * Idempotency: повторный вызов с тем же ключом вернёт кеш
     */
    public function confirmOrderIdempotent(): void
    {
        $customerId = 456;
        $this->actingAs($this->createCustomer($customerId));
        $basket = $this->createBasket($customerId);
        $idempotencyKey = 'idem-key-456';

        // First call
        $response1 = $this->postJson('/api/checkout/confirm', [...], [
            'Idempotency-Key' => $idempotencyKey,
        ]);
        $orderId1 = $response1->json('orderId');

        // Second call с тем же ключом
        $response2 = $this->postJson('/api/checkout/confirm', [...], [
            'Idempotency-Key' => $idempotencyKey,
        ]);
        $orderId2 = $response2->json('orderId');

        // Должны вернуться одинаковые ID
        $this->assertEquals($orderId1, $orderId2);
    }

    /**
     * @test
     * OMS таймаут: вернуть 503 Service Unavailable
     */
    public function confirmOrderOmsTimeout(): void
    {
        $this->mockOmsClient('timeout');
        
        $response = $this->postJson('/api/checkout/confirm', [...]);

        $response->assertStatus(503);
        $response->assertJsonPath('error', 'backend_timeout');
    }
}
```

---

### 4️⃣ SECURITY (Security Checks) — Integration Edition

**Что проверять (специфично для Integration):**

| Риск | Проверка | Пример |
|------|----------|---------|
| **SQL Injection** | Всегда параметризованные запросы, Eloquent ORM | `Model::where('id', $id)->first()` ✅, `DB::raw()` только с параметрами |
| **XSS** | Escaping JSON responses, не использовать `{!! !!}` в blade | `json_encode($data)` ✅ |
| **CSRF/CORS** | Middleware проверяет origin, CSRF токен для POST | `middleware('auth:api', 'cors')` в routes |
| **Authentication** | Проверить что auth-guard используется на route | `auth('api')->id()` обязателен для protected routes |
| **Authorization** | Юзер может видеть только свои данные | Проверить что customerId от auth, не из request |
| **Secrets in logs** | Не логируем passwords, tokens, credit cards | `->except(['password', 'token', 'cardNumber'])` |
| **Secrets in code** | Не hardcodить API keys, URLs | `.env` файлы и `config/services.php` |
| **Timing attacks** | Avoid timing-sensitive comparisons | `hash_equals()` для tokens, не `==` |
| **Rate limiting** | Middleware rate-limit на sensitive endpoints | `middleware('throttle:60,1')` для login |
| **PII in exceptions** | Не expose системные пути, ошибки БД в ответе | `config('app.debug')` должен быть false в prod |
| **Idempotency** | Async операции должны быть идемпотентны | outbox pattern, idempotency_key в БД |
| **TLS/HTTPS** | Все коммуникации с ENSI/OMS через HTTPS | Force HTTPS в nginx config |

**Процесс проверки:**

```php
// ❌ ПЛОХО:
$order = DB::select("SELECT * FROM orders WHERE id = " . $id);
// SQL Injection!

// ✅ ХОРОШО:
$order = Order::find($id);
// Или:
$order = DB::table('orders')->where('id', $id)->first();

---

// ❌ ПЛОХО:
echo $userInput;  // XSS!
// Или в blade:
{!! $userData !!}

// ✅ ХОРОШО:
json_encode($userInput);  // Escaping
// Или в blade:
{{ $userData }}  // Autoescape

---

// ❌ ПЛОХО:
$this->logger->info('User login', [
    'email' => $email,
    'password' => $password,  // ЛОВИ УТЕКИ!
    'creditCard' => $card,     // ЛОВИ УТЕКИ!
]);

// ✅ ХОРОШО:
$this->logger->info('User login', [
    'email' => $email,
    // password не логируем вообще
]);

---

// ❌ ПЛОХО:
if ($token == $receivedToken) {  // Timing attack!
    // auth OK
}

// ✅ ХОРОШО:
if (hash_equals($token, $receivedToken)) {
    // auth OK
}

---

// ❌ ПЛОХО:
$response = response()->json($data)->header('Access-Control-Allow-Origin', '*');

// ✅ ХОРОШО:
// Использовать middleware CORS который проверяет whitelist origins
```

**Integration-специфичные секьюрити вопросы:**

1. **Фронт → Integration контракт** — валидируем ALL входящие поля (FormRequest rules)
2. **Integration → ENSI/OMS контракт** — надёжный retry + timeout, не expose ошибок backend в фронт
3. **Идемпотентность** — outbox pattern для async, idempotency_key для safe retry
4. **Логирование** — X-Trace-Id для трассировки через системы, но не логируем PII/secrets
5. **Rate limiting** — защита от abuse (DDoS) на login, checkout endpoints
6. **Circuit breaker** — если OMS/ENSI падает, graceful degradation (не крашим весь сервис)

---

### 5️⃣ ТЕСТЫ (Testing) — Integration Edition

**Что писать:**

- **Unit tests** — для сервисов (бизнес-логика, маппинг, валидация)
- **Feature tests** — для routes (HTTP контракт, ошибки, status codes)
- **Edge-cases** — race conditions, timeouts, idempotency, duplicate requests

**Структура тестов:**

```
tests/
├── Feature/
│   ├── CheckoutTest.php       # HTTP routes
│   ├── DeliveryTest.php        # async delivery updates
│   └── CustomerProfileTest.php # customer data flows
├── Unit/
│   ├── Services/
│   │   ├── CheckoutServiceTest.php       # business logic
│   │   ├── DeliveryMapperTest.php        # OMS ↔ ENSI conversion
│   │   └── PaymentStatusMapperTest.php   # payment states
│   ├── Mappers/
│   │   └── OrderMapperTest.php
│   └── Validators/
│       └── CheckoutRequestValidatorTest.php
└── Integration/
    ├── OmsClientIntegrationTest.php  # real OMS calls (stage env)
    └── EnsiClientIntegrationTest.php # real ENSI calls (stage env)
```

**Примеры:**

```php
<?php

// Unit test — маппинг OMS → frontend
namespace Tests\Unit\Services;

use App\Services\OrderMapper;
use PHPUnit\Framework\TestCase;

class OrderMapperTest extends TestCase
{
    private OrderMapper $mapper;

    protected function setUp(): void
    {
        parent::setUp();
        $this->mapper = new OrderMapper();
    }

    /**
     * @test
     * Маппинг OMS order statuses в UI-friendly names
     */
    public function mapOmsStatusToPresentationStatus(): void
    {
        // Given: OMS order с внутренним статусом
        $omsOrder = [
            'orderId' => '123',
            'status' => 'ORDER_CONFIRMED',  // OMS internal
            'createdAt' => '2026-10-06T10:00:00Z',
        ];

        // When
        $uiOrder = $this->mapper->toPresentation($omsOrder);

        // Then: status маппирован на UI-friendly
        $this->assertEquals('Confirmed', $uiOrder['status']);
        $this->assertEquals('2026-10-06T10:00:00Z', $uiOrder['createdAt']);
    }

    /**
     * @test
     * Неизвестный статус OMS → fallback значение
     */
    public function unknownOmsStatusUsesFallback(): void
    {
        $omsOrder = [
            'status' => 'UNKNOWN_STATUS_FROM_FUTURE',
        ];

        $uiOrder = $this->mapper->toPresentation($omsOrder);

        // Fallback: "Processing"
        $this->assertEquals('Processing', $uiOrder['status']);
    }
}

---

// Feature test — HTTP route
namespace Tests\Feature;

use Illuminate\Foundation\Testing\DatabaseTransactions;
use Tests\TestCase;

class DeliveryUpdateTest extends TestCase
{
    use DatabaseTransactions;

    /**
     * @test
     * Webhook из OTS: статус доставки обновлён → sync в БД
     */
    public function otsWebhookUpdateDeliveryStatus(): void
    {
        // Given: заказ в БД
        $order = $this->createOrder('ORD-123', 'pending');

        // When: OTS шлёт webhook о смене статуса
        $response = $this->postJson('/webhooks/delivery-update', [
            'orderId' => 'ORD-123',
            'status' => 'on_the_way',
            'trackingUrl' => 'https://cdek.ru/track?abc=123',
            'estimatedDelivery' => '2026-10-10T18:00:00Z',
        ], [
            'Authorization' => 'Bearer ' . $this->otsWebhookSecret(),
            'X-OTS-Signature' => hash_hmac('sha256', ...), // signature check
        ]);

        // Then
        $response->assertStatus(200);
        
        // Проверить что статус обновлён в БД
        $this->assertDatabaseHas('orders', [
            'order_id' => 'ORD-123',
            'delivery_status' => 'on_the_way',
        ]);

        // Проверить что событие отправлено для фронта (push, websocket, или poll)
        $this->assertDatabaseHas('outbox', [
            'topic' => 'order.delivery_status_changed',
            'payload' => json_encode([
                'orderId' => 'ORD-123',
                'status' => 'on_the_way',
            ]),
        ]);
    }

    /**
     * @test
     * Идемпотентность: двойной webhook с тем же orderId
     */
    public function otsWebhookIdempotent(): void
    {
        // First call
        $response1 = $this->postJson('/webhooks/delivery-update', [
            'orderId' => 'ORD-456',
            'status' => 'delivered',
        ], [...headers]);

        // Second call (сеть задержала и отправила дважды)
        $response2 = $this->postJson('/webhooks/delivery-update', [
            'orderId' => 'ORD-456',
            'status' => 'delivered',
        ], [...headers]);

        // Оба должны быть 200, но обновление один раз
        $response1->assertStatus(200);
        $response2->assertStatus(200);

        $orders = DB::table('orders')
            ->where('order_id', 'ORD-456')
            ->where('delivery_status', 'delivered')
            ->count();
        
        // Только одна запись обновлена, не дублировалась
        $this->assertEquals(1, $orders);
    }

    /**
     * @test
     * Невалидная signature на webhook → 401 Unauthorized
     */
    public function otsWebhookInvalidSignature(): void
    {
        $response = $this->postJson('/webhooks/delivery-update', [
            'orderId' => 'ORD-789',
            'status' => 'delivered',
        ], [
            'Authorization' => 'Bearer ' . $this->otsWebhookSecret(),
            'X-OTS-Signature' => 'WRONG_SIGNATURE',
        ]);

        $response->assertStatus(401);
        
        // Проверить что обновление НЕ произошло
        $this->assertDatabaseMissing('orders', [
            'order_id' => 'ORD-789',
            'delivery_status' => 'delivered',
        ]);
    }
}

---

// Cron task test — async job
namespace Tests\Feature;

use App\Jobs\SyncInventoryJob;
use Illuminate\Foundation\Testing\DatabaseTransactions;
use Tests\TestCase;

class SyncInventoryJobTest extends TestCase
{
    use DatabaseTransactions;

    /**
     * @test
     * Cron job: синк остатков из 1C в витрину
     */
    public function syncInventoryFromOneC(): void
    {
        // Given: 1C данные (mock)
        $this->mock1CApi([
            'SKU-001' => ['qty' => 42, 'warehouseId' => 'W1'],
            'SKU-002' => ['qty' => 0, 'warehouseId' => 'W2'],
        ]);

        // When: запустили job
        $job = new SyncInventoryJob();
        $job->handle();

        // Then: остатки обновлены в БД
        $this->assertDatabaseHas('inventory', [
            'sku' => 'SKU-001',
            'quantity' => 42,
        ]);

        $this->assertDatabaseHas('inventory', [
            'sku' => 'SKU-002',
            'quantity' => 0,
        ]);
    }

    /**
     * @test
     * 1C API error: job не упал, залогировал ошибку
     */
    public function syncInventoryHandles1CError(): void
    {
        $this->mock1CApi('timeout');  // Имитируем timeout

        $job = new SyncInventoryJob();
        
        // Job должен не упасть (catch ошибку)
        $job->handle();

        // Проверить что залогирована ошибка
        $this->assertLogged('error', 'inventory.sync.1c_error');
    }
}
```

**Coverage требование: >80%**

```bash
# Прогон тестов с coverage
php artisan test --coverage --coverage-min=80

# Результат должен быть >= 80%
# Если меньше — дописать тесты
```

---

### 6️⃣ КОММИТ (Commit) — Integration Edition

**Что делать:**
- Правильная ветка: `feature/OPSOMN002-XXX`, `fix/BP-INT-YYY`, `refactor/...`
- Сообщение: `feat(checkout): добавить /checkout/confirm с idempotency`
- Co-Authored-By добавить
- Все тесты зелёные (`npm run test` в CI/CD)
- PHPStan clean (`php artisan phpstan:analyse`)
- Код reviewed (если требуется)

**Процесс:**

```bash
# 1. Проверка перед коммитом
git status                          # только нужные файлы
php artisan test                    # все тесты зелёные
php artisan phpstan:analyse         # статанализ clean
php artisan lint:all                # форматирование clean
composer validate                   # composer.json valid

# 2. Staging
git add app/ routes/ tests/ database/migrations/

# 3. Коммит с полным описанием
git commit -m "feat(checkout): добавить POST /checkout/confirm для финализации заказа

Добавлен новый endpoint для подтверждения заказа в OMS:

- CheckoutController::confirm() — HTTP handler
- CheckoutService — бизнес-логика (вызов OMS, outbox sync)
- ConfirmCheckoutRequest — валидация фронт-контракта
- Outbox pattern для идемпотентности (idempotency_key)
- Retry + exponential backoff для OMS таймаутов
- Unit + Feature тесты (coverage 85%)
- Logger integration (X-Trace-Id пробрасывание)

Риски обработаны:
- Двойной запрос: идемпотентность через outbox ✅
- OMS таймаут: retry logic + graceful timeout ✅
- Фронт контракт: валидация в ConfirmCheckoutRequest ✅

AC выполнены:
- POST /api/checkout/confirm вернёт 201 + orderId ✅
- Повторный запрос с Idempotency-Key вернёт кеш ✅
- OMS ошибки маппированы в HTTP codes (400/409/503) ✅
- Логирование включено (X-Trace-Id) ✅
- Coverage >= 80% ✅

Тесты: Feature/CheckoutTest (3 кейса), Unit/CheckoutServiceTest (5 кейсов)

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"

# 4. Пуш
git push origin feature/OPSOMN002-XXX
```

---

### 7️⃣ MR (Merge Request) — Integration Edition

**Что делать:**
- Target branch: `develop` (или `main` если release)
- Заголовок: краткий, компактный
- Описание: summary, changes, test plan, AC
- Проверить CI (tests, lint, coverage)
- Запросить review у Integration-инженера + domain-expert (если cross-platform)

**Процесс:**

```bash
gh pr create \
  --title "feat(checkout): добавить /checkout/confirm" \
  --base develop \
  --body "$(cat <<'EOF'
## Summary
Новый endpoint POST /api/checkout/confirm для финализации заказа покупателя.
Включает идемпотентность (outbox pattern), retry logic для OMS, и полный набор тестов.

## Changes
- **CheckoutController::confirm()** — HTTP handler, маршрут /checkout/confirm
- **CheckoutService** — бизнес-логика (вызов OMS order.confirm, outbox sync)
- **ConfirmCheckoutRequest** — валидация фронт-контракта (basketId, deliveryType, address)
- **Outbox pattern** — идемпотентность через idempotency_key, async event dispatch
- **Retry logic** — exponential backoff для таймаутов OMS (max 3 retry, 1s-5s interval)
- **Logging** — X-Trace-Id пробрасывание, контекст в обоих направлениях
- **Tests** — Feature/CheckoutTest (идемпотентность, ошибки OMS), Unit/CheckoutServiceTest
- **DB migration** — outbox таблица для идемпотентности

## Test plan
- [ ] Unit тесты запущены локально: `php artisan test` (8 тестов passed)
- [ ] Integration тесты на mock OMS: feature/checkout test (3 тестов)
- [ ] Coverage: `php artisan test --coverage` = 85%
- [ ] Manual: POST /api/checkout/confirm с валидными данными → 201 + orderId
- [ ] Manual: повторный запрос с Idempotency-Key → 201 + same orderId (из outbox)
- [ ] Manual: OMS таймаут → 503 Service Unavailable
- [ ] Manual: невалидная basket → 400 Bad Request
- [ ] PHPStan clean: `php artisan phpstan:analyse` ✅

## AC выполнены
- ✅ POST /api/checkout/confirm (auth required)
- ✅ Возвращает 201 Created + {orderId, status, createdAt}
- ✅ Идемпотентна через Idempotency-Key
- ✅ OMS контракт соблюдён
- ✅ Фронт контракт соблюдён (basketId, deliveryType, address обязательны)
- ✅ Логирование включено (X-Trace-Id)
- ✅ Coverage >= 80%
- ✅ Тесты все зелёные в CI

## Risks & Mitigations
- **Race condition**: два одновременных запроса → выигрывает тот что быстрее. Миtigаtion: outbox pattern + DB unique constraint на idempotency_key
- **OMS timeout**: 30s таймаут → retry до 3 раз с backoff. Миtigаtion: graceful 503, логирование для отладки
- **Circuit breaker**: если OMS падает 10 раз подряд → временный 503 без retry. Миtigаtion: не упадёт весь сервис

Closes OPSOMN002-XXX
Relates to BP-INT-YYY
EOF
)"
```

Результат: MR URL будет выведен, передать ревьюерам.

---

## 🔗 Integration-специфичные ссылки

| Тема | Файл/Путь |
|------|-----------|
| **Stack anatomy** | `.claude/skills/integration-stack-anatomy/SKILL.md` |
| **PHP conventions** | `.claude/skills/integration-php-conventions/SKILL.md` |
| **Deployment** | `.claude/skills/integration-deployment/SKILL.md` |
| **Lumen docs** | https://lumen.laravel.com/docs |
| **PHPUnit** | https://phpunit.de/manual/current/en/index.html |
| **OMS API** | `platform/starfish24/core/Order/README.md` |
| **ENSI API** | `platform/ensi/docs/api/` |
| **OTS API** | `platform/gloriaots/Docs/` |

---

## ✨ Важные правила для Integration

### Правило 1: Контракты первыми
- Фронт контракт (что шлёт сайт/мобила) → в ConfirmCheckoutRequest
- Backend контракт (что ответит OMS/ENSI) → в Services, с маппингом на UI
- Не менять контракты без согласования с заказчиком

### Правило 2: Идемпотентность всегда
- Async операции (cron, events) → outbox pattern обязателен
- HTTP POST из фронта → idempotency_key в header
- Никогда не создавать дубли заказов/платежей

### Правило 3: Логирование контекста
- X-Trace-Id пробрасывается автоматически (middleware)
- Логируем customerId (если авторизован), basketId, но НЕ пароли/tokens
- Все ошибки backend логируем (OMS/ENSI timeout и т.п.)

### Правило 4: Retry + timeout
- Таймаут OMS/ENSI: 30s max
- Retry: до 3 раз, exponential backoff (1s, 2s, 5s)
- Fallback: graceful 503 Service Unavailable
- НЕ expose системные ошибки в JSON response

### Правило 5: Тесты обязательны
- Unit: для сервисов (маппинг, валидация)
- Feature: для routes (HTTP контракт, ошибки)
- Coverage: >= 80%

### Правило 6: Security обязателен
- Всегда параметризованные SQL запросы (Eloquent ORM)
- Escaping output (json_encode, не {!! !!})
- Не логируем PII/secrets
- Rate limiting на auth endpoints

---

## 🎓 Полный пример: Нов route для синка остатков

```
ШАГ 1: ПОНИМАНИЕ
✅ Новый route: POST /inventory-update (webhook из 1С)
✅ Принимает: {sku, qty, warehouseId}
✅ Идёт в БД: обновить inventory таблицу
✅ Async: event для vitrine (обновить кеш)
✅ Нет [BLOCKER]

ШАГ 2: ПЛАН
✅ Файлы: InventoryController, InventoryService, InventoryUpdateRequest, 
         Tests/Feature/InventoryTest, migration create_inventory_table
✅ Порядок: request → service → controller → route → tests
✅ Зависимости: none (only DB)

ШАГ 3: КОД
✅ InventoryUpdateRequest (валидация sku, qty, warehouse)
✅ InventoryService::update() (БД + outbox event)
✅ InventoryController::update() (обработка request, error handling)
✅ Route: POST /webhooks/inventory-update (middleware: signature verify)
✅ Комментарии: только почему (идемпотентность, retry)

ШАГ 4: SECURITY
✅ Webhook signature verify (X-OneC-Signature)
✅ Валидация input (ConfirmInventoryUpdateRequest)
✅ SQL параметризован (Eloquent)
✅ Не логируем sensitive data
✅ Rate limit если нужно

ШАГ 5: ТЕСТЫ
✅ Feature: webhook success, invalid signature, duplicate (idempotent)
✅ Unit: маппинг 1С SKU → internal ID, qty validation
✅ Edge-case: отрицательное qty, неизвестный SKU
✅ Coverage: 82%

ШАГ 6: КОММИТ
✅ Ветка: feature/BP-INT-100
✅ Message: feat(inventory): добавить webhook /webhooks/inventory-update
✅ Co-Authored-By добавлен
✅ Все тесты зелёные

ШАГ 7: MR
✅ Target: develop
✅ Описание полное (summary, changes, AC, test plan)
✅ CI зелёный
✅ Готово для ревью

→ ГОТОВО! MR передан ревьюерам
```

---

**Версия:** 1.0  
**Дата:** 2026-10-06  
**Статус:** Production-ready  
**Автор:** Claude Haiku 4.5 + Antonov Aleksandr (Outsource)  
**Основа:** pattern-development-flow.md (shared 7 шагов)
