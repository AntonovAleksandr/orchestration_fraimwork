# Auth-контур (Customer Session) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add customer-Bearer JWT validation to ecom-gateway with three guard tiers (public / auth-optional / auth-required), identity stored in `reqctx.CustomerIdentity`, and propagated downstream as `X-Customer-Id` header via outbound client decorators.

**Architecture:** Local JWT verify (ADR-0013, Option A) — gateway parses Passport RS256 JWT using the RSA public key from env config; no network call on the hot path. Identity lives in `internal/platform/reqctx.CustomerIdentity` and is set by `internal/platform/authn` middleware. Guards are applied per route group in `transport/routes.go` via chi `.Group()`. `clients/customer-auth` is NOT needed in this phase (login/refresh remain in legacy BFF).

**Tech Stack:** Go 1.26.2 · `github.com/golang-jwt/jwt/v5` · chi v5 · `net/http` httptest · stdlib `testing`

**Service dir:** `platform-new/ecom-gateway/` · **Module:** `gj-ecom-gateway`

---

## File Structure

### New files

```
internal/platform/authn/
├── jwt.go              # Verifier: RSA PEM loading, RS256 parse+validate, claims extraction
├── jwt_test.go         # table-driven: valid / expired / wrong-key / wrong-iss / wrong-aud / no-customer-id
├── middleware.go       # Guards struct + NewGuards + NewPassthroughGuards + RequireAuth + OptionalAuth
└── middleware_test.go  # httptest: 401/200 per tier + IDOR test

docs/architecture/adr/
└── 0013-auth-local-jwt-no-auth-client.md
```

### Modified files

```
internal/platform/reqctx/reqctx.go          # + CustomerIdentity type, set/get helpers, PropagateCustomerID
internal/platform/reqctx/reqctx_test.go     # + tests for new functions
internal/platform/httpx/error.go            # + Unauthorized() + Forbidden() methods
internal/platform/httpx/error_test.go       # + tests for new methods
internal/platform/config/config.go          # + CustomerAuthConfig + field + Load + Validate
internal/platform/config/config_test.go     # + tests for new config
internal/app/container.go                   # + AuthGuards *authn.Guards + construction; return (*Container, error)
internal/app/app.go                         # handle container err; pass Auth to transport.Dependencies
internal/platform/transport/routes.go       # + AuthDeps; apply OptionalAuth to recommendations group
internal/app/wire/recommendations.go        # + reqctx.PropagateCustomerID in outbound decorator
internal/domains/recommendations/boundary_test.go  # + authn to forbidden imports list
go.mod + go.sum                             # + github.com/golang-jwt/jwt/v5
```

---

### Task 1: ADR-0013 — local JWT auth, no auth client

**Files:**
- Create: `docs/architecture/adr/0013-auth-local-jwt-no-auth-client.md`

- [ ] **Step 1: Write the ADR**

Create `docs/architecture/adr/0013-auth-local-jwt-no-auth-client.md`:

```markdown
# ADR-0013: Edge auth — local JWT verification, no auth client

- **Status:** Accepted
- **Date:** 2026-05-31
- **Deciders:** Zak (project lead)
- **Scope:** ecom-gateway; auth topology for the whole new GJ Go platform.

## Context

`ecom-gateway` is the north-south BFF for site/mobile. As it gains guarded endpoints
(checkout, profile, basket-commit) it needs to authenticate the customer-Bearer token
issued by ENSI `customer-auth` (Laravel Passport, RS256 JWT with custom `customer_id`
claim added by `corbosman/laravel-passport-claims`).

Two questions need resolution:

1. **How to validate the customer-Bearer** — locally using the public key, or via a
   network call to `customer-auth`.
2. **Does gateway need `clients/customer-auth`** (the Go typed client for customer-auth)?

### Option A — Local JWT verification (chosen)

Gateway loads the Passport RSA public key from config at startup and verifies signatures
locally. No network call on the hot path. Token validity is bounded by `exp`; revocation
within the token's lifetime is not detected (mitigated by a short TTL on Passport tokens).

### Option B — Remote introspection

Gateway calls the `customer-auth` introspection endpoint per request. Catches revocation;
adds a network hop (mitigatable by a per-token cache). Requires `clients/customer-auth`.

### Does gateway own the login flow?

In the current phase (gradual migration), `login` / `refresh` / `logout` remain in the
legacy BFF. Gateway only validates tokens produced by the legacy flow. On a `401`,
the frontend goes to legacy BFF for refresh and retries the gateway. Since gateway does
NOT issue or refresh tokens in this phase, `clients/customer-auth` is not needed.

## Decision

**Option A: local RS256 JWT verify using Passport's RSA public key from env config.**

- No `clients/customer-auth` in this phase.
- Config env vars: `CUSTOMER_AUTH_PUBLIC_KEY` (PEM string) or `CUSTOMER_AUTH_PUBLIC_KEY_FILE`
  (path to PEM file) + `CUSTOMER_AUTH_ISSUER` + `CUSTOMER_AUTH_AUDIENCE`.
- If auth is unconfigured (empty `CUSTOMER_AUTH_ISSUER`), guards fall back to no-ops —
  local dev works without a real Passport key.
- When login/refresh moves to gateway, revisit: add `clients/customer-auth` for the auth
  flow and keep local verify for validation.

### Three guard tiers

| Tier | No `Authorization` header | Invalid / expired token |
|------|--------------------------|------------------------|
| **public** | allow | allow |
| **auth-optional** | allow (anonymous / degraded) | **401** — force frontend refresh |
| **auth-required** | **401** | **401** |

"No token" ≠ "bad token": a present-but-invalid token always returns 401 (even on optional
routes) so the frontend receives a refresh signal rather than silently degrading an
authenticated session.

### Infrastructure requirement (deploy)

Internal services (checkout, catalog-cache, customers, baskets) MUST be reachable only
through gateway. Direct external access allows `X-Customer-Id` spoofing. Enforce via
Kubernetes NetworkPolicy or namespace isolation.

## Consequences

**Positive:** Zero auth latency on the hot path; no dependency on customer-auth availability
for validation.

**Negative:** Revocation within token lifetime is not detected. Mitigated by configuring
short TTL on Passport tokens in `customer-auth`.

## References

- ADR-0008 (topology) — gateway is a north-south edge, not an internal hub.
- ADR-0009 (client packaging) — no `clients/customer-auth` until login moves here.
- ADR-0003 (layout) — auth is `platform/`, not a domain.
- Spec: customer auth section; `checkout` spec §2 (`auth_context`).
```

