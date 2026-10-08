---
name: SKILL
version: 1.0.0
layer: integration-php-conventions
platform: Generic
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---


# Integration Service PHP Conventions

Code lives in `platform/integration/integration/www/`. Stack: PHP + Lumen.

## Lumen vs full Laravel — important differences

Lumen is a stripped-down Laravel. Before using a Laravel feature, verify it works in Lumen. Common gotchas:

| Feature | Status in Lumen |
|---------|----------------|
| Routing | Different syntax — uses `$router->get(...)` in `routes/web.php` style |
| Eloquent | Available but not auto-enabled — must be uncommented in `bootstrap/app.php` |
| Facades | Disabled by default — must call `$app->withFacades()` |
| Blade | Disabled by default — call `$app->withEloquent()` and `$app->withFacades()` separately; Blade requires extra setup |
| Middleware | Different registration in `bootstrap/app.php` |
| Validation | `$this->validate($request, [...])` works in Controllers; FormRequests are NOT supported the same way |
| Sessions | Not enabled by default |
| Mail | Not auto-configured |
| Queues | Available but with reduced driver set |
| Service container | Yes, full DI works |
| Service providers | Yes |

**Rule:** before importing a `Illuminate\<...>\Facades\<X>`, grep for it in existing code or check `bootstrap/app.php` to confirm it's enabled.

## Internal lib usage

The repo composer.json depends on these (probably via VCS or path repos):

| Lib | Use for |
|-----|---------|
| `logger` | All logging — wraps Monolog with Gloria conventions. Don't `use Monolog\Logger` directly. |
| `msq-client` | Publishing to or consuming from the message queue. Has DB migrations (queue state). |
| `health` | Health/readiness endpoints — k8s probes consume these. |

Before importing a third-party lib that does similar — check if the internal lib covers it.

## File layout conventions

| Type | Where |
|------|-------|
| HTTP Controller | `www/app/Http/Controllers/` |
| Middleware | `www/app/Http/Middleware/` |
| Console Command (cron / one-off) | `www/app/Console/Commands/` |
| Service / business logic | `www/app/Services/` or `app/Domain/` (check existing) |
| Job (queue) | `www/app/Jobs/` |
| Listener | `www/app/Listeners/` |
| Event | `www/app/Events/` |
| Model (Eloquent) | `www/app/Models/` |
| Provider | `www/app/Providers/` |
| Config | `www/config/<name>.php` (return array) |
| Migration | `www/database/migrations/` |
| Route | `www/routes/<file>.php` |

Always grep existing code for analogous patterns before deciding placement.

## Composer

- Run `composer install` inside the dev container (or whatever the project uses for local PHP), not on host
- For internal libs (logger/msq-client/health) — if they're path repos in composer.json, modifying them locally takes effect immediately
- Composer scripts: check `composer.json` `scripts` section for `lint`, `test`, `analyse`

## Static analysis (phpstan)

- Config: `www/phpstan.neon`
- Run: `vendor/bin/phpstan analyse` (from `www/`)
- Don't lower the level to suppress errors — fix the type
- For unavoidable issues: use `// @phpstan-ignore-next-line` with a comment explaining why

## Tests (phpunit)

- Config: `www/phpunit.xml`
- Run: `vendor/bin/phpunit` (from `www/`)
- Test layout: `www/tests/<Unit|Feature|Integration>/`
- For feature tests of HTTP endpoints — use Lumen's `$this->json()` / `$this->call()` helpers
- For DB tests — use migrations + transactions (rollback after each test)

## Code style

- PSR-12 (modern PHP standard)
- Strict types: `declare(strict_types=1);` at the top of new files
- Type hints on params and return types — phpstan will complain if missing
- Constructor property promotion (PHP 8.0+) where it makes sense
- Readonly properties (PHP 8.1+) for value objects

## Logging pattern

```php
use Integration\Logger\Logger; // verify exact namespace

$logger = $this->app->make(Logger::class); // or via DI
$logger->info('Checkout started', ['orderId' => $id, 'userId' => $user->id]);
```

Use **structured logging** (context array) — filebeat/Elasticsearch can index keys.

## Message queue pattern

```php
use Integration\MsqClient\Publisher;

$publisher->publish('order.checkout.completed', [
    'orderId' => $id,
    'timestamp' => now()->toIso8601String(),
]);
```

Check `msq-client/src/` for the actual API before using. The lib persists state in DB — so publishing also commits an outbox row (or similar).

## Anti-patterns

- Importing Laravel features not enabled in Lumen without checking
- Using `DB::raw(...)` for SQL when Eloquent / query builder works
- Writing custom Monolog setup when `logger` lib is available
- Adding `vendor/` patches via fork — use composer scripts or pre/post-install hooks instead
- Mixing concerns in a Controller — push business logic to a Service
- Adding tests without running them

## Verification

Before declaring a PHP change done:
1. `composer install` clean (no warnings)
2. `vendor/bin/phpstan analyse` passes
3. `vendor/bin/phpunit --filter <relevant>` passes
4. Manually verify the endpoint or command runs (curl / artisan invoke) if you can

## Development workflow

Follow **`pattern-development-integration.md`** for the 7-step structured development cycle: understanding, planning, implementation, security checks, testing, commit, and merge request. This skill provides the coding conventions; the pattern guides the overall workflow.

## When to escalate

- Where to find / structure decisions → `integration-navigator`
- Deployment / container changes → `integration-deployment` skill
- Cross-system contract changes → `architect`
- Production errors → `logs-detective`
