# Auth Fix: Real Passport JWT Claims

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix ecom-gateway JWT verifier and config to accept real Laravel Passport tokens (no `iss`, identity from `sub`, optional `aud`).

**Architecture:** Surgical changes to 2 platform packages — `authn` (verify logic) and `config` (activation logic). `middleware.go` and `reqctx` are NOT touched. After the fix: public key alone activates auth; `iss`/`aud` are enforced only when configured; identity = `claims.Subject`.

**Tech Stack:** Go · `github.com/golang-jwt/jwt/v5` · stdlib `testing`

**Service dir:** `platform-new/ecom-gateway/` · **Module:** `gj-ecom-gateway`

---

## What changes (and what doesn't)

| File | Change |
|---|---|
| `internal/platform/authn/jwt.go` | Remove `CustomerID` from passportClaims; use `claims.Subject` for identity; make `WithIssuer`/`WithAudience` conditional |
| `internal/platform/authn/jwt_test.go` | Update fixtures (sub→identity, no customer_id); add float-timestamp, no-iss/aud, empty-sub cases |
| `internal/platform/authn/middleware_test.go` | Update `makeToken` call sites (customerID param → sub) |
| `internal/platform/config/config.go` | `IsConfigured()` → key-based; remove 2 broken validations |
| `internal/platform/config/config_test.go` | Remove 2 obsolete tests; add key-alone-is-configured test |
| `middleware.go`, `reqctx.go`, `container.go` | **NOT touched** |

---

### Task 1: Fix authn/jwt.go — real Passport claims

**Files:**
- Modify: `internal/platform/authn/jwt.go`
- Modify: `internal/platform/authn/jwt_test.go`
- Modify: `internal/platform/authn/middleware_test.go`

- [ ] **Step 1: Update jwt_test.go — replace failing test fixtures**

Replace the entire `internal/platform/authn/jwt_test.go` with:

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

// makeTestVerifier builds a strict verifier (enforces issuer + audience).
// Use makeMinimalVerifier for a verifier that accepts any iss/aud.
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

// makeMinimalVerifier builds a verifier with no issuer/audience enforcement.
// Mirrors real Passport deployments where iss is absent.
func makeMinimalVerifier(t *testing.T) (*Verifier, *rsa.PrivateKey) {
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
	v, err := NewVerifier(pubPEM, "", "") // no iss, no aud enforcement
	if err != nil {
		t.Fatalf("NewVerifier: %v", err)
	}
	return v, priv
}

// makeToken builds a signed RS256 JWT. issuer and audience are optional:
// empty string → field omitted from the token (matches real Passport behaviour).
// sub is the customer identity (claims.Subject).
func makeToken(t *testing.T, priv *rsa.PrivateKey, sub string, exp time.Time, issuer, audience string) string {
	t.Helper()
	rc := jwt.RegisteredClaims{
		Subject:   sub,
		ExpiresAt: jwt.NewNumericDate(exp),
		IssuedAt:  jwt.NewNumericDate(time.Now().Add(-time.Second)),
	}
	if issuer != "" {
		rc.Issuer = issuer
	}
	if audience != "" {
		rc.Audience = jwt.ClaimStrings{audience}
	}
	claims := passportClaims{
		RegisteredClaims: rc,
		Scopes:           []string{},
	}
	tok := jwt.NewWithClaims(jwt.SigningMethodRS256, claims)
	signed, err := tok.SignedString(priv)
	if err != nil {
		t.Fatalf("sign token: %v", err)
	}
	return signed
}

