---
name: site-nx-commands
description: Use when running, building, testing, generating, or scripting commands for the Gloria Jeans site. Covers npm scripts (start/dev/build), nx targets (serve/build/test/lint/storybook), generators (g @nx/angular:app/library), dependency graph, e2e (Cypress), and mocked API workflows.
---

# Site Nx Commands

All commands run from `platform/site/gj-ng-front/` (Nx workspace root).

## Setup

```bash
cd platform/site/gj-ng-front

# Volta will switch Node to 20.9.0 automatically if installed
node --version

# Install deps
npm install

# (Optional) install trusted certs for HTTPS dev
mkcert -install
mkcert localhost
# → puts localhost.pem and localhost-key.pem in repo root
```

## Day-to-day development

### Plain serve (no SSR, no mock)
```bash
npm run start          # site-ru on http://localhost:4200 (default)
npm run start:en       # site-en
npm run start:kz       # site-kz
```

### With mock API
```bash
npm run start:mock     # site-ru + mock API
npm run start:en:mock  # site-en + mock API
```

### With trusted HTTPS
```bash
npm run start:cert     # site-ru + mock + https
npm run start:en:cert
```

### SSR (Angular Universal via NestJS)
```bash
npm run dev            # site-ru SSR + mock
npm run dev:en
npm run dev:cert       # SSR + mock + https
npm run dev:en:cert

# Lower-level
npm run dev:ssr        # just SSR (RU)
npm run dev:en:ssr
npm run dev:kz:ssr
```

### Manual mock API only
```bash
npm run serve:api      # NestJS mock API standalone
```

## Builds

Each app × build-config combo has a script:

```bash
# RU
npm run build:site:ru:prod      # production build of site-ru (browser)
npm run build:server:ru:prod    # production build of site-ru SSR server
npm run build:api:prod          # mock API production build

npm run build:site:ru:stage     # staging
npm run build:site:ru:test      # testing
npm run build:site:ru:demo      # demo

# KZ — same set with :kz
npm run build:site:kz:prod
# (en builds aren't all present — check package.json)
```

Each build script first runs `npm run build:version` (regenerates build-version JSON via `tools/generators/generate-build-version.js`).

### Direct nx (more flexible)
```bash
nx build site-ru --configuration production
nx serve site-ru --configuration development
nx build site-ru-e2e
nx test site-ru
nx lint site-ru
nx stylelint site-ru
```

### HTML minification (post-build)
```bash
npm run minify:ru:html
npm run minify:kz:html
```

### Bundle analyzer
```bash
npm run analyze:site:ru:production
```

## Testing

### Unit tests (Jest)
```bash
npm run test:all        # all projects
npm run test:site       # site-ru
npm run test:core       # libs/core
npm run test:server     # libs/server

# Direct nx
nx test <project>
nx test <project> --watch
nx test <project> --coverage
```

### E2E (Cypress)
```bash
nx run site-ru-e2e:e2e
nx run site-en-e2e:e2e
nx run site-kz-e2e:e2e
```

## Linting & style

```bash
npm run lint:all              # eslint all projects
npm run lint:all:fix          # eslint + autofix
npm run stylelint:all         # SCSS/CSS

# Per-project
nx lint <project>
nx stylelint <project>
```

## Storybook

```bash
# Site-level storybook
npm run storybook
npm run storybook:build

# UI lib
npm run storybook:ui
npm run storybook:ui:build

# Shared lib
npm run storybook:shared
npm run storybook:shared:build
```

## Generators (creating new apps/libs)

```bash
# New Angular app
nx g @nx/angular:app <app_name>

# New Angular library
nx g @nx/angular:library <lib_name>

# Add stylelint to a project
nx g nx-stylelint:configuration --project <name>
nx g nx-stylelint:scss --project <name>
```

## Dependency graph

```bash
nx dep-graph                  # opens visual graph in browser
nx dep-graph --file=graph.json # exports JSON
nx affected:dep-graph         # only what's affected by current changes
```

## Affected commands (CI-friendly)

```bash
nx affected --target=lint
nx affected --target=test
nx affected --target=build
```

These only run on projects affected by your changes (relative to base branch).

## Cleanup

```bash
npm run cleanup:dist          # rm -rf dist/
npm run cleanup:node          # rm -rf node_modules/
npm run cleanup:lock          # rm package-lock.json
npm run cleanup:cache         # rm -rf node_modules/.cache/
npm run cleanup               # all of the above except cache
npm run update                # cleanup:node + npm install (clean reinstall)
```

## Prerender (SSG)

```bash
npm run prerender             # static pre-render site-ru
```

## SVG icon optimization

```bash
npm run minify-icon:kit       # apps/site-ru/src/assets/icons/svg/kit/
npm run minify-icon:product
npm run minify-icon:map
```

## Run inside Docker

If user wants to mimic CI build locally, check `Dockerfile` (if present) and `.gitlab-ci.yml`. Production builds happen via GitLab CI.

## Anti-patterns

- `npm install` without checking Volta-pinned Node version (Volta usually auto-switches, but if missing — install matching Node manually)
- Running `nx serve site-ru` and `npm run serve:api` separately when `npm run start:mock` does both
- Building `production` config for quick dev — it's slow. Use `development` first.
- Manually editing `node_modules/.cache/` to fix issues — use `npm run cleanup:cache`
- Running `npm run cleanup` before a quick fix — it wipes `node_modules` (full reinstall takes minutes)

## Troubleshooting

| Problem | Try |
|---------|-----|
| Nx cache stale / weird build errors | `npm run cleanup:cache` |
| `node_modules` corruption | `npm run update` (cleanup + install) |
| Port already in use | `lsof -i :4200` (or whichever) and stop |
| SSL/cert errors in dev | use `:cert` variants and `mkcert -install` |
| TS strict errors after pull | `nx build <project>` reveals them; lint may miss type-only issues |
| Storybook hang | `nx reset` then re-run storybook |