- [ ] **Step 2: Commit**

```bash
git add docs/architecture/adr/0013-auth-local-jwt-no-auth-client.md
git commit -m "docs(adr): 0013 — local JWT edge auth, no auth client in this phase"
```

---

### Task 2: reqctx — CustomerIdentity type + downstream helper

**Files:**
- Modify: `internal/platform/reqctx/reqctx.go`
- Modify: `internal/platform/reqctx/reqctx_test.go`

- [ ] **Step 1: Write failing tests**

Append to `internal/platform/reqctx/reqctx_test.go` (add `"context"` and `"net/http"` to imports if not already present):

```go
func TestCustomerIdentity_RoundTrip(t *testing.T) {
	id := CustomerIdentity{CustomerID: "cust-42", Scopes: []string{"*"}}
	r := httptest.NewRequest("GET", "/", nil)
	r = SetCustomerIdentity(r, id)
	got := CustomerIdentityOf(r)
	if got.CustomerID != id.CustomerID {
		t.Fatalf("CustomerID: want %q, got %q", id.CustomerID, got.CustomerID)
	}
	if len(got.Scopes) != 1 || got.Scopes[0] != "*" {
		t.Fatalf("Scopes: want [*], got %v", got.Scopes)
	}
}

func TestCustomerIdentity_ZeroWhenUnset(t *testing.T) {
	r := httptest.NewRequest("GET", "/", nil)
	if CustomerIdentityOf(r).IsAuthenticated() {
		t.Fatal("want anonymous, got authenticated")
	}
}

func TestPropagateCustomerID_SetsHeader(t *testing.T) {
	id := CustomerIdentity{CustomerID: "cust-99"}
	ctx := WithCustomerIdentity(context.Background(), id)
	outbound, _ := http.NewRequest("GET", "http://downstream/", nil)
	PropagateCustomerID(ctx, outbound)
	if got := outbound.Header.Get("X-Customer-Id"); got != "cust-99" {
		t.Fatalf("X-Customer-Id: want cust-99, got %q", got)
	}
}

func TestPropagateCustomerID_NoopForAnonymous(t *testing.T) {
	ctx := context.Background()
	outbound, _ := http.NewRequest("GET", "http://downstream/", nil)
	PropagateCustomerID(ctx, outbound)
	if got := outbound.Header.Get("X-Customer-Id"); got != "" {
		t.Fatalf("expected no X-Customer-Id for anonymous, got %q", got)
	}
}
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd platform-new/ecom-gateway && go test ./internal/platform/reqctx/...
```

Expected: `FAIL` — `CustomerIdentity`, `SetCustomerIdentity`, `CustomerIdentityOf`, `WithCustomerIdentity`, `PropagateCustomerID` undefined.

- [ ] **Step 3: Implement**

Replace the entire contents of `internal/platform/reqctx/reqctx.go` with:

```go
// Package reqctx is the dedicated place for per-request data carried via the
// request context (guideline §6.2).
package reqctx

import (
	"context"
	"net/http"
)

type ctxKey int

const (
	requestIDKey        ctxKey = iota
	customerIdentityKey ctxKey = iota
)

// CustomerIdentity carries the verified identity of the authenticated customer.
// Zero value (empty CustomerID) represents an anonymous / guest request.
type CustomerIdentity struct {
	CustomerID string
	Scopes     []string
}

// IsAuthenticated reports whether the identity represents an authenticated customer.
func (c CustomerIdentity) IsAuthenticated() bool { return c.CustomerID != "" }

// WithRequestID returns a new context carrying the request ID.
func WithRequestID(ctx context.Context, id string) context.Context {
	return context.WithValue(ctx, requestIDKey, id)
}

// SetRequestID returns a copy of r with the request ID in its context.
func SetRequestID(r *http.Request, id string) *http.Request {
	return r.WithContext(WithRequestID(r.Context(), id))
}

// RequestIDFromContext returns the request ID stored in ctx, or "" if none.
func RequestIDFromContext(ctx context.Context) string {
	if v, ok := ctx.Value(requestIDKey).(string); ok {
		return v
	}
	return ""
}

// RequestID extracts the request ID from r.Context(), or "" if none.
func RequestID(r *http.Request) string {
	return RequestIDFromContext(r.Context())
}

// WithCustomerIdentity returns a new context carrying the customer identity.
func WithCustomerIdentity(ctx context.Context, id CustomerIdentity) context.Context {
	return context.WithValue(ctx, customerIdentityKey, id)
}

// SetCustomerIdentity returns a copy of r with the customer identity in its context.
func SetCustomerIdentity(r *http.Request, id CustomerIdentity) *http.Request {
	return r.WithContext(WithCustomerIdentity(r.Context(), id))
}

// CustomerIdentityFromContext returns the customer identity from ctx, or zero value.
func CustomerIdentityFromContext(ctx context.Context) CustomerIdentity {
	if v, ok := ctx.Value(customerIdentityKey).(CustomerIdentity); ok {
		return v
	}
	return CustomerIdentity{}
}

// CustomerIdentityOf extracts customer identity from r.Context(), or zero value.
func CustomerIdentityOf(r *http.Request) CustomerIdentity {
	return CustomerIdentityFromContext(r.Context())
}

// PropagateCustomerID reads CustomerIdentity from ctx and sets X-Customer-Id on r.
// No-op when the identity is anonymous.
func PropagateCustomerID(ctx context.Context, r *http.Request) {
	if id := CustomerIdentityFromContext(ctx); id.IsAuthenticated() {
		r.Header.Set("X-Customer-Id", id.CustomerID)
	}
}
```

