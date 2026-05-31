# Discount Client v0.1.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a faithful Go client for the WWWDKMVC legacy XML discount server at `platform-new/clients/discount`, covering all 6 operations (GetDiscount, BonusSpend, BonusSpendExt, CouponTranslate, CreateCertificate, ActivateCertificate) with rotating-word HMAC auth, charset decoding, idempotency semantics, and fixture-based tests.

**Architecture:** Single-package `discount` on top of `gj-go-httpclient` (escape-hatch `Do`). Internal XML structs handle marshaling/unmarshaling. `xmlDo` handles auth, word-rotation retry (exactly once), charset decode, and error classification. Public domain types (no xml tags) map 1:1 to/from the internal XML types.

**Tech Stack:** Go 1.26.2, `encoding/xml` (stdlib), `crypto/md5`+`crypto/rand` (stdlib), `golang.org/x/text` (charset decode), `github.com/google/uuid`, `gitlab.gloria.aaanet.ru/go-pkg/gj-go-httpclient` (local replace).

---

## File Map

| File | Responsibility |
|------|---------------|
| `go.mod` | Module declaration, deps, replace directives |
| `doc.go` | Package doc |
| `auth.go` | `WordStore` interface, `InMemoryWordStore`, `newSalt()`, `checksum()` |
| `charset.go` | `decodeCharset()` — windows-1251 → UTF-8 |
| `errors.go` | `ServerError`, `SpendError`, `classifyRezult()` |
| `types.go` | All public domain types (no xml tags): `GetDiscountRequest`, `SpendCouponRequest`, `SpendBonusExtRequest`, `TranslatePromoCodeRequest`, `CreateCertRequest`, `ActivateCertRequest`, `SpendResult`, `GetDiscountResponse`, `CreateCertResult`, `ActivateCertResult`, `DOCFromOrderID()` |
| `xml.go` | Internal XML structs (unexported) + `marshalXxx()` / `unmarshalXxx()` functions for each operation, + `encodeXML()` helper |
| `client.go` | `Config`, `Client`, `New()`, `xmlDo()` (authenticates, sends, detects word rotation / Type=5, returns raw bytes) |
| `api.go` | 10 public methods: `GetDiscount`, `SpendCoupon`, `ReturnCoupon`, `SpendBonusExt`, `ReturnBonusExt`, `TranslatePromoCode`, `RollbackPromoCode`, `CreateCertificate`, `ActivateCertificate`, `RollbackCertificate` |
| `testdata/*.xml` | 15 XML fixture files (see Task 6 onwards) |
| `client_test.go` | All tests (single file, table-driven where natural) |
| `README.md` | Package docs, config, usage examples, unit note |

---

## Task 1: Module Scaffold

**Files:**
- Create: `platform-new/clients/discount/go.mod`
- Create: `platform-new/clients/discount/doc.go`

- [ ] **Step 1: Create the directory**

```bash
mkdir -p /path/to/platform-new/clients/discount/testdata
```

- [ ] **Step 2: Write `go.mod`**

```
module gitlab.gloria.aaanet.ru/e-commerce/platform/clients/discount

go 1.26.2

require (
	github.com/google/uuid v1.6.0
	gitlab.gloria.aaanet.ru/go-pkg/gj-go-httpclient v0.0.0-00010101000000-000000000000
	golang.org/x/text v0.21.0
)

require (
	github.com/beorn7/perks v1.0.1 // indirect
	github.com/cespare/xxhash/v2 v2.3.0 // indirect
	github.com/mattn/go-colorable v0.1.14 // indirect
	github.com/mattn/go-isatty v0.0.20 // indirect
	github.com/munnerz/goautoneg v0.0.0-20191010083416-a7dc8b61c822 // indirect
	github.com/prometheus/client_golang v1.23.2 // indirect
	github.com/prometheus/client_model v0.6.2 // indirect
	github.com/prometheus/common v0.66.1 // indirect
	github.com/prometheus/procfs v0.16.1 // indirect
	github.com/rs/zerolog v1.33.0 // indirect
	gitlab.gloria.aaanet.ru/go-pkg/gj-go-logger v1.0.5 // indirect
	golang.org/x/sys v0.39.0 // indirect
)

replace gitlab.gloria.aaanet.ru/go-pkg/gj-go-httpclient => ../../gj-go-httpclient
```

- [ ] **Step 3: Write `doc.go`**

```go
// Package discount is a faithful Go client for the WWWDKMVC "сервер скидок"
// (discount/loyalty server). It speaks legacy XML-over-HTTP, not REST/JSON.
//
// All monetary fields (Price, Summ, Nominal, Val when DiscountType=2) are
// РУБЛИ with 2 decimal places, transmitted verbatim as strings. Consumers
// must convert to their own Money type; never parse to float64.
//
// Auth uses a rotating shared secret (WordStore). On receiving a Type=6
// response the client saves the new word and retries exactly once.
package discount
```

- [ ] **Step 4: Run `go mod tidy` to fetch deps and generate `go.sum`**

```bash
cd platform-new/clients/discount
go mod tidy
```

Expected: exits 0, creates `go.sum`.

- [ ] **Step 5: Sanity build**

```bash
go build ./...
```

Expected: exits 0 (nothing to build yet, but module resolution OK).

- [ ] **Step 6: Commit**

```bash
git add go.mod go.sum doc.go
git commit -m "feat(discount-client): scaffold module"
```

---

## Task 2: Auth Layer

**Files:**
- Create: `platform-new/clients/discount/auth.go`
- Create: `platform-new/clients/discount/auth_test.go`

- [ ] **Step 1: Write the failing tests in `auth_test.go`**

```go
package discount

import (
	"sync"
	"testing"
)

func TestNewSalt_Format(t *testing.T) {
	s := newSalt()
	if len(s) != 10 {
		t.Fatalf("expected 10-digit salt, got %q (len=%d)", s, len(s))
	}
	for _, c := range s {
		if c < '0' || c > '9' {
			t.Fatalf("salt contains non-digit %q in %q", c, s)
		}
	}
	if s[0] == '0' {
		t.Fatalf("salt must not start with 0, got %q", s)
	}
}

func TestNewSalt_Unique(t *testing.T) {
	seen := map[string]bool{}
	for i := 0; i < 1000; i++ {
		s := newSalt()
		if seen[s] {
			t.Fatalf("duplicate salt %q at iteration %d", s, i)
		}
		seen[s] = true
	}
}

func TestChecksum_Deterministic(t *testing.T) {
	// md5("9999999" + "secret" + "1234567890") = 6d849bd8720de9c4663461035ff04382
	want := "6d849bd8720de9c4663461035ff04382"
	got := checksum("9999999", "secret", "1234567890")
	if got != want {
		t.Errorf("checksum: got %q, want %q", got, want)
	}
}

func TestChecksum_LowercaseHex(t *testing.T) {
	cs := checksum("storeA", "wordB", "0123456789")
	if len(cs) != 32 {
		t.Errorf("expected 32-char hex, got len=%d", len(cs))
	}
	for _, ch := range cs {
		if !(ch >= '0' && ch <= '9') && !(ch >= 'a' && ch <= 'f') {
			t.Errorf("non-lowercase-hex char %q in checksum %q", ch, cs)
		}
	}
}

func TestInMemoryWordStore_GetSet(t *testing.T) {
	s := NewInMemoryWordStore("alpha")
	w, err := s.Word()
	if err != nil || w != "alpha" {
		t.Fatalf("Word() = %q, %v; want %q, nil", w, err, "alpha")
	}
	if err := s.SetWord("beta"); err != nil {
		t.Fatalf("SetWord: %v", err)
	}
	w, _ = s.Word()
	if w != "beta" {
		t.Errorf("after SetWord(beta): got %q", w)
	}
}

func TestInMemoryWordStore_EmptyWord(t *testing.T) {
	s := NewInMemoryWordStore("")
	_, err := s.Word()
	if err == nil {
		t.Fatal("expected error for empty word, got nil")
	}
}

func TestInMemoryWordStore_Concurrent(t *testing.T) {
	s := NewInMemoryWordStore("start")
	var wg sync.WaitGroup
	for i := 0; i < 200; i++ {
		wg.Add(2)
		go func() { defer wg.Done(); s.Word() }()      //nolint:errcheck
		go func() { defer wg.Done(); s.SetWord("x") }() //nolint:errcheck
	}
	wg.Wait()
}
```

- [ ] **Step 2: Run tests → expect failure**

```bash
go test ./... -run TestNewSalt -v
```

Expected: FAIL — `newSalt` undefined.

- [ ] **Step 3: Write `auth.go`**

```go
package discount

import (
	"crypto/md5"
	"crypto/rand"
	"encoding/binary"
	"fmt"
	"sync"
)

// WordStore persists and rotates the shared secret used for CheckSum auth.
// Implement for Redis, databases, etc. in multi-instance deployments.
type WordStore interface {
	Word() (string, error)
	SetWord(word string) error
}

// InMemoryWordStore is a goroutine-safe in-memory WordStore.
type InMemoryWordStore struct {
	mu   sync.RWMutex
	word string
}

// NewInMemoryWordStore initialises a store with the given word.
func NewInMemoryWordStore(initialWord string) *InMemoryWordStore {
	return &InMemoryWordStore{word: initialWord}
}

// Word returns the current word or an error if it is empty.
func (s *InMemoryWordStore) Word() (string, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if s.word == "" {
		return "", fmt.Errorf("discount: word not configured")
	}
	return s.word, nil
}

// SetWord replaces the current word.
func (s *InMemoryWordStore) SetWord(word string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.word = word
	return nil
}

// newSalt generates a random 10-digit numeric salt (1_000_000_000–9_999_999_999).
func newSalt() string {
	var b [8]byte
	if _, err := rand.Read(b[:]); err != nil {
		panic("discount: rand.Read: " + err.Error())
	}
	n := binary.BigEndian.Uint64(b[:])
	n = n%9_000_000_000 + 1_000_000_000
	return fmt.Sprintf("%d", n)
}

// checksum returns lowercase hex(md5(storeID + word + salt)).
// This is the CheckSum query parameter sent to the discount server.
func checksum(storeID, word, salt string) string {
	h := md5.Sum([]byte(storeID + word + salt))
	return fmt.Sprintf("%x", h)
}
```

- [ ] **Step 4: Run tests → expect pass**

```bash
go test ./... -run "TestNewSalt|TestChecksum|TestInMemoryWordStore" -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add auth.go auth_test.go
git commit -m "feat(discount-client): auth — WordStore, salt, checksum"
```

---

## Task 3: Charset Decoding

**Files:**
- Create: `platform-new/clients/discount/charset.go`
- Create: `platform-new/clients/discount/charset_test.go`

- [ ] **Step 1: Write failing tests in `charset_test.go`**

