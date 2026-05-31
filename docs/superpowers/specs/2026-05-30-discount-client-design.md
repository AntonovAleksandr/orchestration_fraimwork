# Discount Client — Design Spec v0.1.0

**Date:** 2026-05-30  
**Status:** approved (rev 2 — money units confirmed, structs unified, Rezult fail-closed, go 1.26.2)  
**Location:** `platform-new/clients/discount`  
**Module:** `gitlab.gloria.aaanet.ru/e-commerce/platform/clients/discount`

---

## 1. Context

WWWDKMVC / WWWDK_API is Gloria Jeans' legacy .NET loyalty & discount server ("сервер скидок"). It exposes a single multiplexed XML endpoint. The checkout service (and cert-sale UI) needs a faithful Go client. The protocol must **not** be modernised — it is XML-over-HTTP with rotating-word HMAC auth, not REST/JSON.

The existing PHP reference implementation lives at:  
`platform/integration/integration/www/app/Service/DiscountClient/`

---

## 2. Wire Protocol

### 2.1 Endpoint

```
POST /api/Query?idStore={storeID}&CheckSum={checksum}
Content-Type: application/gjdk
Body: XML (see per-op shapes below)
```

Operation is determined by the `Type` XML attribute on `<Request>`.

### 2.2 Auth — Rotating-Word HMAC

Every request:
1. Generate a **salt** — 10-digit numeric string (e.g. `fmt.Sprintf("%010d", rand.Int63n(9000000000)+1000000000)`).
2. Compute `checksum = strings.ToLower(hex(md5(storeID + word + salt)))`.
3. Inject `Salt="{salt}"` as an attribute on `<Request>`.
4. Set query params: `?idStore={storeID}&CheckSum={checksum}`.

**Word rotation:** if the server responds with `<Response Type="6" version="4.0" word="newWord"/>`, the client must:
1. Persist the new word via `WordStore.SetWord(newWord)`.
2. Retry the original request exactly **once** with the new word (wasRetried flag prevents infinite loops).
3. Never retry Type=5 errors or transport errors.

**Error response:** `<Response Type="5" version="4.0"><Error Description="..." Code="..." Name="..."/></Response>`

### 2.3 Response charset

The .NET server may return `windows-1251` (detectable from the `Content-Type: ...; charset=windows-1251` header). The client must decode to UTF-8 before XML parsing. Use `golang.org/x/text/encoding/charmap` if charset is `windows-1251`; otherwise assume UTF-8.

---

## 3. Operations — All 6

| Type | Schema (xmlns) | Ver | Name | Mutation? | Idempotency key |
|------|----------------|-----|------|-----------|-----------------|
| 1  | `.../4.8/GetDiscount`    | 4.8 | GetDiscount       | No  | — (stateless quote) |
| 15 | `.../4.3/ActivateCert`   | 4.3 | ActivateCertificate | Yes | DocId + cert IDs |
| 16 | `.../4.0/CreateCert`     | 4.0 | CreateCertificate | Yes | RequestIdentifier (UUID) |
| 17 | `.../4.1/BonusSpend`     | 4.1 | BonusSpend (coupon) | Yes | DOC = `"0000352" + clientOrderID` |
| 21 | `.../4.4/BonusSpendExt`  | 4.4 | BonusSpendExt (loyalty pts) | Yes | DOC = `"0000352" + clientOrderID` |
| 30 | `.../4.2/CuponTranslate` | 4.2 | CouponTranslate (promo code) | Yes | cartCode + email (server-side) |

Base URI prefix for all schemas: `http://discount.gloria-jeans.ru/Schema/`

---

## 4. Per-Operation Wire Shapes

### 4.1 GetDiscount (Type=1, schema 4.8)

**Request:**
```xml
<Request xmlns="http://discount.gloria-jeans.ru/Schema/4.8/GetDiscount"
         Type="1" version="4.8" Salt="1234567890"
         [SaleForOnline="true|false"] [SpecialCalculationId="123"]>
  [<Discount>discountOrCouponID</Discount>]
  <Good Qty="2" Price="1299.00" SellOff="0">SKU001</Good>  <!-- Price: РУБЛИ, decimal -->
  ...
</Request>
```