- [ ] **Step 4: Run tests**

```bash
cd platform-new/ecom-gateway && go test ./internal/platform/reqctx/...
```

Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add internal/platform/reqctx/
git commit -m "feat(reqctx): CustomerIdentity type, context helpers, PropagateCustomerID"
```

---

### Task 3: httpx — Unauthorized + Forbidden helpers

**Files:**
- Modify: `internal/platform/httpx/error.go`
- Modify: `internal/platform/httpx/error_test.go`

- [ ] **Step 1: Write failing tests**

Append to `internal/platform/httpx/error_test.go` (add `"encoding/json"`, `"net/http"`, `"net/http/httptest"` to imports if missing):

```go
func TestHelper_Unauthorized(t *testing.T) {
	h := NewHelper()
	rec := httptest.NewRecorder()
	h.Unauthorized(rec, "missing_token", "authorization required")
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("want 401, got %d", rec.Code)
	}
	var env ErrorEnvelope
	if err := json.NewDecoder(rec.Body).Decode(&env); err != nil {
		t.Fatalf("decode body: %v", err)
	}
	if env.Error != "missing_token" {
		t.Fatalf("want error=missing_token, got %q", env.Error)
	}
}

func TestHelper_Forbidden(t *testing.T) {
	h := NewHelper()
	rec := httptest.NewRecorder()
	h.Forbidden(rec, "insufficient_scope", "scope required")
	if rec.Code != http.StatusForbidden {
		t.Fatalf("want 403, got %d", rec.Code)
	}
}
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd platform-new/ecom-gateway && go test ./internal/platform/httpx/...
```

Expected: `FAIL` — `h.Unauthorized undefined`, `h.Forbidden undefined`.

- [ ] **Step 3: Implement**

Append to `internal/platform/httpx/error.go` (after the `Internal` method):

```go
// Unauthorized writes a 401 response.
func (h *Helper) Unauthorized(w http.ResponseWriter, code, msg string) {
	h.JSON(w, http.StatusUnauthorized, code, msg)
}

// Forbidden writes a 403 response.
func (h *Helper) Forbidden(w http.ResponseWriter, code, msg string) {
	h.JSON(w, http.StatusForbidden, code, msg)
}
```

- [ ] **Step 4: Run tests**

```bash
cd platform-new/ecom-gateway && go test ./internal/platform/httpx/...
```

Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add internal/platform/httpx/
git commit -m "feat(httpx): Unauthorized + Forbidden error helpers"
```

---

### Task 4: authn — JWT Verifier

**Files:**
- Create: `internal/platform/authn/jwt.go`
- Create: `internal/platform/authn/jwt_test.go`

- [ ] **Step 1: Add golang-jwt dependency**

```bash
cd platform-new/ecom-gateway && go get github.com/golang-jwt/jwt/v5 && go mod tidy
```

Expected: `go.mod` now contains a `github.com/golang-jwt/jwt/v5 v5.x.y` line.

- [ ] **Step 2: Write failing tests**

Create `internal/platform/authn/jwt_test.go`:

```go
package authn

import (
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"encoding/pem"
	"errors"
	"testing"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

func makeTestVerifier(t *testing.T) (*Verifier, *rsa.PrivateKey) {
	t.Helper()
	priv, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatalf("rsa.GenerateKey: %v", err)
	}
	pubDER, err := x509.MarshalPKIXPublicKey(&priv.PublicKey)
	if err != nil {
		t.Fatalf("MarshalPKIXPublicKey: %v", err)
	}
	pubPEM := string(pem.EncodeToMemory(&pem.Block{Type: "PUBLIC KEY", Bytes: pubDER}))
	v, err := NewVerifier(pubPEM, "https://auth.example.com", "ecom-gateway")
	if err != nil {
		t.Fatalf("NewVerifier: %v", err)
	}
	return v, priv
}

func makeToken(t *testing.T, priv *rsa.PrivateKey, customerID string, exp time.Time, issuer, audience string) string {
	t.Helper()
	claims := passportClaims{
		RegisteredClaims: jwt.RegisteredClaims{
			Subject:   "user-1",
			Issuer:    issuer,
			Audience:  jwt.ClaimStrings{audience},
			ExpiresAt: jwt.NewNumericDate(exp),
			IssuedAt:  jwt.NewNumericDate(time.Now().Add(-time.Second)),
		},
		Scopes:     []string{"*"},
		CustomerID: customerID,
	}
	tok := jwt.NewWithClaims(jwt.SigningMethodRS256, claims)
	signed, err := tok.SignedString(priv)
	if err != nil {
		t.Fatalf("sign token: %v", err)
	}
	return signed
}

func makeTokenNoCustomerID(t *testing.T, priv *rsa.PrivateKey) string {
	t.Helper()
	claims := jwt.MapClaims{
		"sub": "user-1",
		"iss": "https://auth.example.com",
		"aud": jwt.ClaimStrings{"ecom-gateway"},
		"exp": jwt.NewNumericDate(time.Now().Add(time.Hour)),
		"iat": jwt.NewNumericDate(time.Now()),
	}
	tok := jwt.NewWithClaims(jwt.SigningMethodRS256, claims)
	signed, err := tok.SignedString(priv)
	if err != nil {
		t.Fatalf("sign token: %v", err)
	}
	return signed
}

func TestNewVerifier_RejectsBadPEM(t *testing.T) {
	_, err := NewVerifier("not-pem", "iss", "aud")
	if err == nil {
		t.Fatal("expected error for invalid PEM, got nil")
	}
}

func TestVerifier_Verify(t *testing.T) {
	v, priv := makeTestVerifier(t)

	otherKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatalf("rsa.GenerateKey: %v", err)
	}

	future := time.Now().Add(time.Hour)
	past := time.Now().Add(-time.Hour)

	tests := []struct {
		name       string
		token      string
		wantCustID string
		wantErr    error
	}{
		{
			name:       "valid token",
			token:      makeToken(t, priv, "cust-42", future, "https://auth.example.com", "ecom-gateway"),
			wantCustID: "cust-42",
		},
		{
			name:    "expired token",
			token:   makeToken(t, priv, "cust-42", past, "https://auth.example.com", "ecom-gateway"),
			wantErr: ErrTokenExpired,
		},
		{
			name:    "wrong signing key",
			token:   makeToken(t, otherKey, "cust-42", future, "https://auth.example.com", "ecom-gateway"),
			wantErr: ErrTokenInvalid,
		},
		{
			name:    "wrong issuer",
			token:   makeToken(t, priv, "cust-42", future, "https://wrong.example.com", "ecom-gateway"),
			wantErr: ErrTokenInvalid,
		},
		{
			name:    "wrong audience",
			token:   makeToken(t, priv, "cust-42", future, "https://auth.example.com", "other-service"),
			wantErr: ErrTokenInvalid,
		},
		{
			name:    "missing customer_id claim",
			token:   makeTokenNoCustomerID(t, priv),
			wantErr: ErrTokenInvalid,
		},
		{
			name:    "empty string",
			token:   "",
			wantErr: ErrTokenInvalid,
		},
		{
			name:    "garbage string",
			token:   "not.a.jwt",
			wantErr: ErrTokenInvalid,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			id, err := v.Verify(tc.token)
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("want error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if id.CustomerID != tc.wantCustID {
				t.Fatalf("CustomerID: want %q, got %q", tc.wantCustID, id.CustomerID)
			}
		})
	}
}
```