```go
package discount

import (
	"testing"
)

func TestDecodeCharset_Windows1251(t *testing.T) {
	// "тест" in windows-1251: 0xF2 0xE5 0xF1 0xF2
	input := []byte{0xF2, 0xE5, 0xF1, 0xF2}
	got, err := decodeCharset("text/xml; charset=windows-1251", input)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if string(got) != "тест" {
		t.Errorf("got %q, want %q", got, "тест")
	}
}

func TestDecodeCharset_UTF8_Passthrough(t *testing.T) {
	input := []byte("привет")
	got, err := decodeCharset("text/xml; charset=utf-8", input)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != "привет" {
		t.Errorf("got %q", got)
	}
}

func TestDecodeCharset_NoCharset_Passthrough(t *testing.T) {
	input := []byte("<Response/>")
	got, err := decodeCharset("text/xml", input)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != "<Response/>" {
		t.Errorf("got %q", got)
	}
}

func TestDecodeCharset_EmptyContentType(t *testing.T) {
	input := []byte("<ok/>")
	got, err := decodeCharset("", input)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != "<ok/>" {
		t.Errorf("got %q", got)
	}
}
```

- [ ] **Step 2: Run → expect FAIL**

```bash
go test ./... -run TestDecodeCharset -v
```

Expected: FAIL — `decodeCharset` undefined.

- [ ] **Step 3: Write `charset.go`**

```go
package discount

import (
	"strings"

	"golang.org/x/text/encoding/charmap"
	"golang.org/x/text/transform"
)

// decodeCharset converts raw response bytes to UTF-8.
// It parses the charset from the Content-Type header value.
// Only windows-1251 needs conversion; everything else is passed through.
func decodeCharset(contentType string, data []byte) ([]byte, error) {
	cs := parseCharset(contentType)
	switch strings.ToLower(cs) {
	case "windows-1251", "cp1251", "cp-1251":
		return transform.Bytes(charmap.Windows1251.NewDecoder(), data)
	default:
		// Treat as UTF-8 or unknown — return as-is.
		return data, nil
	}
}

// parseCharset extracts the charset value from a Content-Type header like
// "text/xml; charset=windows-1251". Returns empty string if not present.
func parseCharset(ct string) string {
	for _, part := range strings.Split(ct, ";") {
		part = strings.TrimSpace(part)
		if strings.HasPrefix(strings.ToLower(part), "charset=") {
			return strings.TrimPrefix(strings.TrimPrefix(part, "charset="), "Charset=")
		}
	}
	return ""
}
```

- [ ] **Step 4: Run → expect PASS**

```bash
go test ./... -run TestDecodeCharset -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add charset.go charset_test.go
git commit -m "feat(discount-client): charset — windows-1251 decode"
```

---

## Task 4: Errors & Rezult Classification

**Files:**
- Create: `platform-new/clients/discount/errors.go`
- Create: `platform-new/clients/discount/errors_test.go`

- [ ] **Step 1: Write failing tests in `errors_test.go`**

```go
package discount

import (
	"errors"
	"testing"
)

func TestServerError_Error(t *testing.T) {
	e := &ServerError{Code: 5, Description: "Ошибка авторизации", Name: "NotAllowed"}
	want := "discount server error 5 (NotAllowed): Ошибка авторизации"
	if e.Error() != want {
		t.Errorf("got %q, want %q", e.Error(), want)
	}
}

func TestSpendError_Error(t *testing.T) {
	e := &SpendError{Rezult: "BonusSpendExt_NoBonusQty"}
	want := "discount spend failed: BonusSpendExt_NoBonusQty"
	if e.Error() != want {
		t.Errorf("got %q, want %q", e.Error(), want)
	}
}

var classifyTests = []struct {
	rezult     string
	wantErr    bool
	idempotent bool
}{
	{"ok", false, false},
	{"BonusSpendExt_IsSubmitted", false, true},
	{"IsSubmitted", false, true},                    // suffix match
	{"SomethingIsSubmitted", false, true},           // suffix match
	{"BonusSpendExt_OparationCancelled", false, true},
	{"OparationCancelled", false, true},             // suffix match
	{"BonusSpendExt_NoBonusQty", true, false},
	{"CuponIsUsed", true, false},
	{"WrongNumber", true, false},
	{"", true, false},                               // empty = error (fail-closed)
	{"НеизвестнаяОшибка", true, false},              // unknown localized string = error
	{"ok_extra", true, false},                       // not exactly "ok" = error
}

func TestClassifyRezult(t *testing.T) {
	for _, tc := range classifyTests {
		t.Run(tc.rezult, func(t *testing.T) {
			result, err := classifyRezult(tc.rezult)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error for %q, got nil (result=%+v)", tc.rezult, result)
				}
				var spendErr *SpendError
				if !errors.As(err, &spendErr) {
					t.Fatalf("expected *SpendError, got %T: %v", err, err)
				}
				if spendErr.Rezult != tc.rezult {
					t.Errorf("SpendError.Rezult = %q, want %q", spendErr.Rezult, tc.rezult)
				}
			} else {
				if err != nil {
					t.Fatalf("unexpected error for %q: %v", tc.rezult, err)
				}
				if result.Raw != tc.rezult {
					t.Errorf("SpendResult.Raw = %q, want %q", result.Raw, tc.rezult)
				}
				if result.Idempotent != tc.idempotent {
					t.Errorf("SpendResult.Idempotent = %v, want %v for %q", result.Idempotent, tc.idempotent, tc.rezult)
				}
			}
		})
	}
}
```

- [ ] **Step 2: Run → expect FAIL**

```bash
go test ./... -run "TestServerError|TestSpendError|TestClassifyRezult" -v
```

Expected: FAIL — types undefined.

- [ ] **Step 3: Write `errors.go`**

```go
package discount

import (
	"fmt"
	"strings"
)

// ServerError is returned when the discount server responds with Type=5
// (explicit error response). Distinct from a transport error.
type ServerError struct {
	Code        int
	Description string
	Name        string
}

func (e *ServerError) Error() string {
	return fmt.Sprintf("discount server error %d (%s): %s", e.Code, e.Name, e.Description)
}

// SpendError is returned when a spend/return operation's Rezult text is not a
// recognised success key. The server returned HTTP 200, but the body indicates
// a business-level failure. Raw text is preserved in Rezult.
type SpendError struct {
	Rezult string
}

func (e *SpendError) Error() string {
	return fmt.Sprintf("discount spend failed: %s", e.Rezult)
}

// classifyRezult maps the text body of a spend/return response to either a
// successful SpendResult or a *SpendError. Rule is FAIL-CLOSED: only "ok" and
// suffix-matches on "IsSubmitted"/"OparationCancelled" are treated as success.
// Every other string — including unknown/localised strings — returns *SpendError.
func classifyRezult(rezult string) (SpendResult, error) {
	switch {
	case rezult == "ok":
		return SpendResult{Raw: rezult, Idempotent: false}, nil
	case strings.HasSuffix(rezult, "IsSubmitted"):
		return SpendResult{Raw: rezult, Idempotent: true}, nil
	case strings.HasSuffix(rezult, "OparationCancelled"):
		return SpendResult{Raw: rezult, Idempotent: true}, nil
	default:
		return SpendResult{}, &SpendError{Rezult: rezult}
	}
}
```

Note: `SpendResult` is defined in `types.go` (Task 5). Add a temporary stub for now or write Task 5 immediately after.

- [ ] **Step 4: Write `types.go` stubs (full version in Task 5)**

Since `errors.go` references `SpendResult`, write the minimal stub to unblock compilation:

```go
package discount

// SpendResult is returned on a successful spend or idempotent re-spend.
// Expanded with all public types in Task 5.
type SpendResult struct {
	Raw        string // verbatim Rezult text from server
	Idempotent bool   // true when server already registered the operation
}
```

- [ ] **Step 5: Run tests → expect PASS**

```bash
go test ./... -run "TestServerError|TestSpendError|TestClassifyRezult" -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add errors.go errors_test.go types.go
git commit -m "feat(discount-client): errors — ServerError, SpendError, classifyRezult (fail-closed)"
```

---

## Task 5: Public Types & XML Types

**Files:**
- Modify: `platform-new/clients/discount/types.go` (replace stub with full types)
- Create: `platform-new/clients/discount/xml.go`

No new tests in this task — XML correctness is verified in Tasks 7–12 via round-trip fixture tests.

- [ ] **Step 1: Replace `types.go` with full public types**

```go
package discount

// ─── Money note ───────────────────────────────────────────────────────────────
// ALL monetary fields (Price, Summ, Nominal, Val when DiscountType=2) are
// РУБЛИ as decimal strings verbatim from the wire ("500.00", "1299.00").
// Never parse to float64. The consuming adapter (checkout service) converts
// to its own Money type (kopecks ×100).
// ──────────────────────────────────────────────────────────────────────────────

const saleIDPrefix = "0000352"

// DOCFromOrderID builds the DOC field: "0000352" + clientOrderID.
// This is the idempotency key used by BonusSpend and BonusSpendExt.
func DOCFromOrderID(clientOrderID string) string {
	return saleIDPrefix + clientOrderID
}

// ─── GetDiscount ──────────────────────────────────────────────────────────────

// GetDiscountItem is one product line in a GetDiscount request.
type GetDiscountItem struct {
	ProductID string // product SKU / barcode
	Qty       int
	Price     string // РУБЛИ, decimal verbatim ("1299.00")
	SellOff   int    // 0=regular, 1=first markdown, 2=second, 3=clearance
	Discount  string // optional per-item promo/coupon ID
}

// GetDiscountRequest describes a basket for advisory discount calculation.
type GetDiscountRequest struct {
	StoreID              string // optional; empty → Config.StoreID
	Items                []GetDiscountItem
	DiscountID           string // promo/coupon ID applied to whole basket
	SaleForOnline        *bool  // nil = not sent
	SpecialCalculationID int    // 0 = not sent
}

// DiscountValue is one discount applied to a basket item.
type DiscountValue struct {
	DiscountMetaID int
	DiscountType   int    // 1=percent, 2=absolute РУБЛИ
	Val            string // verbatim: percent ("20.0") or РУБЛИ ("50.00")
	NeedQuestion   int    // 1 = cashier must confirm
	StoreVerified  int    // 1 = phone verification required
	Reason         string
}

// GetDiscountGood is one item in a GetDiscount response.
type GetDiscountGood struct {
	ID        string
	Qty       int
	Discounts []DiscountValue
}

// DiscountMeta describes an active promo referenced by a DiscountValue.
type DiscountMeta struct {
	ID           int
	Description  string
	QuestionText string
	Callback     string
	BonusPromo   bool
	DisplayName  string
}

// GetDiscountResponse is the result of GetDiscount.
type GetDiscountResponse struct {
	Goods []GetDiscountGood
	Metas []DiscountMeta
}

// ─── Spend (BonusSpend) ───────────────────────────────────────────────────────

// SpendResult is returned on a successful spend or idempotent re-spend.
type SpendResult struct {
	Raw        string // verbatim Rezult text from server
	Idempotent bool   // true when server already registered the operation
}

// SpendCouponRequest is the input for SpendCoupon / ReturnCoupon.
type SpendCouponRequest struct {
	StoreID       string // optional; empty → Config.StoreID
	CouponID      string // EAN-13 coupon number
	ClientOrderID string // DOC = "0000352" + ClientOrderID
}

// ─── Spend (BonusSpendExt) ────────────────────────────────────────────────────

// BonusSpendExtItem is per-item bonus allocation (v4.4 only).
type BonusSpendExtItem struct {
	ProductID string
	Qty       int
	Summ      string // РУБЛИ, decimal verbatim
}

// SpendBonusExtRequest is the input for SpendBonusExt / ReturnBonusExt.
type SpendBonusExtRequest struct {
	StoreID        string
	LoyaltyCardID  string
	ClientOrderID  string             // DOC = "0000352" + ClientOrderID
	Summ           string             // РУБЛИ, decimal verbatim ("500.00")
	Currency       string             // "RUB", "UAH", "KZT", etc.
	DiscountTypeID int
	Items          []BonusSpendExtItem // optional per-item breakdown
}

// ─── CouponTranslate ──────────────────────────────────────────────────────────

// TranslatePromoCodeRequest is the input for TranslatePromoCode / RollbackPromoCode.
type TranslatePromoCodeRequest struct {
	StoreID    string
	OrderID    string // maps to cartcode
	Email      string
	PromoCode  string
	CardNum    string // optional loyalty card number
	CustomerID string // optional customer ID
}

// ─── CreateCertificate ────────────────────────────────────────────────────────

// CreateCertRequest is the input for CreateCertificate.
type CreateCertRequest struct {
	StoreID            string
	GoodIDD            string // product SKU for the certificate template
	CustomerPhone      string
	RecipientPhone     string
	RecipientName      string
	RecipientEmail     string
	CongratulationText string
	// RequestIdentifier is the idempotency key (UUID).
	// If empty, the client generates one via uuid.New().String().
	RequestIdentifier string
}

// CreateCertResult is the certificate returned by CreateCertificate.
type CreateCertResult struct {
	GoodIDD            string
	Number             string // EAN-13 certificate number
	CustomerPhone      string
	RecipientPhone     string
	RecipientName      string
	RecipientEmail     string
	CongratulationText string
}

// ─── ActivateCertificate ─────────────────────────────────────────────────────

// CertActivationItem is one certificate to activate.
type CertActivationItem struct {
	ID                 string
	Nominal            string // РУБЛИ, decimal verbatim ("500.00")
	PrepaidPromo       bool
	Phone              string
	CustomerPhone      string
	RecipientName      string
	RecipientEmail     string
	CongratulationText string
	Number             string // optional loyalty card binding
}

// ActivateCertRequest is the input for ActivateCertificate / RollbackCertificate.
type ActivateCertRequest struct {
	StoreID string
	DocID   string
	Certs   []CertActivationItem
}

// ActivatedCert is one certificate in an ActivateCertResult.
type ActivatedCert struct {
	ID                 string
	Nominal            string // РУБЛИ, decimal verbatim
	PrepaidPromo       bool
	Code               string
	Phone              string
	CustomerPhone      string
	RecipientName      string
	RecipientEmail     string
	CongratulationText string
	Token              string
}

// ActivateCertResult is returned by ActivateCertificate.
type ActivateCertResult struct {
	DocID  string
	Certs  []ActivatedCert
	Result int // 1=ok, 0=errors
}
```