// makeTokenWithFloatTimestamps builds a JWT with float iat/nbf/exp like real Passport tokens.
func makeTokenWithFloatTimestamps(t *testing.T, priv *rsa.PrivateKey, sub string) string {
	t.Helper()
	futureExp := float64(time.Now().Add(time.Hour).Unix()) + 0.182551
	nowIat := float64(time.Now().Unix()) + 0.182554
	claims := jwt.MapClaims{
		"sub":    sub,
		"exp":    futureExp,
		"iat":    nowIat,
		"nbf":    nowIat,
		"scopes": []string{},
	}
	tok := jwt.NewWithClaims(jwt.SigningMethodRS256, claims)
	signed, err := tok.SignedString(priv)
	if err != nil {
		t.Fatalf("sign float-ts token: %v", err)
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
	// Strict verifier (enforces issuer + audience)
	vStrict, privStrict := makeTestVerifier(t)

	// Minimal verifier (no iss/aud enforcement — mirrors real Passport)
	vMinimal, privMinimal := makeMinimalVerifier(t)

	otherKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatalf("rsa.GenerateKey: %v", err)
	}

	future := time.Now().Add(time.Hour)
	past := time.Now().Add(-time.Hour)

	tests := []struct {
		name       string
		verifier   *Verifier
		token      string
		wantCustID string
		wantErr    error
	}{
		// --- Strict verifier ---
		{
			name:       "strict: valid token with iss+aud",
			verifier:   vStrict,
			token:      makeToken(t, privStrict, "4455421", future, "https://auth.example.com", "ecom-gateway"),
			wantCustID: "4455421",
		},
		{
			name:     "strict: expired",
			verifier: vStrict,
			token:    makeToken(t, privStrict, "4455421", past, "https://auth.example.com", "ecom-gateway"),
			wantErr:  ErrTokenExpired,
		},
		{
			name:     "strict: wrong signing key",
			verifier: vStrict,
			token:    makeToken(t, otherKey, "4455421", future, "https://auth.example.com", "ecom-gateway"),
			wantErr:  ErrTokenInvalid,
		},
		{
			name:     "strict: wrong issuer",
			verifier: vStrict,
			token:    makeToken(t, privStrict, "4455421", future, "https://wrong.example.com", "ecom-gateway"),
			wantErr:  ErrTokenInvalid,
		},
		{
			name:     "strict: wrong audience",
			verifier: vStrict,
			token:    makeToken(t, privStrict, "4455421", future, "https://auth.example.com", "other-service"),
			wantErr:  ErrTokenInvalid,
		},
		{
			name:     "strict: empty sub",
			verifier: vStrict,
			token:    makeToken(t, privStrict, "", future, "https://auth.example.com", "ecom-gateway"),
			wantErr:  ErrTokenInvalid,
		},
		{
			name:    "strict: empty string",
			verifier: vStrict,
			token:   "",
			wantErr: ErrTokenInvalid,
		},
		{
			name:    "strict: garbage",
			verifier: vStrict,
			token:   "not.a.jwt",
			wantErr: ErrTokenInvalid,
		},
		// --- Minimal verifier (no iss/aud enforcement — real Passport style) ---
		{
			name:       "minimal: valid token without iss/aud",
			verifier:   vMinimal,
			token:      makeToken(t, privMinimal, "4455421", future, "", ""),
			wantCustID: "4455421",
		},
		{
			name:     "minimal: expired",
			verifier: vMinimal,
			token:    makeToken(t, privMinimal, "4455421", past, "", ""),
			wantErr:  ErrTokenExpired,
		},
		{
			name:     "minimal: empty sub",
			verifier: vMinimal,
			token:    makeToken(t, privMinimal, "", future, "", ""),
			wantErr:  ErrTokenInvalid,
		},
		{
			name:       "minimal: float timestamps (real Passport)",
			verifier:   vMinimal,
			token:      makeTokenWithFloatTimestamps(t, privMinimal, "4455421"),
			wantCustID: "4455421",
		},
		// --- Strict verifier rejects tokens missing iss when configured ---
		{
			name:     "strict: token without iss rejected when verifier enforces iss",
			verifier: vStrict,
			token:    makeToken(t, privStrict, "4455421", future, "", "ecom-gateway"),
			wantErr:  ErrTokenInvalid,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			id, err := tc.verifier.Verify(tc.token)
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

- [ ] **Step 2: Update middleware_test.go — fix makeToken call sites**

In `internal/platform/authn/middleware_test.go`, `makeToken` is called with a `customerID` string that was the `customer_id` claim. This parameter is now the JWT `sub` field instead. The call signatures stay the same (same argument order), just the semantics change. No code change needed in `middleware_test.go` — the parameter was named `"cust-42"` and `"cust-99"`, which is now used as `sub`. Verify the file compiles after jwt.go is updated.

- [ ] **Step 3: Run tests to confirm they FAIL**

```bash
cd platform-new/ecom-gateway && go test ./internal/platform/authn/... 2>&1
```

Expected: compile errors — `claims.CustomerID` undefined or similar.

- [ ] **Step 4: Implement the fix in jwt.go**

Replace the entire `internal/platform/authn/jwt.go` with:

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
// issuer and audience are optional — empty string disables enforcement.
// Real Laravel Passport tokens do NOT include an iss claim; customer identity
// is carried in the standard sub (Subject) claim.
type Verifier struct {
	publicKey *rsa.PublicKey
	issuer    string // empty → not enforced
	audience  string // empty → not enforced
}

// passportClaims extends RegisteredClaims with Laravel Passport fields.
// Identity is in RegisteredClaims.Subject; customer_id custom claim is absent.
type passportClaims struct {
	jwt.RegisteredClaims
	Scopes []string `json:"scopes"`
}

// NewVerifier parses publicKeyPEM (PKIX/SPKI "PUBLIC KEY" PEM block).
// issuer and audience are optional enforcement options — pass "" to disable.
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
// Identity is taken from the sub (Subject) claim. Returns ErrTokenExpired for
// expired tokens, ErrTokenInvalid for all other failures.
func (v *Verifier) Verify(tokenStr string) (reqctx.CustomerIdentity, error) {
	opts := []jwt.ParserOption{
		jwt.WithExpirationRequired(),
	}
	if v.issuer != "" {
		opts = append(opts, jwt.WithIssuer(v.issuer))
	}
	if v.audience != "" {
		opts = append(opts, jwt.WithAudience(v.audience))
	}

	var claims passportClaims
	_, err := jwt.ParseWithClaims(tokenStr, &claims,
		func(t *jwt.Token) (interface{}, error) {
			if _, ok := t.Method.(*jwt.SigningMethodRSA); !ok {
				return nil, fmt.Errorf("unexpected signing method: %v", t.Header["alg"])
			}
			return v.publicKey, nil
		},
		opts...,
	)
	if err != nil {
		if errors.Is(err, jwt.ErrTokenExpired) {
			return reqctx.CustomerIdentity{}, ErrTokenExpired
		}
		return reqctx.CustomerIdentity{}, ErrTokenInvalid
	}
	if claims.Subject == "" {
		return reqctx.CustomerIdentity{}, ErrTokenInvalid
	}
	return reqctx.CustomerIdentity{
		CustomerID: claims.Subject,
		Scopes:     claims.Scopes,
	}, nil
}
```

- [ ] **Step 5: Run tests — must pass**

```bash
cd platform-new/ecom-gateway && go test ./internal/platform/authn/... -v 2>&1 | tail -30
```

Expected: all tests PASS (14+ subtests of TestVerifier_Verify + middleware tests).

- [ ] **Step 6: Commit**

```bash
cd platform-new/ecom-gateway && git add internal/platform/authn/ && git commit -m "fix(authn): real Passport claims — sub as identity, optional iss/aud enforcement"
```

---

### Task 2: Fix config.go — key-based auth activation

**Files:**
- Modify: `internal/platform/config/config.go`
- Modify: `internal/platform/config/config_test.go`

- [ ] **Step 1: Write failing tests**

In `internal/platform/config/config_test.go`, make these changes:

**Remove** the following two test functions (they test the old "key requires issuer" and "issuer requires audience" validations that are being removed):
- `TestConfig_CustomerAuth_KeyWithoutIssuer_FailsValidation`
- `TestConfig_CustomerAuth_IssuerWithoutAudience_FailsValidation`

**Add** the following new test function:

```go
func TestConfig_CustomerAuth_KeyAloneIsConfigured(t *testing.T) {
	t.Setenv("CUSTOMER_AUTH_PUBLIC_KEY", "-----BEGIN PUBLIC KEY-----\nfake\n-----END PUBLIC KEY-----")
	t.Setenv("CUSTOMER_AUTH_ISSUER", "")
	t.Setenv("CUSTOMER_AUTH_AUDIENCE", "")
	cfg := Load()
	if err := cfg.Validate(); err != nil {
		t.Fatalf("key-only config must pass validation, got: %v", err)
	}
	if !cfg.CustomerAuth.IsConfigured() {
		t.Fatal("want IsConfigured=true when public key is set, even without issuer/audience")
	}
}
```

- [ ] **Step 2: Run tests to confirm fail**

```bash
cd platform-new/ecom-gateway && go test ./internal/platform/config/... -run TestConfig_CustomerAuth 2>&1
```

Expected: `FAIL` — `TestConfig_CustomerAuth_KeyAloneIsConfigured` fails because `IsConfigured()` currently checks `Issuer != ""`.

- [ ] **Step 3: Implement fixes in config.go**

In `internal/platform/config/config.go`:

**3a.** Change `IsConfigured()`:

```go
// IsConfigured reports whether customer auth is configured.
// Auth is activated by the presence of a public key alone;
// issuer and audience are optional enforcement options.
func (c CustomerAuthConfig) IsConfigured() bool { return c.PublicKeyPEM != "" }
```

**3b.** In `Validate()`, remove these two checks:
```go
// REMOVE this block:
if c.CustomerAuth.PublicKeyPEM != "" && c.CustomerAuth.Issuer == "" {
    return fmt.Errorf("config: CUSTOMER_AUTH_PUBLIC_KEY requires CUSTOMER_AUTH_ISSUER")
}
// REMOVE this block:
if c.CustomerAuth.Issuer != "" && c.CustomerAuth.Audience == "" {
    return fmt.Errorf("config: CUSTOMER_AUTH_ISSUER requires CUSTOMER_AUTH_AUDIENCE")
}
```

Keep the remaining check (issuer without key is still a misconfiguration):
```go
if c.CustomerAuth.Issuer != "" && c.CustomerAuth.PublicKeyPEM == "" {
    return fmt.Errorf("config: CUSTOMER_AUTH_ISSUER requires CUSTOMER_AUTH_PUBLIC_KEY or CUSTOMER_AUTH_PUBLIC_KEY_FILE")
}
```

- [ ] **Step 4: Run config tests — must pass**

```bash
cd platform-new/ecom-gateway && go test ./internal/platform/config/... 2>&1
```

Expected: all PASS.

- [ ] **Step 5: Run full suite**

```bash
cd platform-new/ecom-gateway && go test ./... 2>&1
```

Expected: all 16 packages PASS.

- [ ] **Step 6: Commit**

```bash
cd platform-new/ecom-gateway && git add internal/platform/config/ && git commit -m "fix(config): auth activated by public key alone — issuer/audience are optional"
```

---

## Self-Review

### Spec coverage
| Requirement | Task |
|---|---|
| `sub` → CustomerIdentity.CustomerID | Task 1 (jwt.go) |
| Remove `customer_id` from passportClaims | Task 1 (jwt.go) |
| `iss` enforcement only when configured | Task 1 (jwt.go) |
| `aud` enforcement only when configured | Task 1 (jwt.go) |
| RS256 + exp still required | Task 1 (kept in jwt.go) |
| Empty `sub` → ErrTokenInvalid | Task 1 (test + check) |
| Float timestamps parse OK | Task 1 (test) |
| Key alone → auth active | Task 2 (config) |
| Issuer+audience optional | Task 2 (config) |
| `middleware.go`/`reqctx` NOT touched | Both tasks |

### Verification
```bash
# After both tasks are merged, with stage key:
# CUSTOMER_AUTH_PUBLIC_KEY_FILE=/tmp/passport-stage.pub
# CUSTOMER_AUTH_ISSUER=  (empty)
# CUSTOMER_AUTH_AUDIENCE= (empty)

# 1. No token → 200 (anonymous)
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/v1/recommendations/similar?product_id=X

# 2. Garbage token → 401 invalid_token
curl -s -H "Authorization: Bearer garbage" http://localhost:8080/api/v1/recommendations/similar?product_id=X | jq .

# 3. Real stage token → 200, X-Customer-Id: 4455421 reaches downstream
# (verify via echo-server or gateway access log)
curl -s -H "Authorization: Bearer eyJ0eXAiOiJKV1Qi..." \
  http://localhost:8080/api/v1/recommendations/similar?product_id=X
```