- [ ] **Step 3: Run to verify tests fail**

```bash
cd platform-new/ecom-gateway && go test ./internal/platform/authn/...
```

Expected: `FAIL` — package does not exist / `Verifier`, `ErrTokenExpired`, `ErrTokenInvalid`, `passportClaims` undefined.

- [ ] **Step 4: Implement**

Create `internal/platform/authn/jwt.go`:

```go
package authn

import (
	"crypto/rsa"
	"crypto/x509"
	"encoding/pem"
	"errors"
	"fmt"

	"github.com/golang-jwt/jwt/v5"
	"gj-ecom-gateway/internal/platform/reqctx"
)

var (
	ErrTokenExpired      = errors.New("token expired")
	ErrTokenInvalid      = errors.New("token invalid")
	ErrInsufficientScope = errors.New("insufficient scope")
)

// Verifier validates Passport RS256 JWTs and extracts CustomerIdentity.
type Verifier struct {
	publicKey *rsa.PublicKey
	issuer    string
	audience  string
}

// passportClaims extends RegisteredClaims with Laravel Passport custom fields.
type passportClaims struct {
	jwt.RegisteredClaims
	Scopes     []string `json:"scopes"`
	CustomerID string   `json:"customer_id"`
}

// NewVerifier parses publicKeyPEM (PKIX/SPKI "PUBLIC KEY" PEM block) and returns
// a Verifier that checks issuer and audience on every token.
func NewVerifier(publicKeyPEM, issuer, audience string) (*Verifier, error) {
	block, _ := pem.Decode([]byte(publicKeyPEM))
	if block == nil {
		return nil, fmt.Errorf("authn: failed to decode PEM block")
	}
	pub, err := x509.ParsePKIXPublicKey(block.Bytes)
	if err != nil {
		return nil, fmt.Errorf("authn: parse public key: %w", err)
	}
	rsaPub, ok := pub.(*rsa.PublicKey)
	if !ok {
		return nil, fmt.Errorf("authn: public key is not RSA")
	}
	return &Verifier{publicKey: rsaPub, issuer: issuer, audience: audience}, nil
}

// Verify parses and validates tokenStr, returning the customer identity on success.
// Returns ErrTokenExpired for expired tokens, ErrTokenInvalid for all other failures.
func (v *Verifier) Verify(tokenStr string) (reqctx.CustomerIdentity, error) {
	var claims passportClaims
	_, err := jwt.ParseWithClaims(tokenStr, &claims,
		func(t *jwt.Token) (interface{}, error) {
			if _, ok := t.Method.(*jwt.SigningMethodRSA); !ok {
				return nil, fmt.Errorf("unexpected signing method: %v", t.Header["alg"])
			}
			return v.publicKey, nil
		},
		jwt.WithIssuer(v.issuer),
		jwt.WithAudience(v.audience),
		jwt.WithExpirationRequired(),
	)
	if err != nil {
		if errors.Is(err, jwt.ErrTokenExpired) {
			return reqctx.CustomerIdentity{}, ErrTokenExpired
		}
		return reqctx.CustomerIdentity{}, ErrTokenInvalid
	}
	if claims.CustomerID == "" {
		return reqctx.CustomerIdentity{}, ErrTokenInvalid
	}
	return reqctx.CustomerIdentity{
		CustomerID: claims.CustomerID,
		Scopes:     claims.Scopes,
	}, nil
}
```

- [ ] **Step 5: Run tests**

```bash
cd platform-new/ecom-gateway && go test ./internal/platform/authn/...
```

Expected: `PASS`

- [ ] **Step 6: Commit**

```bash
git add internal/platform/authn/jwt.go internal/platform/authn/jwt_test.go go.mod go.sum
git commit -m "feat(authn): JWT Verifier — RS256 local validation + Passport claims extraction"
```

---

### Task 5: authn — Guards middleware

**Files:**
- Create: `internal/platform/authn/middleware.go`
- Create: `internal/platform/authn/middleware_test.go`