- [ ] **Step 2: Write `xml.go`** — all internal XML structs + marshal/unmarshal functions

```go
package discount

import (
	"encoding/xml"
	"fmt"
	"strconv"
	"strings"
)

// ─── Shared base response detection ─────────────────────────────────────────

type xmlBaseResponse struct {
	XMLName xml.Name `xml:"Response"`
	Type    int      `xml:"Type,attr"`
	Word    string   `xml:"word,attr"`
}

type xmlErrorResponse struct {
	XMLName xml.Name     `xml:"Response"`
	Error   xmlErrorInfo `xml:"Error"`
}

type xmlErrorInfo struct {
	Description string `xml:"Description,attr"`
	Code        int    `xml:"Code,attr"`
	Name        string `xml:"Name,attr"`
}

// xmlSpendResponse covers the text-body responses for BonusSpend, BonusSpendExt,
// and CouponTranslate (all return <Response ...>textContent</Response>).
type xmlSpendResponse struct {
	XMLName xml.Name `xml:"Response"`
	Rezult  string   `xml:",chardata"`
}

// ─── GetDiscount ─────────────────────────────────────────────────────────────

type xmlGetDiscountGoodReq struct {
	XMLName  xml.Name `xml:"Good"`
	Text     string   `xml:",chardata"` // product ID
	Qty      int      `xml:"Qty,attr"`
	Price    string   `xml:"Price,attr"`
	SellOff  int      `xml:"SellOff,attr"`
	Discount string   `xml:"Discount,attr,omitempty"`
}

type xmlGetDiscountRequest struct {
	XMLName              xml.Name                 `xml:"http://discount.gloria-jeans.ru/Schema/4.8/GetDiscount Request"`
	Type                 int                      `xml:"Type,attr"`
	Version              string                   `xml:"version,attr"`
	Salt                 string                   `xml:"Salt,attr"`
	SaleForOnline        string                   `xml:"SaleForOnline,attr,omitempty"`
	SpecialCalculationID int                      `xml:"SpecialCalculationId,attr,omitempty"`
	Discount             string                   `xml:"Discount,omitempty"`
	Goods                []xmlGetDiscountGoodReq
}

type xmlDiscountValue struct {
	XMLName        xml.Name `xml:"Discount"`
	DiscountMetaID int      `xml:"DiscountMeta,attr"`
	DiscountType   int      `xml:"DiscountType,attr"`
	Val            string   `xml:"Val,attr"`
	NeedQuestion   int      `xml:"NeedQuestion,attr"`
	StoreVerified  int      `xml:"StoreVerified,attr"`
	Reason         string   `xml:"Reason,attr,omitempty"`
}

type xmlGetDiscountGoodResp struct {
	XMLName   xml.Name           `xml:"Good"`
	ID        string             `xml:"ID,attr"`
	Qty       int                `xml:"Qty,attr"`
	Discounts []xmlDiscountValue `xml:"Discount"`
}

type xmlDiscountMeta struct {
	XMLName      xml.Name `xml:"DiscountMeta"`
	ID           int      `xml:"ID,attr"`
	Description  string   `xml:"Description,attr"`
	QuestionText string   `xml:"QuestionText,attr,omitempty"`
	Callback     string   `xml:"Callback,attr,omitempty"`
	BonusPromo   bool     `xml:"BonusPromo,attr,omitempty"`
	DisplayName  string   `xml:"DisplayName,attr,omitempty"`
}

type xmlGetDiscountResponse struct {
	XMLName xml.Name                 `xml:"Response"`
	Goods   []xmlGetDiscountGoodResp `xml:"Good"`
	Metas   []xmlDiscountMeta        `xml:"DiscountMeta"`
}

func marshalGetDiscountRequest(req GetDiscountRequest, salt string) (string, error) {
	r := xmlGetDiscountRequest{
		Type:    1,
		Version: "4.8",
		Salt:    salt,
		Discount: req.DiscountID,
	}
	if req.SaleForOnline != nil {
		if *req.SaleForOnline {
			r.SaleForOnline = "true"
		} else {
			r.SaleForOnline = "false"
		}
	}
	if req.SpecialCalculationID != 0 {
		r.SpecialCalculationID = req.SpecialCalculationID
	}
	for _, item := range req.Items {
		r.Goods = append(r.Goods, xmlGetDiscountGoodReq{
			Text:     item.ProductID,
			Qty:      item.Qty,
			Price:    item.Price,
			SellOff:  item.SellOff,
			Discount: item.Discount,
		})
	}
	return encodeXML(r)
}

func unmarshalGetDiscountResponse(data []byte) (GetDiscountResponse, error) {
	var x xmlGetDiscountResponse
	if err := xml.Unmarshal(data, &x); err != nil {
		return GetDiscountResponse{}, fmt.Errorf("discount: unmarshal GetDiscount: %w", err)
	}
	resp := GetDiscountResponse{}
	for _, g := range x.Goods {
		good := GetDiscountGood{ID: g.ID, Qty: g.Qty}
		for _, d := range g.Discounts {
			good.Discounts = append(good.Discounts, DiscountValue{
				DiscountMetaID: d.DiscountMetaID,
				DiscountType:   d.DiscountType,
				Val:            d.Val,
				NeedQuestion:   d.NeedQuestion,
				StoreVerified:  d.StoreVerified,
				Reason:         d.Reason,
			})
		}
		resp.Goods = append(resp.Goods, good)
	}
	for _, m := range x.Metas {
		resp.Metas = append(resp.Metas, DiscountMeta{
			ID:           m.ID,
			Description:  m.Description,
			QuestionText: m.QuestionText,
			Callback:     m.Callback,
			BonusPromo:   m.BonusPromo,
			DisplayName:  m.DisplayName,
		})
	}
	return resp, nil
}

// ─── BonusSpend ──────────────────────────────────────────────────────────────

type xmlBonusSpendRequest struct {
	XMLName  xml.Name `xml:"http://discount.gloria-jeans.ru/Schema/4.1/BonusSpend Request"`
	Type     int      `xml:"Type,attr"`
	Salt     string   `xml:"Salt,attr"`
	Rollback int      `xml:"Rollback,attr"`
	Card     string   `xml:"Card"`
	DOC      string   `xml:"DOC"`
}

func marshalBonusSpendRequest(couponID, clientOrderID string, rollback bool, salt string) (string, error) {
	rb := 0
	if rollback {
		rb = 1
	}
	return encodeXML(xmlBonusSpendRequest{
		Type:     17,
		Salt:     salt,
		Rollback: rb,
		Card:     couponID,
		DOC:      DOCFromOrderID(clientOrderID),
	})
}

func unmarshalSpendResponse(data []byte) (SpendResult, error) {
	var x xmlSpendResponse
	if err := xml.Unmarshal(data, &x); err != nil {
		return SpendResult{}, fmt.Errorf("discount: unmarshal spend response: %w", err)
	}
	return classifyRezult(strings.TrimSpace(x.Rezult))
}

// ─── BonusSpendExt ───────────────────────────────────────────────────────────

type xmlBonusSpendExtGood struct {
	XMLName xml.Name `xml:"Good"`
	Text    string   `xml:",chardata"` // product ID
	Qty     int      `xml:"Qty,attr"`
	Summ    string   `xml:"Summ,attr"`
}

type xmlBonusSpendExtRequest struct {
	XMLName        xml.Name               `xml:"http://discount.gloria-jeans.ru/Schema/4.4/BonusSpendExt Request"`
	Type           int                    `xml:"Type,attr"`
	Version        string                 `xml:"version,attr"`
	Salt           string                 `xml:"Salt,attr"`
	Rollback       int                    `xml:"Rollback,attr"`
	Card           string                 `xml:"Card"`
	DOC            string                 `xml:"DOC"`
	Summ           string                 `xml:"Summ"`
	Currency       string                 `xml:"Currency"`
	TypeOfDiscount int                    `xml:"TypeOfDiscount"`
	Goods          []xmlBonusSpendExtGood `xml:"Good"`
}

func marshalBonusSpendExtRequest(req SpendBonusExtRequest, rollback bool, salt string) (string, error) {
	rb := 0
	if rollback {
		rb = 1
	}
	r := xmlBonusSpendExtRequest{
		Type:           21,
		Version:        "4.4",
		Salt:           salt,
		Rollback:       rb,
		Card:           req.LoyaltyCardID,
		DOC:            DOCFromOrderID(req.ClientOrderID),
		Summ:           req.Summ,
		Currency:       req.Currency,
		TypeOfDiscount: req.DiscountTypeID,
	}
	for _, item := range req.Items {
		r.Goods = append(r.Goods, xmlBonusSpendExtGood{
			Text: item.ProductID,
			Qty:  item.Qty,
			Summ: item.Summ,
		})
	}
	return encodeXML(r)
}

// ─── CouponTranslate ─────────────────────────────────────────────────────────

type xmlCouponTranslateRequest struct {
	XMLName    xml.Name `xml:"http://discount.gloria-jeans.ru/Schema/4.2/CuponTranslate Request"`
	Type       int      `xml:"Type,attr"`
	Version    string   `xml:"version,attr"`
	Salt       string   `xml:"Salt,attr"`
	Rollback   int      `xml:"Rollback,attr"`
	Promocode  string   `xml:"promocode"`
	Email      string   `xml:"email"`
	CartCode   string   `xml:"cartcode"`
	CardNum    string   `xml:"cardnum,omitempty"`
	CustomerID string   `xml:"CustomerId,omitempty"`
}

func marshalCouponTranslateRequest(req TranslatePromoCodeRequest, rollback bool, salt string) (string, error) {
	rb := 0
	if rollback {
		rb = 1
	}
	return encodeXML(xmlCouponTranslateRequest{
		Type:       30,
		Version:    "4.2",
		Salt:       salt,
		Rollback:   rb,
		Promocode:  req.PromoCode,
		Email:      req.Email,
		CartCode:   req.OrderID,
		CardNum:    req.CardNum,
		CustomerID: req.CustomerID,
	})
}

// unmarshalCouponTranslateResponse returns the EAN-13 coupon string.
// "1" means rollback succeeded; "0" means operation not performed.
func unmarshalCouponTranslateResponse(data []byte) (string, error) {
	var x xmlSpendResponse
	if err := xml.Unmarshal(data, &x); err != nil {
		return "", fmt.Errorf("discount: unmarshal CouponTranslate: %w", err)
	}
	return strings.TrimSpace(x.Rezult), nil
}

// ─── CreateCertificate ───────────────────────────────────────────────────────

type xmlCreateCertCert struct {
	GoodIDD            string `xml:"GoodIDD"`
	CustomerPhone      string `xml:"CustomerPhone,omitempty"`
	RecipientPhone     string `xml:"RecipientPhone,omitempty"`
	RecipientName      string `xml:"RecipientName,omitempty"`
	RecipientEmail     string `xml:"RecipientEmail,omitempty"`
	CongratulationText string `xml:"CongratulationText,omitempty"`
	Number             string `xml:"Number,omitempty"` // response only
}

type xmlCreateCertRequest struct {
	XMLName           xml.Name          `xml:"http://discount.gloria-jeans.ru/Schema/4.0/CreateCert Request"`
	Type              int               `xml:"Type,attr"`
	Salt              string            `xml:"Salt,attr"`
	RequestIdentifier string            `xml:"RequestIdentifier,attr"`
	Certificate       xmlCreateCertCert `xml:"Certificate"`
}

type xmlCreateCertResponse struct {
	XMLName     xml.Name          `xml:"Response"`
	Certificate xmlCreateCertCert `xml:"Certificate"`
}

func marshalCreateCertRequest(req CreateCertRequest, salt string) (string, error) {
	return encodeXML(xmlCreateCertRequest{
		Type:              16,
		Salt:              salt,
		RequestIdentifier: req.RequestIdentifier,
		Certificate: xmlCreateCertCert{
			GoodIDD:            req.GoodIDD,
			CustomerPhone:      req.CustomerPhone,
			RecipientPhone:     req.RecipientPhone,
			RecipientName:      req.RecipientName,
			RecipientEmail:     req.RecipientEmail,
			CongratulationText: req.CongratulationText,
		},
	})
}

func unmarshalCreateCertResponse(data []byte) (CreateCertResult, error) {
	var x xmlCreateCertResponse
	if err := xml.Unmarshal(data, &x); err != nil {
		return CreateCertResult{}, fmt.Errorf("discount: unmarshal CreateCert: %w", err)
	}
	return CreateCertResult{
		GoodIDD:            x.Certificate.GoodIDD,
		Number:             x.Certificate.Number,
		CustomerPhone:      x.Certificate.CustomerPhone,
		RecipientPhone:     x.Certificate.RecipientPhone,
		RecipientName:      x.Certificate.RecipientName,
		RecipientEmail:     x.Certificate.RecipientEmail,
		CongratulationText: x.Certificate.CongratulationText,
	}, nil
}

// ─── ActivateCertificate ─────────────────────────────────────────────────────

type xmlActivateCertItem struct {
	XMLName            xml.Name `xml:"Certificate"`
	ID                 string   `xml:"ID,attr"`
	Nominal            string   `xml:"Nominal,attr"`
	PrepaidPromo       bool     `xml:"PrepaidPromo,attr"`
	Phone              string   `xml:"Phone,attr,omitempty"`
	CustomerPhone      string   `xml:"CustomerPhone,attr,omitempty"`
	RecipientName      string   `xml:"RecipientName,attr,omitempty"`
	RecipientEmail     string   `xml:"RecipientEmail,attr,omitempty"`
	Number             string   `xml:"Number,attr,omitempty"`
	CongratulationText string   `xml:"CongratulationText,omitempty"`
}

type xmlActivateCertRequest struct {
	XMLName      xml.Name              `xml:"http://discount.gloria-jeans.ru/Schema/4.3/ActivateCert Request"`
	Type         int                   `xml:"Type,attr"`
	Salt         string                `xml:"Salt,attr"`
	DocID        string                `xml:"DocId,attr"`
	Rollback     int                   `xml:"Rollback,attr"`
	Certificates []xmlActivateCertItem `xml:"Certificate"`
}

type xmlActivatedCert struct {
	XMLName            xml.Name `xml:"Certificate"`
	ID                 string   `xml:"ID,attr"`
	Nominal            string   `xml:"Nominal,attr"`
	PrepaidPromo       bool     `xml:"PrepaidPromo,attr"`
	Code               string   `xml:"Code,attr,omitempty"`
	Phone              string   `xml:"Phone,attr,omitempty"`
	CustomerPhone      string   `xml:"CustomerPhone,attr,omitempty"`
	RecipientName      string   `xml:"RecipientName,attr,omitempty"`
	RecipientEmail     string   `xml:"RecipientEmail,attr,omitempty"`
	CongratulationText string   `xml:"CongratulationText,omitempty"`
	Token              string   `xml:"Token,omitempty"`
}

type xmlActivateCertResponse struct {
	XMLName  xml.Name           `xml:"Response"`
	DocID    string             `xml:"DocId,attr"`
	CertList []xmlActivatedCert `xml:"CertList>Certificate"`
	Rezult   int                `xml:"Rezult"`
}

func marshalActivateCertRequest(req ActivateCertRequest, rollback bool, salt string) (string, error) {
	rb := 0
	if rollback {
		rb = 1
	}
	r := xmlActivateCertRequest{
		Type:     15,
		Salt:     salt,
		DocID:    req.DocID,
		Rollback: rb,
	}
	for _, c := range req.Certs {
		r.Certificates = append(r.Certificates, xmlActivateCertItem{
			ID:                 c.ID,
			Nominal:            c.Nominal,
			PrepaidPromo:       c.PrepaidPromo,
			Phone:              c.Phone,
			CustomerPhone:      c.CustomerPhone,
			RecipientName:      c.RecipientName,
			RecipientEmail:     c.RecipientEmail,
			Number:             c.Number,
			CongratulationText: c.CongratulationText,
		})
	}
	return encodeXML(r)
}

func unmarshalActivateCertResponse(data []byte) (ActivateCertResult, error) {
	var x xmlActivateCertResponse
	if err := xml.Unmarshal(data, &x); err != nil {
		return ActivateCertResult{}, fmt.Errorf("discount: unmarshal ActivateCert: %w", err)
	}
	res := ActivateCertResult{DocID: x.DocID, Result: x.Rezult}
	for _, c := range x.CertList {
		res.Certs = append(res.Certs, ActivatedCert{
			ID:                 c.ID,
			Nominal:            c.Nominal,
			PrepaidPromo:       c.PrepaidPromo,
			Code:               c.Code,
			Phone:              c.Phone,
			CustomerPhone:      c.CustomerPhone,
			RecipientName:      c.RecipientName,
			RecipientEmail:     c.RecipientEmail,
			CongratulationText: c.CongratulationText,
			Token:              c.Token,
		})
	}
	return res, nil
}

// ─── helpers ─────────────────────────────────────────────────────────────────

// encodeXML marshals v to an XML string using encoding/xml.
// Does NOT prepend the XML declaration.
func encodeXML(v any) (string, error) {
	b, err := xml.Marshal(v)
	if err != nil {
		return "", err
	}
	return string(b), nil
}

// resolveStoreID returns the per-request storeID if non-empty,
// else falls back to the client-level default.
func resolveStoreID(defaultID, perRequestID string) string {
	if perRequestID != "" {
		return perRequestID
	}
	return defaultID
}

// Ensure strconv is used (for future numeric conversions by consumers).
var _ = strconv.Itoa
```