**Response:**
```xml
<Response Type="1" version="4.8">
  <Good ID="SKU001" Qty="2">
    <Discount DiscountMeta="42" DiscountType="1" Val="20.0"
              NeedQuestion="0" StoreVerified="0" [Reason="..."]/>
    <!-- DiscountType=1: Val=percent (не рубли); DiscountType=2: Val=РУБЛИ абс. скидка -->
  </Good>
  <DiscountMeta ID="42" Description="Акция 20%" Callback="http://..."
                [BonusPromo="true"] [DisplayName="..."]/>
  [<BillText .../>]
</Response>
```

`DiscountType`: 1=percent (Val=percent value, not rubles), 2=absolute amount (**Val=РУБЛИ**). `Val` is verbatim string on wire.

### 4.2 BonusSpend (Type=17, schema 4.1) — coupon

**Request:**
```xml
<Request xmlns="http://discount.gloria-jeans.ru/Schema/4.1/BonusSpend"
         Type="17" Salt="1234567890" Rollback="0">
  <Card>couponEAN13</Card>
  <DOC>0000352clientOrderID</DOC>
</Request>
```

**Response:** `<Response Type="17" version="4.1">ok</Response>` (XML text node)

**Rezult classification — FAIL-CLOSED:**
- `"ok"` → success (`SpendResult{Idempotent:false}`)
- suffix-matches `"IsSubmitted"` OR `"OparationCancelled"` → idempotent success (`SpendResult{Idempotent:true}`)
- **EVERYTHING ELSE** (including unknown/localized strings) → `*SpendError{Rezult: raw}`. Unknown text is NEVER treated as success.
- Raw string always preserved in `SpendResult.Raw` or `SpendError.Rezult`.

### 4.3 BonusSpendExt (Type=21, schema 4.4) — loyalty points

**Request:**
```xml
<Request xmlns="http://discount.gloria-jeans.ru/Schema/4.4/BonusSpendExt"
         Type="21" version="4.4" Salt="1234567890" Rollback="0">
  <Card>loyaltyCardID</Card>
  <DOC>0000352clientOrderID</DOC>
  <Summ>500.00</Summ>            <!-- РУБЛИ, decimal 2 знака, напр. "500.00" -->
  <Currency>RUB</Currency>
  <TypeOfDiscount>discountTypeID</TypeOfDiscount>
  <!-- optional per-item breakdown (v4.4 only): -->
  <Good Qty="1" Summ="250.00">SKU001</Good>  <!-- Good.Summ: РУБЛИ -->
</Request>
```

**Response:** `<Response Type="21" version="4.4">ok</Response>` (XML text node)

**Rezult classification — same FAIL-CLOSED rule:**
- `"ok"` → success
- suffix-matches `"IsSubmitted"` → idempotent success
- suffix-matches `"OparationCancelled"` → idempotent rollback success
- **EVERYTHING ELSE** → `*SpendError`. No exceptions.

### 4.4 CouponTranslate (Type=30, schema 4.2) — promo code → EAN-13

**Request:**
```xml
<Request xmlns="http://discount.gloria-jeans.ru/Schema/4.2/CuponTranslate"
         Type="30" version="4.2" Salt="1234567890" Rollback="0">
  <promocode>PROMO2024</promocode>
  <email>user@example.com</email>
  <cartcode>orderID</cartcode>
  [<cardnum>loyaltyCardNum</cardnum>]
  [<CustomerId>customerID</CustomerId>]
</Request>
```

**Response:** `<Response Type="30" version="4.2">{couponEAN13}</Response>` (text node)
- Rollback success returns `"1"`.
- `"0"` = operation not performed.

### 4.5 CreateCertificate (Type=16, schema 4.0)

**Request:**
```xml
<Request xmlns="http://discount.gloria-jeans.ru/Schema/4.0/CreateCert"
         Type="16" Salt="1234567890" RequestIdentifier="{uuid}">
  <Certificate>
    <GoodIDD>CERT-SKU-500</GoodIDD>
    [<CustomerPhone>+7...</CustomerPhone>]
    [<RecipientPhone>+7...</RecipientPhone>]
    [<RecipientName>Иван</RecipientName>]
    [<RecipientEmail>recv@example.com</RecipientEmail>]
    [<CongratulationText>Поздравляю!</CongratulationText>]
  </Certificate>
</Request>
```

**Response:**
```xml
<Response Type="16" version="4.0">
  <Certificate>
    <GoodIDD>CERT-SKU-500</GoodIDD>
    <Number>1234567890123</Number>
    [<CustomerPhone>...</CustomerPhone>]
    ...
  </Certificate>
</Response>
```