- [ ] **Step 1: Write failing tests**

Create `internal/platform/authn/middleware_test.go`:

```go
package authn

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"gj-ecom-gateway/internal/platform/httpx"
	"gj-ecom-gateway/internal/platform/reqctx"
)

func makeTestGuards(t *testing.T) *Guards {
	t.Helper()
	v, _ := makeTestVerifier(t)
	return NewGuards(v, httpx.NewHelper())
}

func echoIDHandler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		id := reqctx.CustomerIdentityOf(r)
		w.Header().Set("X-Got-Customer-Id", id.CustomerID)
		w.WriteHeader(http.StatusOK)
	})
}

func TestRequireAuth_NoToken_Returns401(t *testing.T) {
	guards := makeTestGuards(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/", nil)
	guards.RequireAuth(echoIDHandler()).ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("want 401, got %d: %s", rec.Code, rec.Body.String())
	}
}

func TestRequireAuth_ValidToken_Returns200WithIdentity(t *testing.T) {
	v, priv := makeTestVerifier(t)
	guards := NewGuards(v, httpx.NewHelper())
	tok := makeToken(t, priv, "cust-42", time.Now().Add(time.Hour), "https://auth.example.com", "ecom-gateway")
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/", nil)
	req.Header.Set("Authorization", "Bearer "+tok)
	guards.RequireAuth(echoIDHandler()).ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("want 200, got %d: %s", rec.Code, rec.Body.String())
	}
	if got := rec.Header().Get("X-Got-Customer-Id"); got != "cust-42" {
		t.Fatalf("X-Got-Customer-Id: want cust-42, got %q", got)
	}
}

func TestRequireAuth_ExpiredToken_Returns401(t *testing.T) {
	v, priv := makeTestVerifier(t)
	guards := NewGuards(v, httpx.NewHelper())
	tok := makeToken(t, priv, "cust-42", time.Now().Add(-time.Hour), "https://auth.example.com", "ecom-gateway")
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/", nil)
	req.Header.Set("Authorization", "Bearer "+tok)
	guards.RequireAuth(echoIDHandler()).ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("want 401 for expired, got %d", rec.Code)
	}
}

func TestRequireAuth_InvalidToken_Returns401(t *testing.T) {
	guards := makeTestGuards(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/", nil)
	req.Header.Set("Authorization", "Bearer garbage.token.value")
	guards.RequireAuth(echoIDHandler()).ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("want 401 for invalid token, got %d", rec.Code)
	}
}

func TestOptionalAuth_NoToken_PassesAsAnonymous(t *testing.T) {
	guards := makeTestGuards(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/", nil)
	guards.OptionalAuth(echoIDHandler()).ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("optional: want 200 for anonymous (no token), got %d", rec.Code)
	}
	if got := rec.Header().Get("X-Got-Customer-Id"); got != "" {
		t.Fatalf("optional: anonymous should have no customer ID, got %q", got)
	}
}

func TestOptionalAuth_ValidToken_SetsIdentity(t *testing.T) {
	v, priv := makeTestVerifier(t)
	guards := NewGuards(v, httpx.NewHelper())
	tok := makeToken(t, priv, "cust-99", time.Now().Add(time.Hour), "https://auth.example.com", "ecom-gateway")
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/", nil)
	req.Header.Set("Authorization", "Bearer "+tok)
	guards.OptionalAuth(echoIDHandler()).ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("want 200, got %d", rec.Code)
	}
	if got := rec.Header().Get("X-Got-Customer-Id"); got != "cust-99" {
		t.Fatalf("X-Got-Customer-Id: want cust-99, got %q", got)
	}
}

func TestOptionalAuth_ExpiredToken_Returns401(t *testing.T) {
	v, priv := makeTestVerifier(t)
	guards := NewGuards(v, httpx.NewHelper())
	tok := makeToken(t, priv, "cust-99", time.Now().Add(-time.Hour), "https://auth.example.com", "ecom-gateway")
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/", nil)
	req.Header.Set("Authorization", "Bearer "+tok)
	guards.OptionalAuth(echoIDHandler()).ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("optional: expired token must return 401 (not silent downgrade), got %d", rec.Code)
	}
}

func TestRequireAuth_AntiIDOR(t *testing.T) {
	v, priv := makeTestVerifier(t)
	guards := NewGuards(v, httpx.NewHelper())

	var capturedID string
	spy := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedID = reqctx.CustomerIdentityOf(r).CustomerID
		w.WriteHeader(http.StatusOK)
	})

	tok := makeToken(t, priv, "real-cust-id", time.Now().Add(time.Hour), "https://auth.example.com", "ecom-gateway")
	req := httptest.NewRequest("POST", "/", strings.NewReader(`{"customer_id":"evil-spoofed-id"}`))
	req.Header.Set("Authorization", "Bearer "+tok)
	req.Header.Set("Content-Type", "application/json")
	guards.RequireAuth(spy).ServeHTTP(httptest.NewRecorder(), req)

	if capturedID != "real-cust-id" {
		t.Fatalf("IDOR: downstream received %q, want real-cust-id from token", capturedID)
	}
}

func TestPassthroughGuards_AlwaysAllow(t *testing.T) {
	guards := NewPassthroughGuards()
	for _, mw := range []struct {
		name string
		fn   func(http.Handler) http.Handler
	}{
		{"RequireAuth", guards.RequireAuth},
		{"OptionalAuth", guards.OptionalAuth},
	} {
		t.Run(mw.name, func(t *testing.T) {
			rec := httptest.NewRecorder()
			req := httptest.NewRequest("GET", "/", nil)
			mw.fn(echoIDHandler()).ServeHTTP(rec, req)
			if rec.Code != http.StatusOK {
				t.Fatalf("passthrough %s: want 200, got %d", mw.name, rec.Code)
			}
		})
	}
}
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd platform-new/ecom-gateway && go test ./internal/platform/authn/...
```