> Note: the unused `strconv` import will be removed by `go mod tidy` / `goimports`. Remove it if `go build` complains, or omit the blank identifier usage.

- [ ] **Step 3: Build**

```bash
go build ./...
```

Expected: exits 0.

- [ ] **Step 4: Commit**

```bash
git add types.go xml.go
git commit -m "feat(discount-client): public types + XML marshal/unmarshal"
```

---

## Task 6: Core Client + Word-Rotation Tests

**Files:**
- Create: `platform-new/clients/discount/client.go`
- Create: `platform-new/clients/discount/client_test.go`
- Create: `platform-new/clients/discount/testdata/error_resp.xml`
- Create: `platform-new/clients/discount/testdata/word_rotation_resp.xml`

- [ ] **Step 1: Write the fixture files**

`testdata/error_resp.xml`:
```xml
<Response Type="5" version="4.0"><Error Description="Ошибка авторизации" Code="5" Name="NotAllowed"/></Response>
```

`testdata/word_rotation_resp.xml`:
```xml
<Response Type="6" version="4.0" word="newSecret123"/>
```

- [ ] **Step 2: Write failing tests in `client_test.go`**

```go
package discount

import (
	"context"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
)

// ─── helpers ─────────────────────────────────────────────────────────────────

func newTestClient(t *testing.T, handler http.Handler) *Client {
	t.Helper()
	srv := httptest.NewServer(handler)
	t.Cleanup(srv.Close)
	c, err := New(Config{
		BaseURL:  srv.URL,
		StoreID:  "9999999",
		WordStore: NewInMemoryWordStore("secret"),
	})
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return c
}

func fixture(t *testing.T, name string) []byte {
	t.Helper()
	b, err := os.ReadFile(filepath.Join("testdata", name))
	if err != nil {
		t.Fatalf("fixture %q: %v", name, err)
	}
	return b
}

func staticHandler(body []byte) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/xml; charset=utf-8")
		w.Write(body)
	})
}

// ─── core client tests ───────────────────────────────────────────────────────

func TestXmlDo_ServerError(t *testing.T) {
	c := newTestClient(t, staticHandler(fixture(t, "error_resp.xml")))
	_, err := c.xmlDo(context.Background(), "test_op", "9999999",
		func(salt string) (string, error) {
			return "<Request><dummy/></Request>", nil
		},
	)
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	var sErr *ServerError
	if !errors.As(err, &sErr) {
		t.Fatalf("expected *ServerError, got %T: %v", err, err)
	}
	if sErr.Code != 5 || sErr.Name != "NotAllowed" {
		t.Errorf("unexpected ServerError: %+v", sErr)
	}
}

func TestXmlDo_WordRotation_RetryOnce(t *testing.T) {
	var callCount atomic.Int32
	rotResp := fixture(t, "word_rotation_resp.xml")
	// second call must succeed; we use a simple text response
	// (xmlDo returns raw bytes for non-5/non-6 responses)
	successResp := []byte(`<Response Type="17" version="4.1">ok</Response>`)

	c := newTestClient(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n := callCount.Add(1)
		w.Header().Set("Content-Type", "text/xml; charset=utf-8")
		if n == 1 {
			w.Write(rotResp)
		} else {
			w.Write(successResp)
		}
	}))

	raw, err := c.xmlDo(context.Background(), "test_op", "9999999",
		func(salt string) (string, error) { return "<Request><dummy/></Request>", nil },
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !strings.Contains(string(raw), "ok") {
		t.Errorf("unexpected response body: %s", raw)
	}
	if n := callCount.Load(); n != 2 {
		t.Errorf("expected 2 HTTP calls, got %d", n)
	}
	// word must have been updated
	w, _ := c.config.WordStore.Word()
	if w != "newSecret123" {
		t.Errorf("word not updated: %q", w)
	}
}

func TestXmlDo_WordRotation_NoDoubleRetry(t *testing.T) {
	var callCount atomic.Int32
	rotResp := fixture(t, "word_rotation_resp.xml")

	c := newTestClient(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callCount.Add(1)
		w.Header().Set("Content-Type", "text/xml; charset=utf-8")
		w.Write(rotResp) // always return Type=6
	}))

	_, err := c.xmlDo(context.Background(), "test_op", "9999999",
		func(salt string) (string, error) { return "<Request><dummy/></Request>", nil },
	)
	if err == nil {
		t.Fatal("expected error on double word rotation, got nil")
	}
	if n := callCount.Load(); n != 2 {
		t.Errorf("expected exactly 2 HTTP calls (no third retry), got %d", n)
	}
}

func TestXmlDo_RequestContentType(t *testing.T) {
	var gotCT string
	c := newTestClient(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotCT = r.Header.Get("Content-Type")
		w.Header().Set("Content-Type", "text/xml; charset=utf-8")
		io.WriteString(w, `<Response Type="1" version="4.8"></Response>`)
	}))

	c.xmlDo(context.Background(), "test_op", "9999999",
		func(salt string) (string, error) { return "<Request><dummy/></Request>", nil },
	)
	if gotCT != "application/gjdk" {
		t.Errorf("Content-Type: got %q, want %q", gotCT, "application/gjdk")
	}
}

func TestXmlDo_QueryParams(t *testing.T) {
	var gotQuery string
	c := newTestClient(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotQuery = r.URL.RawQuery
		w.Header().Set("Content-Type", "text/xml")
		io.WriteString(w, `<Response Type="1" version="4.8"></Response>`)
	}))

	c.xmlDo(context.Background(), "test_op", "9999999",
		func(salt string) (string, error) { return "<Request><dummy/></Request>", nil },
	)
	if !strings.Contains(gotQuery, "idStore=9999999") {
		t.Errorf("query missing idStore: %q", gotQuery)
	}
	if !strings.Contains(gotQuery, "CheckSum=") {
		t.Errorf("query missing CheckSum: %q", gotQuery)
	}
}
```