**Idempotency:** server deduplicates by `RequestIdentifier`. Client always generates a fresh UUID unless the caller supplies one (for retry scenarios).

### 4.6 ActivateCertificate (Type=15, schema 4.3)

**Request:**
```xml
<Request xmlns="http://discount.gloria-jeans.ru/Schema/4.3/ActivateCert"
         Type="15" Salt="1234567890" DocId="orderDocID" Rollback="0">
  <Certificate ID="1234567890123" Nominal="500.00" PrepaidPromo="false"  <!-- Nominal: РУБЛИ -->
               [Phone="+7..."] [CustomerPhone="+7..."]
               [RecipientName="Иван"] [RecipientEmail="recv@..."]>
    [<CongratulationText>...</CongratulationText>]
  </Certificate>
  ...
</Request>
```

**Response:**
```xml
<Response Type="15" version="4.3" DocId="orderDocID">
  <CertList>
    <Certificate ID="1234567890123" Nominal="500.00" [Code="..."]
                 [Token="..."] .../>
  </CertList>
  <Rezult>1</Rezult>   <!-- 1=ok, 0=errors -->
</Response>
```

**Idempotency:** server deduplicates by `DocId`. Rollback by same `DocId` + `Rollback="1"`.

---

## 5. Package Structure

```
platform-new/clients/discount/
├── doc.go              # package doc
├── go.mod              # module + replace for gj-go-httpclient
├── go.sum
├── client.go           # Client, Config, New(), xmlDo(), wordRotationRetry
├── auth.go             # WordStore interface, InMemoryWordStore, newSalt(), checksum()
├── xml.go              # all XML request/response structs + DOCFromOrderID()
├── api.go              # 6 public methods + rollback variants
├── errors.go           # ServerError, SpendError, classify rezult
├── charset.go          # charset detection + windows-1251 → UTF-8 conversion
├── testdata/
│   ├── get_discount_req.xml
│   ├── get_discount_resp.xml
│   ├── bonus_spend_req.xml        # Rollback=0
│   ├── bonus_spend_resp.xml       # "ok"
│   ├── bonus_spend_resp_dup.xml   # "BonusSpendExt_IsSubmitted" (idempotent)
│   ├── bonus_spend_resp_fail.xml  # "BonusSpendExt_NoBonusQty" (error)
│   ├── bonus_spend_ext_req.xml
│   ├── bonus_spend_ext_resp.xml
│   ├── coupon_translate_req.xml
│   ├── coupon_translate_resp.xml
│   ├── create_cert_req.xml        # fixed RequestIdentifier + Salt for deterministic checksum
│   ├── create_cert_resp.xml
│   ├── activate_cert_req.xml
│   ├── activate_cert_resp.xml
│   ├── activate_cert_resp_error.xml  # Type=5
│   ├── error_resp.xml             # Type=5 generic
│   └── word_rotation_resp.xml     # Type=6
└── client_test.go
```

---

## 6. Core Types

### 6.1 Client & Config

```go
type Config struct {
    BaseURL   string     // scheme+host, no trailing slash
    StoreID   string     // default storeID; per-request override via request field
    WordStore WordStore
}

type Client struct {
    hc      *httpclient.Client
    config  Config
}

func New(cfg Config, opts ...httpclient.Option) (*Client, error)
```

### 6.2 Auth

```go
type WordStore interface {
    Word() (string, error)
    SetWord(word string) error
}

// InMemoryWordStore is goroutine-safe; suitable for single-process deployments.
type InMemoryWordStore struct {
    mu   sync.RWMutex
    word string
}

func NewInMemoryWordStore(initialWord string) *InMemoryWordStore

func newSalt() string  // 10-digit numeric string via crypto/rand
func checksum(storeID, word, salt string) string  // lowercase hex(md5(storeID+word+salt))
```

### 6.3 xmlDo flow (internal)

```go
// xmlDo: authenticate → send → detect Type=6 → optional retry → return raw XML bytes.
// wasRetried prevents infinite retry loops.
func (c *Client) xmlDo(ctx context.Context, op, storeID, xmlBody string) ([]byte, error)
```

