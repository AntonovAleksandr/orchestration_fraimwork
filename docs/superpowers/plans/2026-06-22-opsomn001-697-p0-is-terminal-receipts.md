# OPSOMN001-697 P0 IS Terminal Receipts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop Integration Service from exporting terminal 1C Ecom XML with an invalid prepaid receipt when the required terminal receipt is missing or present under a different payment.

**Architecture:** Keep the fix local to Integration Service order export mapping. Before creating terminal 1C XML, choose only the receipt type valid for the terminal scenario; if the current OMS payload is stale, refresh the full order from OMS once or with a short bounded retry; if the required receipt is still unavailable, fail before sending invalid XML to 1C.

**Tech Stack:** PHP 7.4/Lumen, existing Integration Service mutators, `OmsClient`, `Connector`, PHPUnit.

## Global Constraints

- Do not change OMS/Camunda in this P0 plan.
- Do not change 1C XML shape beyond `receipt_info` and `payment_return` semantics.
- Do not fallback from terminal `COMPLETED` to `fullPrepayment`.
- Do not fallback from terminal refund `CANCELLED`/`LOST` to charged `fullPrepayment`.
- Keep current behavior for non-terminal exports unless a test proves it is part of this defect.
- All new behavior must be covered by unit tests before implementation.

---

## Evidence Summary

Jira comment `220234` says MR `!840` only fixed one case: when several receipts already exist in a payment, pick the correct one by `accountingType`.

The remaining P0 IS gaps are:

- `COMPLETED` attempt can arrive before `fullPayment`; current mapper can export `fullPrepayment` together with delivered terminal markers.
- `CANCELLED` attempt can arrive before returned payment / `credit`; current mapper can fall back to charged prepayment.
- `payment_return` must prefer `orderPaymentReturnDateTime`, then the returned/credit payment date, then status history.

Known out-of-scope but related:

- `2000467801` retry with final receipt still got 500 from 1C, likely because of paid delivery `order_entry`.
- `2000467809` retry after credit still got 500, likely because of inconsistent post-refund payload state.
- `orderExportWithFeedbackActivity` currently records export errors as variables and completes the external task; it does not perform technical retry.

---

## Files

- Modify: `platform/integration/integration/www/app/Service/UserApi/Mutators/V1/Order/AbstractOrderExport1CMutator.php`
- Modify: `platform/integration/integration/www/app/Service/Consts/Enums/Payment/Oms/ReceiptAccountingTypeEnum.php`
- Create or modify: `platform/integration/integration/www/app/Service/ExceptionRepository/Order/System/TerminalReceiptNotReady.php`
- Modify: `platform/integration/integration/www/tests/Unit/UserApi/Mutators/V1/Order/OrderExport1CReceiptTest.php`
- Optionally modify: `platform/integration/integration/www/app/Service/UserApi/Services/V1/Order/OrderService.php` if refresh must happen outside the mutator

---

### Task 1: Lock Down Receipt Type Selection

**Files:**
- Modify: `platform/integration/integration/www/app/Service/Consts/Enums/Payment/Oms/ReceiptAccountingTypeEnum.php`
- Modify: `platform/integration/integration/www/app/Service/UserApi/Mutators/V1/Order/AbstractOrderExport1CMutator.php`
- Test: `platform/integration/integration/www/tests/Unit/UserApi/Mutators/V1/Order/OrderExport1CReceiptTest.php`

**Interfaces:**
- Produces: `ReceiptAccountingTypeEnum::CREDIT = 'credit'`
- Produces: strict receipt lookup helper accepting ordered accounting types

- [ ] **Step 1: Add failing tests for strict receipt lookup**

Add tests proving:

```php
public function testCompletedDoesNotFallbackToFullPrepaymentWhenFullPaymentMissing(): void
{
    $mutable = $this->makeCompletedPrepaidOrder([
        $this->makeReceipt('fullPrepayment', '2450252070', '2026-06-22T11:40:24Z'),
    ]);

    $this->assertNull($this->callMutateReceiptInfo($mutable));
}

public function testCancelledDoesNotFallbackToChargedPrepaymentWhenReturnedPaymentMissing(): void
{
    $mutable = $this->makeCancelledPrepaidOrder([
        $this->makeChargedPaymentWithReceipt('fullPrepayment', '1651485341', '2026-06-22T12:11:59Z'),
    ]);

    $this->assertNull($this->callMutateReceiptInfo($mutable));
}
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform/integration/integration/www
./vendor/bin/phpunit tests/Unit/UserApi/Mutators/V1/Order/OrderExport1CReceiptTest.php
```

Expected: new tests fail because current code still allows fallback to `fullPrepayment`.

- [ ] **Step 3: Implement strict accounting type selection**

Implement these rules:

- `COMPLETED`: search only `fullPayment`.
- `CANCELLED`/`LOST` with returned payment: search only `credit`.
- `CANCELLED`/`LOST` without returned payment but refund expected: return `null` for `receipt_info`, with warning trace.
- Non-terminal behavior remains unchanged.