- [ ] **Step 3: Run → expect FAIL**

```bash
go test ./... -run "TestXmlDo" -v
```

Expected: FAIL — `New`, `Client`, `xmlDo` undefined.

- [ ] **Step 4: Write `client.go`**

```go
package discount

import (
	"context"
	"encoding/xml"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"

	httpclient "gitlab.gloria.aaanet.ru/go-pkg/gj-go-httpclient"
)

// Config holds the configuration for a Client.
type Config struct {
	BaseURL   string    // scheme+host, no trailing slash (e.g. "http://discount.example.com")
	StoreID   string    // default store ID; per-request fields can override
	WordStore WordStore // must be non-nil
}

// Client sends requests to the WWWDKMVC discount server.
type Client struct {
	hc     *httpclient.Client
	config Config
}

// New creates a Client. Returns error if config.WordStore is nil or BaseURL is empty.
func New(cfg Config, opts ...httpclient.Option) (*Client, error) {
	if cfg.BaseURL == "" {
		return nil, fmt.Errorf("discount: Config.BaseURL is required")
	}
	if cfg.WordStore == nil {
		return nil, fmt.Errorf("discount: Config.WordStore is required")
	}
	cfg.BaseURL = strings.TrimRight(cfg.BaseURL, "/")
	hc := httpclient.New("discount", cfg.BaseURL, opts...)
	return &Client{hc: hc, config: cfg}, nil
}

// xmlBodyFn builds the XML request body for the given salt.
type xmlBodyFn func(salt string) (string, error)

// xmlDo authenticates and sends one request. On Type=6 response it rotates the
// word and retries exactly once. Returns raw response bytes (Type != 5 and != 6).
func (c *Client) xmlDo(ctx context.Context, op, storeID string, buildFn xmlBodyFn) ([]byte, error) {
	return c.xmlDoInternal(ctx, op, storeID, buildFn, false)
}

func (c *Client) xmlDoInternal(ctx context.Context, op, storeID string, buildFn xmlBodyFn, wasRetried bool) ([]byte, error) {
	word, err := c.config.WordStore.Word()
	if err != nil {
		return nil, fmt.Errorf("discount: %s: word store: %w", op, err)
	}
	salt := newSalt()
	cs := checksum(storeID, word, salt)

	body, err := buildFn(salt)
	if err != nil {
		return nil, fmt.Errorf("discount: %s: build body: %w", op, err)
	}

	rawURL := c.config.BaseURL + "/api/Query?" +
		url.Values{"idStore": {storeID}, "CheckSum": {cs}}.Encode()

	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, rawURL, strings.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("discount: %s: new request: %w", op, err)
	}
	httpReq.Header.Set("Content-Type", "application/gjdk")

	resp, err := c.hc.Do(ctx, op, httpReq)
	if err != nil {
		return nil, err // already wrapped by httpclient
	}
	defer resp.Body.Close()

	rawBytes, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20)) // 1 MiB cap
	if err != nil {
		return nil, fmt.Errorf("discount: %s: read body: %w", op, err)
	}

	decoded, decErr := decodeCharset(resp.Header.Get("Content-Type"), rawBytes)
	if decErr != nil {
		decoded = rawBytes // fall back to raw
	}

	// Peek at the Response Type to decide routing.
	var base xmlBaseResponse
	if err := xml.Unmarshal(decoded, &base); err != nil {
		return nil, fmt.Errorf("discount: %s: parse response type: %w", op, err)
	}

	switch base.Type {
	case 6: // word rotation — update and retry once
		if wasRetried {
			return nil, &ServerError{
				Code:        -1,
				Description: "word rotation loop: server returned Type=6 twice",
				Name:        "WordRotationLoop",
			}
		}
		if base.Word == "" {
			return nil, &ServerError{
				Code:        -1,
				Description: "server returned Type=6 without new word",
				Name:        "MissingWord",
			}
		}
		if err := c.config.WordStore.SetWord(base.Word); err != nil {
			return nil, fmt.Errorf("discount: %s: update word: %w", op, err)
		}
		return c.xmlDoInternal(ctx, op, storeID, buildFn, true)

	case 5: // explicit server error
		var errResp xmlErrorResponse
		xml.Unmarshal(decoded, &errResp) //nolint:errcheck
		return nil, &ServerError{
			Code:        errResp.Error.Code,
			Description: errResp.Error.Description,
			Name:        errResp.Error.Name,
		}

	default:
		return decoded, nil
	}
}
```

- [ ] **Step 5: Run → expect PASS**

```bash
go test ./... -run "TestXmlDo" -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add client.go client_test.go testdata/error_resp.xml testdata/word_rotation_resp.xml
git commit -m "feat(discount-client): core Client + xmlDo + word-rotation tests"
```

---

## Task 7: GetDiscount API Method

**Files:**
- Create: `platform-new/clients/discount/api.go` (initial)
- Create: `platform-new/clients/discount/testdata/get_discount_resp.xml`
- Modify: `platform-new/clients/discount/client_test.go`

- [ ] **Step 1: Write fixture `testdata/get_discount_resp.xml`**

```xml
<Response Type="1" version="4.8">
  <Good ID="SKU001" Qty="2">
    <Discount DiscountMeta="42" DiscountType="1" Val="20.0" NeedQuestion="0" StoreVerified="0"/>
  </Good>
  <Good ID="SKU002" Qty="1">
    <Discount DiscountMeta="42" DiscountType="2" Val="50.00" NeedQuestion="0" StoreVerified="0"/>
  </Good>
  <DiscountMeta ID="42" Description="Акция 20%" Callback="http://discount.gloria-jeans.ru/Schema/4.1/BonusSpend" BonusPromo="true" DisplayName="Скидка онлайн"/>
</Response>
```

- [ ] **Step 2: Add tests to `client_test.go`**

```go
func TestGetDiscount_Happy(t *testing.T) {
	c := newTestClient(t, staticHandler(fixture(t, "get_discount_resp.xml")))

	resp, err := c.GetDiscount(context.Background(), GetDiscountRequest{
		Items: []GetDiscountItem{
			{ProductID: "SKU001", Qty: 2, Price: "1299.00", SellOff: 0},
			{ProductID: "SKU002", Qty: 1, Price: "599.00", SellOff: 0},
		},
	})
	if err != nil {
		t.Fatalf("GetDiscount: %v", err)
	}
	if len(resp.Goods) != 2 {
		t.Fatalf("expected 2 goods, got %d", len(resp.Goods))
	}
	if resp.Goods[0].ID != "SKU001" {
		t.Errorf("Goods[0].ID = %q, want SKU001", resp.Goods[0].ID)
	}
	if len(resp.Goods[0].Discounts) != 1 {
		t.Fatalf("expected 1 discount on SKU001, got %d", len(resp.Goods[0].Discounts))
	}
	d := resp.Goods[0].Discounts[0]
	if d.DiscountMetaID != 42 || d.DiscountType != 1 || d.Val != "20.0" {
		t.Errorf("unexpected discount: %+v", d)
	}
	// SKU002 has absolute discount (DiscountType=2, РУБЛИ)
	if resp.Goods[1].Discounts[0].DiscountType != 2 || resp.Goods[1].Discounts[0].Val != "50.00" {
		t.Errorf("SKU002 discount: %+v", resp.Goods[1].Discounts[0])
	}
	if len(resp.Metas) != 1 || resp.Metas[0].ID != 42 {
		t.Errorf("unexpected metas: %+v", resp.Metas)
	}
	if !resp.Metas[0].BonusPromo {
		t.Error("expected BonusPromo=true")
	}
}

func TestGetDiscount_StoreIDOverride(t *testing.T) {
	var gotStoreID string
	c := newTestClient(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotStoreID = r.URL.Query().Get("idStore")
		w.Header().Set("Content-Type", "text/xml")
		io.WriteString(w, `<Response Type="1" version="4.8"></Response>`)
	}))

	c.GetDiscount(context.Background(), GetDiscountRequest{
		StoreID: "1111111",
		Items:   []GetDiscountItem{{ProductID: "X", Qty: 1, Price: "100.00"}},
	})
	if gotStoreID != "1111111" {
		t.Errorf("idStore = %q, want 1111111", gotStoreID)
	}
}

func TestGetDiscount_EmptyResponse(t *testing.T) {
	// Server returns empty <Response> (no discounts) — must not error
	c := newTestClient(t, staticHandler([]byte(`<Response Type="1" version="4.8"></Response>`)))
	resp, err := c.GetDiscount(context.Background(), GetDiscountRequest{
		Items: []GetDiscountItem{{ProductID: "X", Qty: 1, Price: "100.00"}},
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(resp.Goods) != 0 || len(resp.Metas) != 0 {
		t.Errorf("expected empty response, got %+v", resp)
	}
}
```