Flow:
1. `word ← WordStore.Word()`
2. `salt ← newSalt()`
3. `checksum ← checksum(storeID, word, salt)`
4. Inject `Salt="{salt}"` into `xmlBody` (string replace on `<Request ` prefix)
5. Build `*http.Request` POST to `/api/Query?idStore={storeID}&CheckSum={checksum}`, body=xmlBody, `Content-Type: application/gjdk`
6. `resp ← hc.Do(ctx, op, req)`
7. Read body; detect charset from Content-Type header; convert to UTF-8 if needed
8. Parse `<Response Type="T" [word="W"]>`
   - T=6 → `WordStore.SetWord(W)`, retry once (wasRetried=true), goto 1
   - T=5 → return `*ServerError{Code, Description, Name}`
   - else → return raw `[]byte`

### 6.4 XML Types (key structs)

```go
// ---- Request base ----
// All requests embed these attributes on <Request>
// Salt is always set by xmlDo; callers do not set it.

// ---- GetDiscount ----
type GetDiscountItem struct {
    ProductID string // XmlText on <Good>
    Qty       int    `xml:"Qty,attr"`
    Price     string `xml:"Price,attr"` // РУБЛИ, decimal verbatim ("1299.00"); consumer converts to Money
    SellOff   int    `xml:"SellOff,attr"`
    Discount  string `xml:"Discount,attr,omitempty"` // per-item promo
}

type GetDiscountRequest struct {
    StoreID              string // optional override; uses Config.StoreID if empty
    Items                []GetDiscountItem
    DiscountID           string  // promo/coupon ID applied to whole basket
    SaleForOnline        *bool
    SpecialCalculationID string
}

type DiscountValue struct {
    DiscountMetaID int    `xml:"DiscountMeta,attr"`
    DiscountType   int    `xml:"DiscountType,attr"` // 1=percent, 2=absolute РУБЛИ
    Val            string `xml:"Val,attr"`           // verbatim: percent ("20.0") or РУБЛИ ("50.00"); consumer converts
    NeedQuestion   int    `xml:"NeedQuestion,attr"`
    StoreVerified  int    `xml:"StoreVerified,attr"`
    Reason         string `xml:"Reason,attr,omitempty"`
}

type GetDiscountGood struct {
    ID        string         `xml:"ID,attr"`
    Qty       int            `xml:"Qty,attr"`
    Discounts []DiscountValue `xml:"Discount"`
}

type DiscountMeta struct {
    ID          int    `xml:"ID,attr"`
    Description string `xml:"Description,attr"`
    QuestionText string `xml:"QuestionText,attr,omitempty"`
    Callback    string `xml:"Callback,attr,omitempty"`
    BonusPromo  bool   `xml:"BonusPromo,attr,omitempty"`
    DisplayName string `xml:"DisplayName,attr,omitempty"`
}

type GetDiscountResponse struct {
    Type     int               `xml:"Type,attr"`
    Version  string            `xml:"version,attr"`
    Goods    []GetDiscountGood `xml:"Good"`
    Metas    []DiscountMeta    `xml:"DiscountMeta"`
}

// ---- Spend (BonusSpend + BonusSpendExt) ----
// SpendResult is the classified result of a spend/return operation.
type SpendResult struct {
    Raw        string // verbatim Rezult text from server
    Idempotent bool   // true if server indicated already-done (IsSubmitted etc.)
}

// ---- BonusSpend (coupon) ----
type SpendCouponRequest struct {
    StoreID       string // optional; empty → Config.StoreID
    CouponID      string // EAN-13 coupon number
    ClientOrderID string // DOC = "0000352" + ClientOrderID
}

// ---- BonusSpendExt (loyalty points) ----
type BonusSpendExtItem struct {
    ProductID string // XML text
    Qty       int    `xml:"Qty,attr"`
    Summ      string `xml:"Summ,attr"` // РУБЛИ, decimal verbatim; consumer converts to Money
}

type SpendBonusExtRequest struct {
    StoreID        string
    LoyaltyCardID  string
    ClientOrderID  string // DOC = "0000352" + ClientOrderID
    Summ           string // РУБЛИ, decimal verbatim ("500.00"); consumer converts to Money
    Currency       string
    DiscountTypeID int
    Items          []BonusSpendExtItem // optional per-item breakdown (v4.4)
}

// ---- CouponTranslate ----
type TranslatePromoCodeRequest struct {
    StoreID    string
    OrderID    string // cartcode
    Email      string
    PromoCode  string
    CardNum    string // optional loyalty card
    CustomerID string // optional
}

// ---- CreateCertificate ----
type CreateCertRequest struct {
    StoreID           string
    GoodIDD           string // product SKU for the certificate
    CustomerPhone     string
    RecipientPhone    string
    RecipientName     string
    RecipientEmail    string
    CongratulationText string
    // RequestIdentifier is generated by the client (uuid.New().String()) unless caller sets it
    RequestIdentifier  string
}

type CreateCertResult struct {
    GoodIDD           string
    Number            string // generated cert EAN number
    CustomerPhone     string
    RecipientPhone    string
    RecipientName     string
    RecipientEmail    string
    CongratulationText string
}

// ---- ActivateCertificate ----
type CertActivationItem struct {
    ID                 string
    Nominal            string // РУБЛИ, decimal verbatim ("500.00"); consumer converts to Money
    PrepaidPromo       bool
    Phone              string
    CustomerPhone      string
    RecipientName      string
    RecipientEmail     string
    CongratulationText string
    Number             string // loyalty card number (binding)
}

type ActivateCertRequest struct {
    StoreID string
    DocID   string
    Certs   []CertActivationItem
}

type ActivatedCert struct {
    ID                 string
    Nominal            string // РУБЛИ, decimal verbatim — returned from server as-is
    PrepaidPromo       bool
    Code               string
    Phone              string
    CustomerPhone      string
    RecipientName      string
    RecipientEmail     string
    CongratulationText string
    Token              string
}

type ActivateCertResult struct {
    DocID  string
    Certs  []ActivatedCert
    Result int // 1=ok, 0=errors
}
```

