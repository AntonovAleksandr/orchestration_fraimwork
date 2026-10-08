---
name: SKILL
version: 1.0.0
layer: integration-deployment
platform: Generic
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---


# Integration Deployment

Integration ships as **two Docker containers from one codebase**:

| Container | Purpose | Built from |
|-----------|---------|-----------|
| `integration-api` | HTTP API (nginx + PHP-FPM) | `containers/integration-api/Dockerfile` |
| `integration-cron` | Scheduled jobs (cron + supervisor) | `containers/integration-cron/Dockerfile` |

## Container layouts

### `containers/integration-api/`
```
Dockerfile
nginx.conf            # nginx vhost — fastcgi_pass to php-fpm
php.ini               # PHP runtime config
php-fpm.conf          # FPM pool config
lumen.conf            # Lumen-specific runtime tweaks
supervisor-laravel.conf  # supervisor managing PHP-FPM + nginx + filebeat
filebeat.yml          # log shipping → ELK
filebeat-7.16.0-amd64.deb  # bundled filebeat binary
start.sh              # entrypoint — starts supervisor
README.md
JenkinsFile           # CI (legacy, possibly unused if .gitlab-ci.yml is canonical)
id_rsa                # ⚠️ ssh key — verify this isn't a real prod secret in repo
crontab-php           # may not be active in api container; legacy
```

### `containers/integration-cron/`
Similar layout but Dockerfile omits nginx; supervisor runs `cron + php artisan schedule:run` via `crontab-php`. Filebeat still ships logs.

## Boot order (typical)

`Dockerfile CMD` → `start.sh` → `supervisord -c /etc/supervisor/supervisor-laravel.conf`

Supervisor then starts:
- (api) `php-fpm`, `nginx`, `filebeat`
- (cron) `cron`, `filebeat`

## Common modifications

### Add a new env var
- Update `lumen.conf` or `.env.base` in `www/`
- If the value differs between deploys, set it in helm-values (not in repo)

### Change PHP memory limit / timeout
- `php.ini` in BOTH containers (api + cron)
- `php-fpm.conf` for FPM-level pool tuning (api only)

### Add a cron entry
- `containers/integration-cron/crontab-php` — add line:
  ```
  0 */1 * * * cd /var/www && php artisan command:name >> /var/log/cron.log 2>&1
  ```
- Ensure the command class exists in `www/app/Console/Commands/`
- Rebuild integration-cron, redeploy

### Add a route prefix or vhost rule
- `containers/integration-api/nginx.conf` (api only)

### Tune supervisor
- `supervisor-laravel.conf` in the relevant container

### Filebeat changes
- `filebeat.yml` — output to logstash/elastic
- Be careful with regex patterns — bad ones can lose logs

## Gotchas

- **Two Dockerfiles, easy to drift** — when changing PHP version or extensions, update BOTH api and cron Dockerfiles. Diff them periodically to catch drift.
- **filebeat binary is committed** (`filebeat-7.16.0-amd64.deb`) — large blob, harder to update; if you bump filebeat version, replace the .deb file.
- **`id_rsa` in repo** — if it's a real private key, that's a security issue. Verify (probably it's a deploy key or example). Don't commit secrets going forward.
- **`JenkinsFile` AND `.gitlab-ci.yml`** — likely Jenkins is legacy; GitLab CI is canonical. Check `.gitlab-ci.yml` for the actual build pipeline.

## How to verify deploy locally

These containers are built and run via the CI pipeline, but for local debugging:

```bash
# Build
cd platform/integration/integration
docker build -f containers/integration-api/Dockerfile -t integration-api:dev .
docker build -f containers/integration-cron/Dockerfile -t integration-cron:dev .

# Run (mounting code; production uses immutable image)
docker run --rm -p 8080:80 -v $PWD/www:/var/www integration-api:dev
docker run --rm -v $PWD/www:/var/www integration-cron:dev
```

Real production deploy → helm chart in `avg-integration-service/devops/helm-chart` (not cloned locally; use `mcp__gj-buddy__gitlab_get_repository_file` to inspect).

## Anti-patterns

- Editing only one Dockerfile when the change applies to both deploys
- Putting application logic in `containers/` (it's runtime config — code lives in `www/`)
- Hardcoding prod URLs/secrets in Dockerfile (use helm-values via env)
- Bypassing supervisor by adding processes directly in Dockerfile CMD

## Development workflow

For application code changes (vs deploy config), follow **`pattern-development-integration.md`** for the structured 7-step development cycle. This skill covers deployment infrastructure; the pattern guides development discipline and integration with the deployment model.

## When to escalate

- CI pipeline questions → `gitlab-investigator` (look at `.gitlab-ci.yml`, recent jobs)
- helm-chart / helm-values changes → these repos aren't cloned; use `mcp__gj-buddy__gitlab_get_repository_file`
- Production deploy strategy → `architect`