- [ ] **Step 4: Run focused tests**

Run:

```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform/integration/integration/www
./vendor/bin/phpunit tests/Unit/UserApi/Mutators/V1/Order/OrderExport1CReceiptTest.php
```

Expected: strict negative tests pass.

---

### Task 2: Define Refund Expected Detection

**Files:**
- Modify: `platform/integration/integration/www/app/Service/UserApi/Mutators/V1/Order/AbstractOrderExport1CMutator.php`
- Test: `platform/integration/integration/www/tests/Unit/UserApi/Mutators/V1/Order/OrderExport1CReceiptTest.php`

**Interfaces:**
- Produces: private helper `isRefundExpected(array $mutable): bool`

- [ ] **Step 1: Add tests for refund expected states**

Add cases:

```php
public function testRefundExpectedWhenOrderHasPaymentReturnDateTime(): void
{
    $mutable = $this->makeCancelledPrepaidOrder([]);
    $mutable['customAttributes'][] = [
        'name' => 'orderPaymentReturnDateTime',
        'value' => '2026-06-22T12:34:49+00:00',
    ];

    $this->assertTrue($this->callIsRefundExpected($mutable));
}

public function testRefundExpectedWhenAnyItemPaymentReturnedIsTrue(): void
{
    $mutable = $this->makeCancelledPrepaidOrder([]);
    $mutable['items'][0]['payment']['returned'] = true;

    $this->assertTrue($this->callIsRefundExpected($mutable));
}
```

- [ ] **Step 2: Run tests and verify they fail**

Run the focused unit test file.

- [ ] **Step 3: Implement `isRefundExpected()` conservatively**

Return `true` when any of these are true:

- custom attribute `orderPaymentReturnDateTime` exists and is not empty;
- any item has `payment.returned === true`;
- a returned/credit payment exists but has no usable credit receipt yet.

Avoid using `order.isPaid=false` alone as the only signal, because post-refund payloads can be contradictory.

- [ ] **Step 4: Run focused tests**

Expected: refund detection tests pass.

---

### Task 3: Correct `payment_return` Date Chain

**Files:**
- Modify: `platform/integration/integration/www/app/Service/UserApi/Mutators/V1/Order/AbstractOrderExport1CMutator.php`
- Test: `platform/integration/integration/www/tests/Unit/UserApi/Mutators/V1/Order/OrderExport1CReceiptTest.php`

**Interfaces:**
- Produces: `payment_return` date precedence:
  1. `orderPaymentReturnDateTime`
  2. returned/credit payment or credit receipt date
  3. status history fallback

- [ ] **Step 1: Add failing tests for date precedence**

Add tests:

```php
public function testPaymentReturnUsesOrderPaymentReturnDateTimeBeforeCancelledHistory(): void
{
    $mutable = $this->makeCancelledOrderWithReturnedCreditPayment();
    $mutable['customAttributes'][] = [
        'name' => 'orderPaymentReturnDateTime',
        'value' => '2026-06-21T14:34:08+00:00',
    ];

    $this->assertSame('2026-06-21T17:34:08', $this->callMutatePaymentReturn($mutable));
}

public function testPaymentReturnFallsBackToCreditReceiptDate(): void
{
    $mutable = $this->makeCancelledOrderWithReturnedCreditPayment('2026-06-21T14:34:22Z');

    $this->assertSame('2026-06-21T17:34:22', $this->callMutatePaymentReturn($mutable));
}
```

- [ ] **Step 2: Run tests and verify missing fallback fails**

Run focused PHPUnit file.

- [ ] **Step 3: Implement date chain**

Keep existing `orderPaymentReturnDateTime` behavior, then add fallback from returned payment / credit receipt, then use status history as last resort.

- [ ] **Step 4: Run focused tests**

Expected: `payment_return` date tests pass.

---

### Task 4: Refresh Stale OMS Payload Before Terminal Export

**Files:**
- Modify: `platform/integration/integration/www/app/Service/UserApi/Services/V1/Order/OrderService.php`
- Or modify: `platform/integration/integration/www/app/Service/UserApi/Mutators/V1/Order/AbstractOrderExport1CMutator.php`
- Test: `platform/integration/integration/www/tests/Unit/UserApi/Mutators/V1/Order/OrderExport1CReceiptTest.php`

**Interfaces:**
- Consumes: `OmsClient::getOrderFull(string $orderId)`
- Produces: bounded refresh flow used only when terminal receipt is missing

- [ ] **Step 1: Choose refresh boundary**

Preferred boundary: `OrderService::export()` before calling `Ecom1CClient::createOrder($mutated)`.

Reason: refresh changes the entire `data` payload and should happen before mutation and XML creation, not inside a field mutator with hidden network calls.

- [ ] **Step 2: Add a test seam for refresh**

If existing unit tests cannot mock `OmsClient` cleanly, extract a small protected method:

```php
protected function refreshOrderFull(string $orderId): array
{
    return Connector::sendAndParse(OmsClient::getOrderFull($orderId));
}
```