### 6.5 Errors

```go
// ServerError is returned when the discount server responds with Type=5.
type ServerError struct {
    Code        int
    Description string
    Name        string
}
func (e *ServerError) Error() string

// SpendError is returned when a spend operation's Rezult is a failure key,
// not a Type=5 error (server returned HTTP 200 with a failure text body).
type SpendError struct {
    Rezult string // raw localization key from server
}
func (e *SpendError) Error() string
```

---

## 7. Public API

```go
// GetDiscount returns the discount calculation for the basket (stateless, advisory).
func (c *Client) GetDiscount(ctx context.Context, req GetDiscountRequest) (GetDiscountResponse, error)

// SpendCoupon activates (spends) a coupon. Idempotent by DOC.
func (c *Client) SpendCoupon(ctx context.Context, req SpendCouponRequest) (SpendResult, error)

// ReturnCoupon rolls back a coupon spend. Idempotent by DOC.
func (c *Client) ReturnCoupon(ctx context.Context, req SpendCouponRequest) (SpendResult, error)

// SpendBonusExt spends loyalty bonus points. Idempotent by DOC.
func (c *Client) SpendBonusExt(ctx context.Context, req SpendBonusExtRequest) (SpendResult, error)

// ReturnBonusExt rolls back a loyalty bonus spend. Idempotent by DOC.
func (c *Client) ReturnBonusExt(ctx context.Context, req SpendBonusExtRequest) (SpendResult, error)

// TranslatePromoCode resolves a human-readable promo code to a coupon EAN-13.
// Idempotent by cartCode+email (server-side).
func (c *Client) TranslatePromoCode(ctx context.Context, req TranslatePromoCodeRequest) (string, error)

// RollbackPromoCode rolls back a promo code translation. Returns nil on success.
func (c *Client) RollbackPromoCode(ctx context.Context, req TranslatePromoCodeRequest) error

// CreateCertificate creates and pre-populates a gift certificate. Idempotent by RequestIdentifier.
func (c *Client) CreateCertificate(ctx context.Context, req CreateCertRequest) (CreateCertResult, error)

// ActivateCertificate activates one or more certificates. Idempotent by DocID.
func (c *Client) ActivateCertificate(ctx context.Context, req ActivateCertRequest) (ActivateCertResult, error)

// RollbackCertificate reverses certificate activation. Returns nil on success.
func (c *Client) RollbackCertificate(ctx context.Context, req ActivateCertRequest) error
```

---

## 8. Tests

All tests use `httptest.NewServer` with canned XML responses. No real network calls.