- [ ] **Step 3: Run → expect FAIL**

```bash
go test ./... -run TestGetDiscount -v
```

Expected: FAIL — `GetDiscount` undefined.

- [ ] **Step 4: Write `api.go`** (GetDiscount only for now)

```go
package discount

import "context"

// GetDiscount returns the advisory discount calculation for the basket.
// This is a stateless quote — it commits nothing.
func (c *Client) GetDiscount(ctx context.Context, req GetDiscountRequest) (GetDiscountResponse, error) {
	storeID := resolveStoreID(c.config.StoreID, req.StoreID)
	raw, err := c.xmlDo(ctx, "get_discount", storeID, func(salt string) (string, error) {
		return marshalGetDiscountRequest(req, salt)
	})
	if err != nil {
		return GetDiscountResponse{}, err
	}
	return unmarshalGetDiscountResponse(raw)
}
```

- [ ] **Step 5: Run → expect PASS**

```bash
go test ./... -run TestGetDiscount -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add api.go testdata/get_discount_resp.xml
git commit -m "feat(discount-client): GetDiscount + tests"
```

---

## Task 8: BonusSpend (Coupon)

**Files:**
- Create: `testdata/bonus_spend_resp.xml`, `testdata/bonus_spend_resp_dup.xml`, `testdata/bonus_spend_resp_fail.xml`
- Modify: `api.go`, `client_test.go`

- [ ] **Step 1: Write fixtures**

`testdata/bonus_spend_resp.xml`:
```xml
<Response Type="17" version="4.1">ok</Response>
```

`testdata/bonus_spend_resp_dup.xml`:
```xml
<Response Type="17" version="4.1">BonusSpendExt_IsSubmitted</Response>
```

`testdata/bonus_spend_resp_fail.xml`:
```xml
<Response Type="17" version="4.1">BonusSpendExt_NoBonusQty</Response>
```

- [ ] **Step 2: Add tests**

```go
func TestSpendCoupon_Happy(t *testing.T) {
	c := newTestClient(t, staticHandler(fixture(t, "bonus_spend_resp.xml")))
	result, err := c.SpendCoupon(context.Background(), SpendCouponRequest{
		CouponID: "2000123456789", ClientOrderID: "ORD-001",
	})
	if err != nil {
		t.Fatalf("SpendCoupon: %v", err)
	}
	if result.Raw != "ok" || result.Idempotent {
		t.Errorf("unexpected result: %+v", result)
	}
}

func TestSpendCoupon_Duplicate(t *testing.T) {
	c := newTestClient(t, staticHandler(fixture(t, "bonus_spend_resp_dup.xml")))
	result, err := c.SpendCoupon(context.Background(), SpendCouponRequest{
		CouponID: "2000123456789", ClientOrderID: "ORD-001",
	})
	if err != nil {
		t.Fatalf("SpendCoupon duplicate: %v", err)
	}
	if !result.Idempotent {
		t.Error("expected Idempotent=true for IsSubmitted response")
	}
}

func TestSpendCoupon_Fail(t *testing.T) {
	c := newTestClient(t, staticHandler(fixture(t, "bonus_spend_resp_fail.xml")))
	_, err := c.SpendCoupon(context.Background(), SpendCouponRequest{
		CouponID: "2000123456789", ClientOrderID: "ORD-001",
	})
	var spendErr *SpendError
	if !errors.As(err, &spendErr) {
		t.Fatalf("expected *SpendError, got %T: %v", err, err)
	}
	if spendErr.Rezult != "BonusSpendExt_NoBonusQty" {
		t.Errorf("Rezult = %q", spendErr.Rezult)
	}
}

func TestReturnCoupon_Happy(t *testing.T) {
	var gotBody string
	c := newTestClient(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		b, _ := io.ReadAll(r.Body)
		gotBody = string(b)
		w.Header().Set("Content-Type", "text/xml")
		io.WriteString(w, `<Response Type="17" version="4.1">ok</Response>`)
	}))

	_, err := c.ReturnCoupon(context.Background(), SpendCouponRequest{
		CouponID: "2000123456789", ClientOrderID: "ORD-001",
	})
	if err != nil {
		t.Fatalf("ReturnCoupon: %v", err)
	}
	if !strings.Contains(gotBody, `Rollback="1"`) {
		t.Errorf("expected Rollback=1 in request body, got:\n%s", gotBody)
	}
	if !strings.Contains(gotBody, "0000352ORD-001") {
		t.Errorf("expected DOC=0000352ORD-001 in body, got:\n%s", gotBody)
	}
}
```

- [ ] **Step 3: Run → expect FAIL**

```bash
go test ./... -run "TestSpendCoupon|TestReturnCoupon" -v
```

- [ ] **Step 4: Add `SpendCoupon` and `ReturnCoupon` to `api.go`**

```go
// SpendCoupon activates (spends) a coupon. Idempotent by DOC.
func (c *Client) SpendCoupon(ctx context.Context, req SpendCouponRequest) (SpendResult, error) {
	storeID := resolveStoreID(c.config.StoreID, req.StoreID)
	raw, err := c.xmlDo(ctx, "spend_coupon", storeID, func(salt string) (string, error) {
		return marshalBonusSpendRequest(req.CouponID, req.ClientOrderID, false, salt)
	})
	if err != nil {
		return SpendResult{}, err
	}
	return unmarshalSpendResponse(raw)
}

// ReturnCoupon rolls back a coupon spend. Idempotent by DOC.
func (c *Client) ReturnCoupon(ctx context.Context, req SpendCouponRequest) (SpendResult, error) {
	storeID := resolveStoreID(c.config.StoreID, req.StoreID)
	raw, err := c.xmlDo(ctx, "return_coupon", storeID, func(salt string) (string, error) {
		return marshalBonusSpendRequest(req.CouponID, req.ClientOrderID, true, salt)
	})
	if err != nil {
		return SpendResult{}, err
	}
	return unmarshalSpendResponse(raw)
}
```

- [ ] **Step 5: Run → expect PASS**

```bash
go test ./... -run "TestSpendCoupon|TestReturnCoupon" -v
```

- [ ] **Step 6: Commit**

```bash
git add api.go testdata/bonus_spend_resp*.xml
git commit -m "feat(discount-client): SpendCoupon / ReturnCoupon + tests"
```

---

## Task 9: BonusSpendExt (Loyalty Points)

**Files:**
- Create: `testdata/bonus_spend_ext_resp.xml`, `testdata/bonus_spend_ext_resp_cancelled.xml`
- Modify: `api.go`, `client_test.go`

- [ ] **Step 1: Write fixtures**

`testdata/bonus_spend_ext_resp.xml`:
```xml
<Response Type="21" version="4.4">ok</Response>
```

`testdata/bonus_spend_ext_resp_cancelled.xml`:
```xml
<Response Type="21" version="4.4">BonusSpendExt_OparationCancelled</Response>
```

- [ ] **Step 2: Add tests**

```go
func TestSpendBonusExt_Happy(t *testing.T) {
	c := newTestClient(t, staticHandler(fixture(t, "bonus_spend_ext_resp.xml")))
	result, err := c.SpendBonusExt(context.Background(), SpendBonusExtRequest{
		LoyaltyCardID: "1234567890", ClientOrderID: "ORD-002",
		Summ: "500.00", Currency: "RUB", DiscountTypeID: 42,
	})
	if err != nil {
		t.Fatalf("SpendBonusExt: %v", err)
	}
	if result.Idempotent || result.Raw != "ok" {
		t.Errorf("unexpected result: %+v", result)
	}
}

func TestReturnBonusExt_OparationCancelled(t *testing.T) {
	c := newTestClient(t, staticHandler(fixture(t, "bonus_spend_ext_resp_cancelled.xml")))
	result, err := c.ReturnBonusExt(context.Background(), SpendBonusExtRequest{
		LoyaltyCardID: "1234567890", ClientOrderID: "ORD-002",
		Summ: "500.00", Currency: "RUB", DiscountTypeID: 42,
	})
	if err != nil {
		t.Fatalf("ReturnBonusExt: %v", err)
	}
	if !result.Idempotent {
		t.Error("expected Idempotent=true for OparationCancelled")
	}
}

func TestSpendBonusExt_WithItems(t *testing.T) {
	var gotBody string
	c := newTestClient(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		b, _ := io.ReadAll(r.Body)
		gotBody = string(b)
		w.Header().Set("Content-Type", "text/xml")
		io.WriteString(w, `<Response Type="21" version="4.4">ok</Response>`)
	}))

	c.SpendBonusExt(context.Background(), SpendBonusExtRequest{
		LoyaltyCardID: "1234567890", ClientOrderID: "ORD-003",
		Summ: "500.00", Currency: "RUB", DiscountTypeID: 42,
		Items: []BonusSpendExtItem{
			{ProductID: "SKU001", Qty: 1, Summ: "250.00"},
			{ProductID: "SKU002", Qty: 1, Summ: "250.00"},
		},
	})
	if !strings.Contains(gotBody, "SKU001") || !strings.Contains(gotBody, "SKU002") {
		t.Errorf("expected Good items in body, got:\n%s", gotBody)
	}
	if !strings.Contains(gotBody, `Summ="250.00"`) {
		t.Errorf("expected Summ attr in Good items, got:\n%s", gotBody)
	}
}
```

- [ ] **Step 3: Run → expect FAIL**

```bash
go test ./... -run "TestSpendBonusExt|TestReturnBonusExt" -v
```

- [ ] **Step 4: Add to `api.go`**

```go
// SpendBonusExt spends loyalty bonus points. Idempotent by DOC.
func (c *Client) SpendBonusExt(ctx context.Context, req SpendBonusExtRequest) (SpendResult, error) {
	storeID := resolveStoreID(c.config.StoreID, req.StoreID)
	raw, err := c.xmlDo(ctx, "spend_bonus_ext", storeID, func(salt string) (string, error) {
		return marshalBonusSpendExtRequest(req, false, salt)
	})
	if err != nil {
		return SpendResult{}, err
	}
	return unmarshalSpendResponse(raw)
}

// ReturnBonusExt rolls back a loyalty bonus spend. Idempotent by DOC.
func (c *Client) ReturnBonusExt(ctx context.Context, req SpendBonusExtRequest) (SpendResult, error) {
	storeID := resolveStoreID(c.config.StoreID, req.StoreID)
	raw, err := c.xmlDo(ctx, "return_bonus_ext", storeID, func(salt string) (string, error) {
		return marshalBonusSpendExtRequest(req, true, salt)
	})
	if err != nil {
		return SpendResult{}, err
	}
	return unmarshalSpendResponse(raw)
}
```