Expected: `FAIL` — `Guards`, `NewGuards`, `NewPassthroughGuards` undefined.

- [ ] **Step 3: Implement**

Create `internal/platform/authn/middleware.go`:

```go
package authn

import (
	"errors"
	"net/http"
	"strings"

	"gj-ecom-gateway/internal/platform/httpx"
	"gj-ecom-gateway/internal/platform/reqctx"
)

// Guards holds the chi-compatible middleware for the two protected tiers.
type Guards struct {
	RequireAuth  func(http.Handler) http.Handler
	OptionalAuth func(http.Handler) http.Handler
}

// NewGuards builds Guards backed by v. Auth errors are written via errs.
func NewGuards(v *Verifier, errs *httpx.Helper) *Guards {
	return &Guards{
		RequireAuth:  requireAuthMiddleware(v, errs),
		OptionalAuth: optionalAuthMiddleware(v, errs),
	}
}

// NewPassthroughGuards returns Guards where both middleware are no-ops.
// Use when auth is not configured (local dev without a Passport key).
func NewPassthroughGuards() *Guards {
	pass := func(next http.Handler) http.Handler { return next }
	return &Guards{RequireAuth: pass, OptionalAuth: pass}
}

func requireAuthMiddleware(v *Verifier, errs *httpx.Helper) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			tokenStr, ok := extractBearer(r)
			if !ok {
				errs.Unauthorized(w, "missing_token", "authorization required")
				return
			}
			identity, err := v.Verify(tokenStr)
			if err != nil {
				writeAuthError(w, errs, err)
				return
			}
			next.ServeHTTP(w, reqctx.SetCustomerIdentity(r, identity))
		})
	}
}

func optionalAuthMiddleware(v *Verifier, errs *httpx.Helper) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			tokenStr, ok := extractBearer(r)
			if !ok {
				// No token → anonymous; proceed without identity.
				next.ServeHTTP(w, r)
				return
			}
			// Token present but invalid/expired → 401 (never silent downgrade).
			identity, err := v.Verify(tokenStr)
			if err != nil {
				writeAuthError(w, errs, err)
				return
			}
			next.ServeHTTP(w, reqctx.SetCustomerIdentity(r, identity))
		})
	}
}

func extractBearer(r *http.Request) (string, bool) {
	h := strings.TrimSpace(r.Header.Get("Authorization"))
	if !strings.HasPrefix(h, "Bearer ") {
		return "", false
	}
	return strings.TrimSpace(strings.TrimPrefix(h, "Bearer ")), true
}

func writeAuthError(w http.ResponseWriter, errs *httpx.Helper, err error) {
	switch {
	case errors.Is(err, ErrTokenExpired):
		errs.Unauthorized(w, "token_expired", "token has expired")
	case errors.Is(err, ErrInsufficientScope):
		errs.Forbidden(w, "insufficient_scope", "token lacks required scope")
	default:
		errs.Unauthorized(w, "invalid_token", "token is invalid")
	}
}
```

- [ ] **Step 4: Run tests**

```bash
cd platform-new/ecom-gateway && go test ./internal/platform/authn/...
```

Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add internal/platform/authn/middleware.go internal/platform/authn/middleware_test.go
git commit -m "feat(authn): Guards — RequireAuth / OptionalAuth / passthrough; IDOR test"
```

---

### Task 6: config — CustomerAuth section

**Files:**
- Modify: `internal/platform/config/config.go`
- Modify: `internal/platform/config/config_test.go`

- [ ] **Step 1: Write failing tests**

Append to `internal/platform/config/config_test.go` (file already exists; add imports `"os"` if missing — check first):

```go
func TestConfig_CustomerAuth_LoadsFromEnv(t *testing.T) {
	t.Setenv("CUSTOMER_AUTH_PUBLIC_KEY", "-----BEGIN PUBLIC KEY-----\nfake\n-----END PUBLIC KEY-----")
	t.Setenv("CUSTOMER_AUTH_ISSUER", "https://auth.example.com")
	t.Setenv("CUSTOMER_AUTH_AUDIENCE", "ecom-gateway")
	cfg := Load()
	if cfg.CustomerAuth.Issuer != "https://auth.example.com" {
		t.Fatalf("Issuer: want %q, got %q", "https://auth.example.com", cfg.CustomerAuth.Issuer)
	}
	if cfg.CustomerAuth.Audience != "ecom-gateway" {
		t.Fatalf("Audience: want ecom-gateway, got %q", cfg.CustomerAuth.Audience)
	}
	if !cfg.CustomerAuth.IsConfigured() {
		t.Fatal("want IsConfigured=true")
	}
}

func TestConfig_CustomerAuth_IssuerWithoutKey_FailsValidation(t *testing.T) {
	t.Setenv("CUSTOMER_AUTH_ISSUER", "https://auth.example.com")
	t.Setenv("CUSTOMER_AUTH_PUBLIC_KEY", "")
	t.Setenv("CUSTOMER_AUTH_PUBLIC_KEY_FILE", "")
	cfg := Load()
	if err := cfg.Validate(); err == nil {
		t.Fatal("expected validation error when issuer set without public key")
	}
}

func TestConfig_CustomerAuth_KeyWithoutIssuer_FailsValidation(t *testing.T) {
	t.Setenv("CUSTOMER_AUTH_PUBLIC_KEY", "-----BEGIN PUBLIC KEY-----\nfake\n-----END PUBLIC KEY-----")
	t.Setenv("CUSTOMER_AUTH_ISSUER", "")
	cfg := Load()
	if err := cfg.Validate(); err == nil {
		t.Fatal("expected validation error when public key set without issuer")
	}
}