| Test | Fixture | Assertion |
|------|---------|-----------|
| `TestGetDiscount_Happy` | `get_discount_resp.xml` | Parses Goods + DiscountMeta correctly |
| `TestBonusSpend_Happy` | `bonus_spend_resp.xml` ("ok") | Returns SpendResult{Idempotent:false} |
| `TestBonusSpend_Duplicate` | `bonus_spend_resp_dup.xml` ("BonusSpendExt_IsSubmitted") | Returns SpendResult{Idempotent:true} |
| `TestBonusSpend_NoBonusQty` | `bonus_spend_resp_fail.xml` | Returns *SpendError |
| `TestBonusSpendExt_Happy` | `bonus_spend_ext_resp.xml` | Returns SpendResult{Idempotent:false} |
| `TestCouponTranslate_Happy` | `coupon_translate_resp.xml` | Returns EAN-13 string |
| `TestCreateCertificate_Happy` | `create_cert_resp.xml` | Returns CreateCertResult with Number |
| `TestActivateCertificate_Happy` | `activate_cert_resp.xml` | Rezult==1, cert list populated |
| `TestActivateCertificate_ServerError` | `activate_cert_resp_error.xml` (Type=5) | Returns *ServerError |
| `TestWordRotation_RetryOnce` | word_rotation_resp.xml then success | 2 HTTP calls; word updated; retried |
| `TestWordRotation_NoDoubleRetry` | Two consecutive Type=6 responses | Only 1 retry; second Type=6 → error |
| `TestChecksum_Deterministic` | Fixed storeID+word+salt | md5 matches expected hex |
| `TestDOCFromOrderID` | — | "0000352"+"ABC" == "0000352ABC" |

---

## 9. go.mod

```
module gitlab.gloria.aaanet.ru/e-commerce/platform/clients/discount

go 1.26.2

require (
    github.com/google/uuid v1.6.0
    gitlab.gloria.aaanet.ru/go-pkg/gj-go-httpclient v0.0.0-00010101000000-000000000000
    golang.org/x/text v0.x.x
)

replace gitlab.gloria.aaanet.ru/go-pkg/gj-go-httpclient => ../../gj-go-httpclient
```

---

## 10. Key Design Decisions

1. **No oapi-codegen / code generation** — contract is legacy XML, hand-crafted Go structs with `xml:` tags.
2. **Salt in XML body** — generated in `xmlDo`, injected by string-replacing `<Request ` with `<Request Salt="X" `. This mirrors PHP middleware behavior and avoids double-parse.
3. **CertificateActivationItem base** — v4.1 uses `CertificateActivationItem` (ID, Nominal, PrepaidPromo, Phone, CustomerPhone, RecipientName, CongratulationText); v4.3 extends with Code, Token, Number, RecipientEmail, CongratulationText. Go client uses v4.3 shape (`ActivateCertificate`) as it's the current schema.
4. **SpendResult vs SpendError** — server returns HTTP 200 with a text body that can be "ok", a known idempotent key, or a failure key. This is distinct from Type=5 (ServerError). Both are modelled explicitly.
5. **WordStore interface** — `InMemoryWordStore` is provided; callers can inject a distributed store (Redis, etc.) by implementing the interface.
6. **Per-request storeID** — all request types have an optional `StoreID` field; if empty, `Config.StoreID` is used.
7. **DOC constant** — `const saleIDPrefix = "0000352"` (from `SaleIdEnum::DEFAULT_SALE_ID`). `DOCFromOrderID` = `saleIDPrefix + clientOrderID`. Cert idempotency uses `DocId` (not DOC format), set by the caller.
8. **RequestIdentifier for cert creation** — if caller leaves it empty, `xmlDo` generates `uuid.New().String()`. The caller can supply a fixed UUID for retry idempotency.
9. **Money units — РУБЛИ (decimal)** — confirmed by server-side comparisons: `bonus_nominal_rus = 200m` (200₽), `> 2500m` (2500₽ basket threshold), cert nominals 500₽, loyalty `Summ` in rubles. All monetary fields on the wire are decimal strings ("500.00", "1299.00"). Client DTOs hold verbatim `string`; consumer (checkout adapter) converts to `Money` (kopecks ×100). NEVER `float64` in DTO.
10. **Rezult classification is FAIL-CLOSED** — only `"ok"` and suffix-matches on `"IsSubmitted"` / `"OparationCancelled"` are success. Every other string (including unknown localized messages the server may return in different locales) returns `*SpendError`. This prevents silent data loss if the server changes message text.