- [ ] **Step 5: Run → expect PASS**

```bash
go test ./... -run "TestSpendBonusExt|TestReturnBonusExt" -v
```

- [ ] **Step 6: Commit**

```bash
git add api.go testdata/bonus_spend_ext_resp*.xml
git commit -m "feat(discount-client): SpendBonusExt / ReturnBonusExt + tests"
```

---

## Task 10: CouponTranslate (Promo Code)

**Files:**
- Create: `testdata/coupon_translate_resp.xml`, `testdata/coupon_translate_rollback_resp.xml`
- Modify: `api.go`, `client_test.go`

- [ ] **Step 1: Write fixtures**

`testdata/coupon_translate_resp.xml`:
```xml
<Response Type="30" version="4.2">2000123456789</Response>
```

`testdata/coupon_translate_rollback_resp.xml`:
```xml
<Response Type="30" version="4.2">1</Response>
```

- [ ] **Step 2: Add tests**

```go
func TestTranslatePromoCode_Happy(t *testing.T) {
	c := newTestClient(t, staticHandler(fixture(t, "coupon_translate_resp.xml")))
	ean, err := c.TranslatePromoCode(context.Background(), TranslatePromoCodeRequest{
		OrderID: "CART-001", Email: "user@example.com", PromoCode: "PROMO2024",
	})
	if err != nil {
		t.Fatalf("TranslatePromoCode: %v", err)
	}
	if ean != "2000123456789" {
		t.Errorf("got %q, want 2000123456789", ean)
	}
}

func TestRollbackPromoCode_Happy(t *testing.T) {
	c := newTestClient(t, staticHandler(fixture(t, "coupon_translate_rollback_resp.xml")))
	if err := c.RollbackPromoCode(context.Background(), TranslatePromoCodeRequest{
		OrderID: "CART-001", Email: "user@example.com", PromoCode: "PROMO2024",
	}); err != nil {
		t.Fatalf("RollbackPromoCode: %v", err)
	}
}

func TestTranslatePromoCode_ServerError(t *testing.T) {
	c := newTestClient(t, staticHandler(fixture(t, "error_resp.xml")))
	_, err := c.TranslatePromoCode(context.Background(), TranslatePromoCodeRequest{
		OrderID: "CART-001", Email: "user@example.com", PromoCode: "BAD",
	})
	var sErr *ServerError
	if !errors.As(err, &sErr) {
		t.Fatalf("expected *ServerError, got %T: %v", err, err)
	}
}

func TestTranslatePromoCode_OptionalFields(t *testing.T) {
	var gotBody string
	c := newTestClient(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		b, _ := io.ReadAll(r.Body)
		gotBody = string(b)
		w.Header().Set("Content-Type", "text/xml")
		io.WriteString(w, `<Response Type="30" version="4.2">2000111222333</Response>`)
	}))

	c.TranslatePromoCode(context.Background(), TranslatePromoCodeRequest{
		OrderID:    "CART-001",
		Email:      "user@example.com",
		PromoCode:  "PROMO",
		CardNum:    "CARD123",
		CustomerID: "CUST456",
	})
	if !strings.Contains(gotBody, "CARD123") {
		t.Errorf("expected cardnum in body, got:\n%s", gotBody)
	}
	if !strings.Contains(gotBody, "CUST456") {
		t.Errorf("expected CustomerId in body, got:\n%s", gotBody)
	}
}
```

- [ ] **Step 3: Run → expect FAIL**

```bash
go test ./... -run "TestTranslatePromoCode|TestRollbackPromoCode" -v
```

- [ ] **Step 4: Add to `api.go`**

```go
// TranslatePromoCode resolves a human-readable promo code to a coupon EAN-13.
// Idempotent by cartCode + email on the server side.
func (c *Client) TranslatePromoCode(ctx context.Context, req TranslatePromoCodeRequest) (string, error) {
	storeID := resolveStoreID(c.config.StoreID, req.StoreID)
	raw, err := c.xmlDo(ctx, "translate_promo_code", storeID, func(salt string) (string, error) {
		return marshalCouponTranslateRequest(req, false, salt)
	})
	if err != nil {
		return "", err
	}
	return unmarshalCouponTranslateResponse(raw)
}

// RollbackPromoCode reverses a promo code translation.
func (c *Client) RollbackPromoCode(ctx context.Context, req TranslatePromoCodeRequest) error {
	storeID := resolveStoreID(c.config.StoreID, req.StoreID)
	_, err := c.xmlDo(ctx, "rollback_promo_code", storeID, func(salt string) (string, error) {
		return marshalCouponTranslateRequest(req, true, salt)
	})
	return err
}
```

- [ ] **Step 5: Run → expect PASS**

```bash
go test ./... -run "TestTranslatePromoCode|TestRollbackPromoCode" -v
```

- [ ] **Step 6: Commit**

```bash
git add api.go testdata/coupon_translate_resp.xml testdata/coupon_translate_rollback_resp.xml
git commit -m "feat(discount-client): TranslatePromoCode / RollbackPromoCode + tests"
```

---

## Task 11: CreateCertificate

**Files:**
- Create: `testdata/create_cert_resp.xml`
- Modify: `api.go`, `client_test.go`

- [ ] **Step 1: Write fixture `testdata/create_cert_resp.xml`**

```xml
<Response Type="16" version="4.0">
  <Certificate>
    <GoodIDD>CERT-SKU-500</GoodIDD>
    <Number>4600000500012</Number>
    <CustomerPhone>+79001234567</CustomerPhone>
    <RecipientName>Иван</RecipientName>
    <RecipientEmail>ivan@example.com</RecipientEmail>
  </Certificate>
</Response>
```

- [ ] **Step 2: Add tests**

```go
func TestCreateCertificate_Happy(t *testing.T) {
	c := newTestClient(t, staticHandler(fixture(t, "create_cert_resp.xml")))
	result, err := c.CreateCertificate(context.Background(), CreateCertRequest{
		GoodIDD:           "CERT-SKU-500",
		CustomerPhone:     "+79001234567",
		RecipientName:     "Иван",
		RecipientEmail:    "ivan@example.com",
		RequestIdentifier: "fixed-uuid-for-test",
	})
	if err != nil {
		t.Fatalf("CreateCertificate: %v", err)
	}
	if result.Number != "4600000500012" {
		t.Errorf("Number = %q, want 4600000500012", result.Number)
	}
	if result.GoodIDD != "CERT-SKU-500" {
		t.Errorf("GoodIDD = %q", result.GoodIDD)
	}
}

func TestCreateCertificate_AutoRequestID(t *testing.T) {
	var gotBody string
	c := newTestClient(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		b, _ := io.ReadAll(r.Body)
		gotBody = string(b)
		w.Header().Set("Content-Type", "text/xml")
		w.Write(fixture(t, "create_cert_resp.xml"))
	}))

	// RequestIdentifier left empty → client generates a UUID
	c.CreateCertificate(context.Background(), CreateCertRequest{GoodIDD: "CERT-SKU-500"})
	if !strings.Contains(gotBody, `RequestIdentifier="`) {
		t.Errorf("expected RequestIdentifier in body, got:\n%s", gotBody)
	}
	// UUID must not be empty string
	start := strings.Index(gotBody, `RequestIdentifier="`) + len(`RequestIdentifier="`)
	end := strings.Index(gotBody[start:], `"`)
	if end == 0 {
		t.Errorf("RequestIdentifier is empty in body:\n%s", gotBody)
	}
}

func TestCreateCertificate_FixedRequestID(t *testing.T) {
	var gotBody string
	c := newTestClient(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		b, _ := io.ReadAll(r.Body)
		gotBody = string(b)
		w.Header().Set("Content-Type", "text/xml")
		w.Write(fixture(t, "create_cert_resp.xml"))
	}))

	c.CreateCertificate(context.Background(), CreateCertRequest{
		GoodIDD:           "CERT-SKU-500",
		RequestIdentifier: "my-idempotency-key",
	})
	if !strings.Contains(gotBody, `RequestIdentifier="my-idempotency-key"`) {
		t.Errorf("expected fixed RequestIdentifier in body, got:\n%s", gotBody)
	}
}
```

- [ ] **Step 3: Run → expect FAIL**

```bash
go test ./... -run TestCreateCertificate -v
```

- [ ] **Step 4: Add to `api.go`** (requires importing `github.com/google/uuid`)

```go
import (
    "context"

    "github.com/google/uuid"
)

// CreateCertificate creates and pre-populates a gift certificate.
// Idempotent by RequestIdentifier (UUID). If req.RequestIdentifier is empty,
// a new UUID is generated automatically.
func (c *Client) CreateCertificate(ctx context.Context, req CreateCertRequest) (CreateCertResult, error) {
	if req.RequestIdentifier == "" {
		req.RequestIdentifier = uuid.New().String()
	}
	storeID := resolveStoreID(c.config.StoreID, req.StoreID)
	raw, err := c.xmlDo(ctx, "create_certificate", storeID, func(salt string) (string, error) {
		return marshalCreateCertRequest(req, salt)
	})
	if err != nil {
		return CreateCertResult{}, err
	}
	return unmarshalCreateCertResponse(raw)
}
```

- [ ] **Step 5: Run → expect PASS**

```bash
go test ./... -run TestCreateCertificate -v
```

- [ ] **Step 6: Commit**

```bash
git add api.go testdata/create_cert_resp.xml
git commit -m "feat(discount-client): CreateCertificate + tests"
```

---

## Task 12: ActivateCertificate

**Files:**
- Create: `testdata/activate_cert_resp.xml`, `testdata/activate_cert_resp_error.xml`
- Modify: `api.go`, `client_test.go`

- [ ] **Step 1: Write fixtures**

`testdata/activate_cert_resp.xml`:
```xml
<Response Type="15" version="4.3" DocId="ORDER-001">
  <CertList>
    <Certificate ID="4600000500012" Nominal="500.00" PrepaidPromo="false" Code="1234" Token="dGVzdA=="/>
  </CertList>
  <Rezult>1</Rezult>
</Response>
```

`testdata/activate_cert_resp_error.xml`:
```xml
<Response Type="5" version="4.0"><Error Description="Сертификат не найден" Code="6" Name="ActivateCert_CertNotFound"/></Response>
```

- [ ] **Step 2: Add tests**

```go
func TestActivateCertificate_Happy(t *testing.T) {
	c := newTestClient(t, staticHandler(fixture(t, "activate_cert_resp.xml")))
	result, err := c.ActivateCertificate(context.Background(), ActivateCertRequest{
		DocID: "ORDER-001",
		Certs: []CertActivationItem{
			{ID: "4600000500012", Nominal: "500.00"},
		},
	})
	if err != nil {
		t.Fatalf("ActivateCertificate: %v", err)
	}
	if result.Result != 1 {
		t.Errorf("Result = %d, want 1", result.Result)
	}
	if result.DocID != "ORDER-001" {
		t.Errorf("DocID = %q, want ORDER-001", result.DocID)
	}
	if len(result.Certs) != 1 {
		t.Fatalf("expected 1 cert, got %d", len(result.Certs))
	}
	cert := result.Certs[0]
	if cert.ID != "4600000500012" || cert.Nominal != "500.00" {
		t.Errorf("unexpected cert: %+v", cert)
	}
	if cert.Code != "1234" || cert.Token != "dGVzdA==" {
		t.Errorf("unexpected code/token: %+v", cert)
	}
}