func TestConfig_CustomerAuth_AllEmpty_IsUnconfigured(t *testing.T) {
	t.Setenv("CUSTOMER_AUTH_PUBLIC_KEY", "")
	t.Setenv("CUSTOMER_AUTH_PUBLIC_KEY_FILE", "")
	t.Setenv("CUSTOMER_AUTH_ISSUER", "")
	t.Setenv("CUSTOMER_AUTH_AUDIENCE", "")
	cfg := Load()
	if err := cfg.Validate(); err != nil {
		t.Fatalf("unconfigured auth must not fail validation: %v", err)
	}
	if cfg.CustomerAuth.IsConfigured() {
		t.Fatal("want IsConfigured=false when all fields empty")
	}
}
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd platform-new/ecom-gateway && go test ./internal/platform/config/...
```

Expected: `FAIL` — `cfg.CustomerAuth` field undefined, `IsConfigured` undefined.

- [ ] **Step 3: Implement**

In `internal/platform/config/config.go`:

**3a.** Add `CustomerAuthConfig` struct and `IsConfigured` method after the existing config types:

```go
// CustomerAuthConfig configures customer-Bearer JWT validation at the north-south edge.
// When all fields are empty, auth is unconfigured and guards fall back to passthrough.
type CustomerAuthConfig struct {
	PublicKeyPEM string // RSA public key in PKIX PEM format ("PUBLIC KEY" block)
	Issuer       string // expected "iss" claim (e.g. Passport base URL)
	Audience     string // expected "aud" claim (e.g. Passport client_id)
}

// IsConfigured reports whether customer auth is configured.
func (c CustomerAuthConfig) IsConfigured() bool { return c.Issuer != "" }
```

**3b.** Add `CustomerAuth CustomerAuthConfig` field to `Config` struct.

**3c.** In `Load()`, add to the returned `Config{}` literal:

```go
CustomerAuth: CustomerAuthConfig{
    PublicKeyPEM: loadCustomerAuthKey(),
    Issuer:       getEnv("CUSTOMER_AUTH_ISSUER", ""),
    Audience:     getEnv("CUSTOMER_AUTH_AUDIENCE", ""),
},
```

**3d.** Add helper function (after `clampInt`):

```go
func loadCustomerAuthKey() string {
	if v := os.Getenv("CUSTOMER_AUTH_PUBLIC_KEY"); v != "" {
		return v
	}
	if path := os.Getenv("CUSTOMER_AUTH_PUBLIC_KEY_FILE"); path != "" {
		if data, err := os.ReadFile(path); err == nil {
			return string(data)
		}
	}
	return ""
}
```

**3e.** In `Validate()`, add after the existing hydrator checks:

```go
if c.CustomerAuth.Issuer != "" && c.CustomerAuth.PublicKeyPEM == "" {
    return fmt.Errorf("config: CUSTOMER_AUTH_ISSUER requires CUSTOMER_AUTH_PUBLIC_KEY or CUSTOMER_AUTH_PUBLIC_KEY_FILE")
}
if c.CustomerAuth.PublicKeyPEM != "" && c.CustomerAuth.Issuer == "" {
    return fmt.Errorf("config: CUSTOMER_AUTH_PUBLIC_KEY requires CUSTOMER_AUTH_ISSUER")
}
```

- [ ] **Step 4: Run tests**

```bash
cd platform-new/ecom-gateway && go test ./internal/platform/config/...
```

Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add internal/platform/config/
git commit -m "feat(config): CustomerAuthConfig — public key + issuer + audience from env"
```

---

### Task 7: Wire auth into container and transport

**Files:**
- Modify: `internal/app/container.go`
- Modify: `internal/app/app.go`
- Modify: `internal/platform/transport/routes.go`

No new test files — covered by the existing and new unit tests. Verify with build + full test run.

- [ ] **Step 1: Update container.go**

In `internal/app/container.go`:

**1a.** Add import `"gj-ecom-gateway/internal/platform/authn"` and `"fmt"`.

**1b.** Add `AuthGuards *authn.Guards` field to `Container`.

**1c.** Change `NewContainer` to return `(*Container, error)` and wire auth:

```go
func NewContainer(cfg config.Config) (*Container, error) {
	c := &Container{Config: cfg}

	c.Metrics = observability.NewMetrics()
	c.ErrorsHelper = httpx.NewHelper()
	c.HealthHandler = health.NewHandler(health.NewService(cfg.AppName, cfg.Env, nil))
	c.RecommendationsHandler = wire.Recommendations(cfg, c.Metrics, c.ErrorsHelper)

	if cfg.CustomerAuth.IsConfigured() {
		v, err := authn.NewVerifier(
			cfg.CustomerAuth.PublicKeyPEM,
			cfg.CustomerAuth.Issuer,
			cfg.CustomerAuth.Audience,
		)
		if err != nil {
			return nil, fmt.Errorf("authn verifier: %w", err)
		}
		c.AuthGuards = authn.NewGuards(v, c.ErrorsHelper)
	} else {
		c.AuthGuards = authn.NewPassthroughGuards()
	}

	return c, nil
}
```

- [ ] **Step 2: Update app.go**

In `internal/app/app.go`, update the `NewContainer` call to handle the error and pass `AuthDeps`:

Change:
```go
container := NewContainer(cfg)
```
To:
```go
container, err := NewContainer(cfg)
if err != nil {
    return nil, fmt.Errorf("container: %w", err)
}
```

Change the `transport.NewServer` call to include `Auth`:
```go
server := transport.NewServer(cfg, transport.Dependencies{
    Auth:          transport.AuthDeps{Guards: container.AuthGuards},
    Health:        health.Deps{Handler: container.HealthHandler},
    Observability: observability.Deps{Metrics: container.Metrics},
    Recommendations: recommendations.Deps{
        Handler: container.RecommendationsHandler,
    },
})
```

- [ ] **Step 3: Update transport/routes.go**

Replace the entire contents of `internal/platform/transport/routes.go` with:

