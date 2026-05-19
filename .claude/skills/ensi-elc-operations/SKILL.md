---
name: ensi-elc-operations
description: Use when running ENSI services locally — starting/stopping containers, executing commands inside service containers (composer, artisan, npm), managing the elc workspace. Triggers on requests like "start the catalog services", "run migrations", "composer install in pim", "what's the elc command for X".
---

# ENSI ELC Operations

`elc` (ENSI Local Containers) is the CLI tool that orchestrates Docker containers for local development. The workspace is registered as `gj` → `<workspace>/platform/ensi/workspace`.

## Workspace registration (one-time / verification)

```bash
elc workspace list          # should show: gj <workspace>/platform/ensi/workspace
elc workspace show          # current selected workspace
elc workspace select gj     # if needed
```

If `gj` is missing or wrong:
```bash
elc workspace add gj <workspace>/platform/ensi/workspace
```

## Common operations

### Start / stop services

```bash
# Start everything tagged 'backend' (recommended for development)
elc -w gj start --tag=backend

# Start one service (resolves its dependencies: database, proxy, ...)
elc -w gj start catalog-pim

# Start by mode (deps profile)
elc -w gj start --mode=dev

# Stop all
elc -w gj stop

# Restart
elc -w gj restart

# Wipe containers + volumes (DESTRUCTIVE — confirm with user first)
elc -w gj destroy
```

### Execute commands inside a container

```bash
# Composer in PIM
elc -w gj -c catalog-pim exec composer install
elc -w gj -c catalog-pim exec composer test
elc -w gj -c catalog-pim exec composer lint

# Laravel artisan
elc -w gj -c catalog-pim exec php artisan migrate
elc -w gj -c catalog-pim exec php artisan tinker

# Direct shell
elc -w gj -c catalog-pim exec sh

# Database psql (component is 'database')
elc -w gj -c database exec psql -U postgres
```

### Multiple services with tag

```bash
# Run composer install for everything tagged 'backend'
elc -w gj --tag=backend exec composer install
```

### Git hooks (run inside container)

```bash
# Set up hooks for a service (one-time per repo)
elc -w gj -c catalog-pim set-hooks ./hooks-dir
```

## Modes (deps profiles) in workspace.yaml

| Mode | Includes |
|------|----------|
| `dev` (default) | database, proxy + the requested service |
| `hook` | minimal deps to run git hooks |

(Check `workspace.yaml` for current mode definitions — they evolve.)

## Tags in workspace.yaml

| Tag | Services |
|-----|----------|
| `backend` | All PHP backend services |
| `app` | All apps (frontend + backend) |
| `code` | Apps with source code (excludes infra-only) |

## Service short list

Use these names with `-c <name>`:
- `catalog-pim`, `catalog-offers`, `catalog-feed`, `catalog-catalog-cache`
- `cms-cms`
- `customers-customers`, `customers-customer-auth`
- `customers-api-web`
- `orders-baskets`
- `units-admin-auth`, `units-bu`
- `admin-gui-backend`, `admin-gui-frontend`
- `connectors-webapi-connector`, `connectors-cdn-adapter`, `connectors-ensi-connector`, `connectors-audit`
- Infra: `proxy`, `database`, `es`, `elastic`, `kibana`, `redis`, `redis-ui`, `kafka`, `kafka-ui`

## Domain access

Services are exposed on `*.gj.127.0.0.1.nip.io`. Examples:
- `http://catalog-pim.gj.127.0.0.1.nip.io`
- `http://kibana.gj.127.0.0.1.nip.io`
- `http://kafka-ui.gj.127.0.0.1.nip.io`
- `http://admin-gui-frontend.gj.127.0.0.1.nip.io`

## Anti-patterns

- Running `php artisan migrate` on host — Laravel won't connect to containerized DB. Always `elc -c <svc> exec ...`.
- `docker compose` manually — bypasses elc state, breaks on subsequent `elc` calls.
- `elc destroy` without explicit user confirmation — destroys volumes (data loss).

## Troubleshooting

| Problem | Try |
|---------|-----|
| Container won't start | `elc -w gj logs <name>` |
| Port already in use | `lsof -i :<port>` then stop the offender |
| Stale containers | `elc -w gj destroy && elc -w gj start <name>` (confirm first!) |
| `elc workspace list` wrong | Re-add: `elc workspace remove gj && elc workspace add gj <workspace>/platform/ensi/workspace` |
| Permission errors inside container | Check `GROUP_ID`/`USER_ID` vars in `env.yaml` |