func TestActivateCertificate_ServerError(t *testing.T) {
	c := newTestClient(t, staticHandler(fixture(t, "activate_cert_resp_error.xml")))
	_, err := c.ActivateCertificate(context.Background(), ActivateCertRequest{
		DocID: "ORDER-BAD",
		Certs: []CertActivationItem{{ID: "0000000000000", Nominal: "500.00"}},
	})
	var sErr *ServerError
	if !errors.As(err, &sErr) {
		t.Fatalf("expected *ServerError, got %T: %v", err, err)
	}
	if sErr.Name != "ActivateCert_CertNotFound" {
		t.Errorf("Name = %q", sErr.Name)
	}
	if sErr.Code != 6 {
		t.Errorf("Code = %d, want 6", sErr.Code)
	}
}

func TestRollbackCertificate_Happy(t *testing.T) {
	var gotBody string
	c := newTestClient(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		b, _ := io.ReadAll(r.Body)
		gotBody = string(b)
		w.Header().Set("Content-Type", "text/xml")
		w.Write(fixture(t, "activate_cert_resp.xml"))
	}))

	err := c.RollbackCertificate(context.Background(), ActivateCertRequest{
		DocID: "ORDER-001",
		Certs: []CertActivationItem{{ID: "4600000500012", Nominal: "500.00"}},
	})
	if err != nil {
		t.Fatalf("RollbackCertificate: %v", err)
	}
	if !strings.Contains(gotBody, `Rollback="1"`) {
		t.Errorf("expected Rollback=1 in body, got:\n%s", gotBody)
	}
}

func TestActivateCertificate_PrepaidPromoFalse(t *testing.T) {
	// PrepaidPromo=false must always appear in the request (not omitted)
	var gotBody string
	c := newTestClient(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		b, _ := io.ReadAll(r.Body)
		gotBody = string(b)
		w.Header().Set("Content-Type", "text/xml")
		w.Write(fixture(t, "activate_cert_resp.xml"))
	}))
	c.ActivateCertificate(context.Background(), ActivateCertRequest{
		DocID: "D", Certs: []CertActivationItem{{ID: "X", Nominal: "100.00", PrepaidPromo: false}},
	})
	if !strings.Contains(gotBody, `PrepaidPromo="false"`) {
		t.Errorf("expected PrepaidPromo=false in body, got:\n%s", gotBody)
	}
}
```

- [ ] **Step 3: Run → expect FAIL**

```bash
go test ./... -run "TestActivateCertificate|TestRollbackCertificate" -v
```

- [ ] **Step 4: Add to `api.go`**

```go
// ActivateCertificate activates one or more gift certificates. Idempotent by DocID.
func (c *Client) ActivateCertificate(ctx context.Context, req ActivateCertRequest) (ActivateCertResult, error) {
	storeID := resolveStoreID(c.config.StoreID, req.StoreID)
	raw, err := c.xmlDo(ctx, "activate_certificate", storeID, func(salt string) (string, error) {
		return marshalActivateCertRequest(req, false, salt)
	})
	if err != nil {
		return ActivateCertResult{}, err
	}
	return unmarshalActivateCertResponse(raw)
}

// RollbackCertificate reverses certificate activation. Idempotent by DocID.
func (c *Client) RollbackCertificate(ctx context.Context, req ActivateCertRequest) error {
	storeID := resolveStoreID(c.config.StoreID, req.StoreID)
	_, err := c.xmlDo(ctx, "rollback_certificate", storeID, func(salt string) (string, error) {
		return marshalActivateCertRequest(req, true, salt)
	})
	return err
}
```

- [ ] **Step 5: Run → expect PASS**

```bash
go test ./... -run "TestActivateCertificate|TestRollbackCertificate" -v
```

- [ ] **Step 6: Commit**

```bash
git add api.go testdata/activate_cert_resp.xml testdata/activate_cert_resp_error.xml
git commit -m "feat(discount-client): ActivateCertificate / RollbackCertificate + tests"
```

---

## Task 13: DOCFromOrderID & Checksum Determinism Tests

**Files:**
- Modify: `client_test.go`

These test pure functions already implemented; this task confirms coverage.

- [ ] **Step 1: Add tests**

```go
func TestDOCFromOrderID(t *testing.T) {
	tests := []struct{ input, want string }{
		{"ORD-001", "0000352ORD-001"},
		{"", "0000352"},
		{"12345", "000035212345"},
	}
	for _, tc := range tests {
		got := DOCFromOrderID(tc.input)
		if got != tc.want {
			t.Errorf("DOCFromOrderID(%q) = %q, want %q", tc.input, got, tc.want)
		}
	}
}

func TestChecksum_CrossCheck(t *testing.T) {
	// Reference: echo -n "9999999secret1234567890" | md5sum
	// = 6d849bd8720de9c4663461035ff04382
	got := checksum("9999999", "secret", "1234567890")
	const want = "6d849bd8720de9c4663461035ff04382"
	if got != want {
		t.Errorf("got %q, want %q", got, want)
	}
}
```

- [ ] **Step 2: Run → expect PASS**

```bash
go test ./... -run "TestDOCFromOrderID|TestChecksum_CrossCheck" -v
```

Expected: all PASS.

- [ ] **Step 3: Full test suite**

```bash
go test ./... -v 2>&1 | tail -30
```

Expected: all tests PASS, zero failures.

- [ ] **Step 4: Commit**

```bash
git add client_test.go
git commit -m "test(discount-client): DOCFromOrderID + checksum cross-check"
```

---

## Task 14: README, Final Verification & Tag v0.1.0

**Files:**
- Create: `platform-new/clients/discount/README.md`

- [ ] **Step 1: Write `README.md`**

```markdown
# clients/discount

Go client for the WWWDKMVC "сервер скидок" (Gloria Jeans discount/loyalty server).

## Protocol

Single XML endpoint: `POST /api/Query?idStore={storeID}&CheckSum={md5(storeID+word+salt)}`  
Content-Type: `application/gjdk` — legacy XML, **not JSON**.

Auth uses a rotating shared secret (`WordStore`). The client detects a `<Response Type="6" word="..."/>` response and retries exactly once with the new word.

## Money Units

All monetary fields (`Price`, `Summ`, `Nominal`, `Val` when `DiscountType=2`) are **РУБЛИ** as decimal strings verbatim from the wire (`"500.00"`, `"1299.00"`). **Never parse to float64.** Convert to your `Money` type (kopecks ×100) in your adapter.

## Operations

| Method | Type | Description |
|--------|------|-------------|
| `GetDiscount` | 1 | Advisory basket quote (stateless) |
| `SpendCoupon` / `ReturnCoupon` | 17 | Coupon spend/rollback; idempotent by DOC |
| `SpendBonusExt` / `ReturnBonusExt` | 21 | Loyalty point spend/rollback; idempotent by DOC |
| `TranslatePromoCode` / `RollbackPromoCode` | 30 | Promo code → EAN-13 coupon |
| `CreateCertificate` | 16 | Gift cert creation; idempotent by `RequestIdentifier` |
| `ActivateCertificate` / `RollbackCertificate` | 15 | Cert activation; idempotent by `DocID` |

## Usage

```go
import (
    "context"
    discount "gitlab.gloria.aaanet.ru/e-commerce/platform/clients/discount"
)

store := discount.NewInMemoryWordStore(os.Getenv("DISCOUNT_WORD"))
client, err := discount.New(discount.Config{
    BaseURL:   os.Getenv("DISCOUNT_BASE_URL"),
    StoreID:   os.Getenv("DISCOUNT_STORE_ID"),
    WordStore: store,
})

resp, err := client.GetDiscount(ctx, discount.GetDiscountRequest{
    Items: []discount.GetDiscountItem{
        {ProductID: "SKU001", Qty: 2, Price: "1299.00", SellOff: 0},
    },
})
```

## DOC idempotency key

```go
doc := discount.DOCFromOrderID(clientOrderID) // "0000352" + clientOrderID
```

## Configuration keys

Secrets are in k8s secret `secret-is-api-env-builder`:
- `SALE_SERVICE_CLIENT_URL` → `Config.BaseURL`
- `SALE_SERVICE_CLIENT_WORD` → initial word for `NewInMemoryWordStore`
- `SALE_SERVICE_CLIENT_STORE_ID` → `Config.StoreID`
```

- [ ] **Step 2: Run full build + vet + test — collect evidence**

```bash
go build ./... && echo "BUILD OK"
go vet ./... && echo "VET OK"
go test ./... -v -count=1 2>&1 | tee /tmp/discount-test-output.txt
grep -E "^(ok|FAIL|---)" /tmp/discount-test-output.txt
```

Expected output (all lines start with `ok` or `---  PASS`):
```
ok      gitlab.gloria.aaanet.ru/e-commerce/platform/clients/discount
```

Zero `FAIL` lines.

- [ ] **Step 3: Commit README**

```bash
git add README.md
git commit -m "docs(discount-client): README with protocol, money-units, usage"
```

- [ ] **Step 4: Tag v0.1.0** *(tag on the module path prefix if using git tags for Go modules)*

```bash
git tag clients/discount/v0.1.0
git push origin clients/discount/v0.1.0
```

(If the repo uses a flat tag without subpath, use `git tag discount/v0.1.0` per the project convention.)

---

## Self-Review Checklist

- [x] All 6 operations covered: GetDiscount, BonusSpend, BonusSpendExt, CouponTranslate, CreateCertificate, ActivateCertificate
- [x] All rollback variants: ReturnCoupon, ReturnBonusExt, RollbackPromoCode, RollbackCertificate
- [x] Word rotation: retry-once test (Task 6), no-double-retry test (Task 6)
- [x] Type=5 ServerError parsing (Task 6 + Task 12)
- [x] Rezult fail-closed classification (Task 4): ok → success, IsSubmitted → idempotent, everything else → SpendError
- [x] Idempotent duplicate test (Task 8: BonusSpendExt_IsSubmitted)
- [x] Money fields as `string` everywhere — no `float64` in types.go or xml.go
- [x] DOCFromOrderID = "0000352" + clientOrderID (Task 13)
- [x] Checksum deterministic cross-check with known md5 (Task 13)
- [x] Charset decode windows-1251 (Task 3)
- [x] Content-Type: application/gjdk (Task 6: TestXmlDo_RequestContentType)
- [x] Per-request storeID override (Task 7: TestGetDiscount_StoreIDOverride)
- [x] RequestIdentifier auto-generated if empty (Task 11)
- [x] PrepaidPromo=false always in ActivateCert request (Task 12)
- [x] Rollback=1 in ReturnCoupon and RollbackCertificate requests verified (Tasks 8, 12)
- [x] go.mod go 1.26.2 (Task 1)
- [x] README with money-unit warning (Task 14)