```go
package transport

import (
	"gj-ecom-gateway/internal/domains/recommendations"
	"gj-ecom-gateway/internal/platform/authn"
	"gj-ecom-gateway/internal/platform/health"
	"gj-ecom-gateway/internal/platform/observability"

	"github.com/go-chi/chi/v5"
)

// AuthDeps carries the per-tier guards for the router.
type AuthDeps struct {
	Guards *authn.Guards
}

// Dependencies holds per-domain Deps consumed by registerRoutes.
type Dependencies struct {
	Auth            AuthDeps
	Health          health.Deps
	Observability   observability.Deps
	Recommendations recommendations.Deps
}

// registerRoutes mounts observability first (so /metrics is always reachable
// and the instrumentation middleware wraps everything after), then health, then
// the versioned API group.
func registerRoutes(r chi.Router, deps Dependencies) {
	observability.Mount(r, deps.Observability)
	health.Mount(r, deps.Health)

	r.Route("/api/v1", func(rr chi.Router) {
		// Recommendations: auth-optional — enriches response when token is present;
		// serves anonymous / guest requests without a token.
		rr.Group(func(gr chi.Router) {
			gr.Use(deps.Auth.Guards.OptionalAuth)
			recommendations.Mount(gr, deps.Recommendations)
		})
	})
}
```

- [ ] **Step 4: Build and test**

```bash
cd platform-new/ecom-gateway && go build ./... && go test ./...
```

Expected: all tests `PASS`, no build errors.

- [ ] **Step 5: Commit**

```bash
git add internal/app/container.go internal/app/app.go internal/platform/transport/routes.go
git commit -m "feat(wire): thread AuthGuards through container → transport; OptionalAuth on recommendations"
```

---

### Task 8: Propagate X-Customer-Id downstream + tighten boundary test

**Files:**
- Modify: `internal/app/wire/recommendations.go`
- Modify: `internal/domains/recommendations/boundary_test.go`

- [ ] **Step 1: Update wire/recommendations.go**

In `internal/app/wire/recommendations.go`, update the `WithRequestDecorator` call:

Change:
```go
httpclient.WithRequestDecorator(func(ctx context.Context, r *http.Request) {
    if id := reqctx.RequestIDFromContext(ctx); id != "" {
        r.Header.Set("X-Request-ID", id)
    }
}),
```

To:
```go
httpclient.WithRequestDecorator(func(ctx context.Context, r *http.Request) {
    if id := reqctx.RequestIDFromContext(ctx); id != "" {
        r.Header.Set("X-Request-ID", id)
    }
    reqctx.PropagateCustomerID(ctx, r)
}),
```

- [ ] **Step 2: Update boundary_test.go**

In `internal/domains/recommendations/boundary_test.go`, add `"gj-ecom-gateway/internal/platform/authn"` to the `forbiddenPrefixes` slice:

Change:
```go
forbiddenPrefixes := []string{
    "gj-ecom-gateway/internal/app",
    "gj-ecom-gateway/internal/platform/config",
    "gj-ecom-gateway/internal/platform/health",
    "gj-ecom-gateway/internal/platform/logger",
    "gj-ecom-gateway/internal/platform/observability",
    "gj-ecom-gateway/internal/platform/transport",
    "gj-ecom-gateway/internal/domains",
    "gj-ecom-gateway/internal/adapters",
    "gitlab.gloria.aaanet.ru/e-commerce/platform/clients",
}
```

To:
```go
forbiddenPrefixes := []string{
    "gj-ecom-gateway/internal/app",
    "gj-ecom-gateway/internal/platform/config",
    "gj-ecom-gateway/internal/platform/authn",
    "gj-ecom-gateway/internal/platform/health",
    "gj-ecom-gateway/internal/platform/logger",
    "gj-ecom-gateway/internal/platform/observability",
    "gj-ecom-gateway/internal/platform/transport",
    "gj-ecom-gateway/internal/domains",
    "gj-ecom-gateway/internal/adapters",
    "gitlab.gloria.aaanet.ru/e-commerce/platform/clients",
}
```

- [ ] **Step 3: Run all tests**

```bash
cd platform-new/ecom-gateway && go test ./...
```

Expected: all `PASS`

- [ ] **Step 4: Commit**

```bash
git add internal/app/wire/recommendations.go internal/domains/recommendations/boundary_test.go
git commit -m "feat(wire): propagate X-Customer-Id to catalog-cache; forbid authn import from domains"
```

---

## Self-Review

### Spec coverage

| Requirement | Task |
|-------------|------|
| Валидация customer-Bearer (подпись, exp, iss/aud) | Task 4 |
| Извлечь `customer_id` из claim | Task 4 |
| Identity propagation — reqctx + `X-Customer-Id` downstream | Tasks 2, 7, 8 |
| Три тира guard: public / optional / required | Tasks 5, 7 |
| "нет токена" ≠ "битый токен": optional + expired → 401 | Task 5 test `TestOptionalAuth_ExpiredToken_Returns401` |
| Anti-IDOR: customer_id только из токена | Task 5 test `TestRequireAuth_AntiIDOR` |
| Единый envelope 401/403 | Tasks 3, 5 |
| Auth не configured → passthrough (local dev) | Tasks 5, 6, 7 |
| Сетевая изоляция (инфра) | ADR Task 1 |
| ADR: local vs remote + login-флоу + нужен ли auth-client | Task 1 |

### DoD check

- Protected endpoint (RequireAuth): no token → 401 ✅ · invalid/expired → 401 ✅ · valid → identity in reqctx ✅
- customer_id только из токена, тест на IDOR ✅
- Guards конфигурируемы per-route через `deps.Auth.Guards.{Require,Optional}Auth` ✅
- Гостевые ручки (OptionalAuth без токена) работают ✅
- Тесты: valid / invalid / expired / missing / guest / scope-fail / IDOR ✅
- ADR зафиксирован ✅
- Инфра-изоляция задокументирована в ADR ✅