Override it in a test subclass.

- [ ] **Step 3: Add failing test for stale COMPLETED payload**

Create a test where first payload has only `fullPrepayment`, refresh payload has `fullPayment`, and final mutation uses `fullPayment`.

- [ ] **Step 4: Add failing test for stale CANCELLED payload**

Create a test where first payload has only charged `fullPrepayment`, refresh payload has returned `credit`, and final mutation uses `credit`.

- [ ] **Step 5: Implement bounded refresh**

Only refresh when all are true:

- destination is `1c-ecom`;
- order status is `COMPLETED`, `CANCELLED`, or `LOST`;
- order is online prepaid / refund scenario;
- required terminal receipt is missing in current payload.

Use a bounded policy, for example:

- attempt current payload;
- refresh once immediately;
- optionally sleep 1 second and refresh once more if the team accepts a synchronous wait.

Do not make unbounded polling.

- [ ] **Step 6: Run focused tests**

Expected: stale payload tests pass and existing success cases still pass.

---

### Task 5: Fail Before Sending Invalid Terminal XML

**Files:**
- Create or modify: `platform/integration/integration/www/app/Service/ExceptionRepository/Order/System/TerminalReceiptNotReady.php`
- Modify: `platform/integration/integration/www/app/Service/UserApi/Services/V1/Order/OrderService.php`
- Test: `platform/integration/integration/www/tests/Unit/UserApi/Mutators/V1/Order/OrderExport1CReceiptTest.php`

**Interfaces:**
- Produces: explicit exception when terminal receipt remains unavailable after refresh

- [ ] **Step 1: Add failing test for no send when terminal receipt missing**

Test that `Ecom1CClient::createOrder()` is not called when `COMPLETED` still has no `fullPayment` after refresh.

- [ ] **Step 2: Add exception class**

Create:

```php
<?php

namespace App\Service\ExceptionRepository\Order\System;

use App\Service\GloriaJeansSupport\Contracts\Enums\ErrorCodeEnum;
use App\Service\IntegrationFoundation\Exceptions\ApiException;
use Awg\Logger\Contracts\Severity;
use Awg\Logger\Contracts\Type;

class TerminalReceiptNotReady extends ApiException
{
    protected const DEFAULT_EXCEPTION_REASON = 'Terminal receipt is not ready for order export';
    protected const DEFAULT_EXCEPTION_TYPE = Type::RUNTIME;
    protected const DEFAULT_EXCEPTION_SEVERITY = Severity::WARNING;
    protected const DEFAULT_EXCEPTION_ERROR_CODE = ErrorCodeEnum::ORDER;
    protected const DEFAULT_EXCEPTION_HTTP_CODE = 500;
}
```

- [ ] **Step 3: Throw only after refresh is exhausted**

Throw `TerminalReceiptNotReady` with context:

- order id;
- client order id;
- status id;
- destination;
- expected receipt type;
- present receipt accounting types;
- whether refresh was attempted.

- [ ] **Step 4: Run focused tests**

Expected: invalid XML is never sent; explicit error is raised.

---

### Task 6: Verification

**Files:**
- No new files beyond implementation tasks

- [ ] **Step 1: Run focused PHPUnit**

```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform/integration/integration/www
./vendor/bin/phpunit tests/Unit/UserApi/Mutators/V1/Order/OrderExport1CReceiptTest.php
```

Expected: all receipt export tests pass.

- [ ] **Step 2: Run existing wider unit suite if local bootstrap allows**

```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform/integration/integration/www
./vendor/bin/phpunit tests/Unit
```

Expected: unit suite passes. If local-only bootstrap prevents full run, do not commit local bootstrap workarounds; document the blocker.

- [ ] **Step 3: Docker verification**

Run the focused suite inside the project PHP runtime container if available.

Expected: PHP version and dependencies match deployment target.

- [ ] **Step 4: Manual log validation on stage**

After deploy to stage, validate:

- `2000467781` attempt with missing `fullPayment` no longer sends prepayment for `COMPLETED`;
- `2000467801` attempt 1 no longer sends prepayment for `COMPLETED`;
- `2000467809` attempt before credit no longer sends charged prepayment for `CANCELLED`;
- `2000467800` still sends credit when credit is already in payload.

---

## Not Covered By This P0 Plan

These items are required to close the broader Jira analysis, but they are not IS P0 receipt selection:

- 1C 500 on `COMPLETED` with paid delivery line in `order_entry`.
- 1C 500 on post-refund retry with `isPaid=false` and non-zero `payableCost`.
- Real retry/defer semantics in `orderExportWithFeedbackActivity`; current handler catches export exceptions, sets `exportResponseCode`, and the external task executor completes the task.

Recommended follow-up analysis:

- Inspect 1C logs for `2000467801` attempt 2 and compare XML against successful `2000467781` retry.
- Decide whether paid delivery should be present in terminal `COMPLETED` XML and how receipt allocation should cover it.
- Change OMS/Camunda flow so transient export failure can produce a retry instead of only an alert/result variable.
