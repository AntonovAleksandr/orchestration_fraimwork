---
name: site-stack-anatomy
description: Use when working with the Gloria Jeans site (gj-ng-front). Explains the Nx monorepo layout (apps + libs + tools), Angular SSR + NestJS server architecture, NgRx state organization, build profiles (dev/demo/testing/staging/production), Storybook setup, and what lives where. Trigger on anything related to platform/site/.
---

# Site Stack Anatomy

`platform/site/gj-ng-front/` is an **Nx monorepo** built around **Angular 20** + **NgRx** + **NestJS SSR**. Default branch is **`release/production`**.

## Monorepo structure

```
gj-ng-front/
├── apps/                          # thin app shells (one per locale)
│   ├── site-ru/                   # main RU production
│   ├── site-en/                   # feature EN
│   ├── site-kz/                   # KZ
│   └── site-{ru,en,kz}-e2e/       # Cypress
├── libs/                          # real code lives here
│   ├── analytics/                 # analytics tracking
│   ├── core/                      # i18n, store setup, services, utils, models
│   ├── data-access/               # API clients (calls integration / ENSI)
│   ├── modules/                   # feature modules — each self-contained
│   │   ├── basket/
│   │   ├── catalog/
│   │   ├── checkout/
│   │   ├── home/
│   │   └── profile/
│   ├── routing/                   # global route config
│   ├── server/                    # NestJS SSR server + mock API
│   ├── shared/                    # shared components/pipes/directives
│   ├── ui/                        # higher-level UI components (with storybook)
│   └── ui-kit/                    # UI primitives (with storybook)
├── tools/                         # nx generators
│   └── generators/
│       └── generate-build-version.js
├── configs/                       # shared configs (svgo, etc.)
├── .devserver/                    # local mock API server
├── .storybook/                    # global storybook config
├── deprecated/                    # legacy — avoid modifying
├── nx.json                        # nx workspace config
├── package.json                   # npm
├── tsconfig.base.json
├── jest.config.js / jest.preset.js
└── .gitlab-ci.yml
```

**Key principle:** apps are thin shells; **the real code lives in `libs/`**. An app typically imports from many libs and assembles them into a bootable Angular SSR application.

## Three apps, one codebase

Each locale (RU, EN, KZ) gets its own app under `apps/site-<locale>/`. They share `libs/` but can differ in:
- Locale-specific assets (icons, images)
- Locale-specific `app.config.ts` / routes
- Feature flag values

Most common task: changes in `libs/` automatically benefit all three apps.

## Build profiles

Each app supports 5 build configurations:

| Profile | What it does |
|---------|-------------|
| `development` | Local dev — non-minified, source maps, dev API |
| `demo` | Demo environment build |
| `testing` | Testing environment |
| `staging` | Staging environment |
| `production` | Production |

Apply via Nx: `nx build site-ru --configuration production`.

The npm scripts (`build:site:ru:prod`, etc.) wrap nx commands with `npm run build:version` first (generates a build-version JSON used by the app).

## SSR architecture

Angular SSR (Universal) is hosted by **NestJS** in `libs/server/`:
1. Client requests `https://site/path`
2. NestJS server receives request, invokes Angular renderer
3. Angular renders HTML server-side, hydrates on client

NestJS is also used in dev for **mock API** (`.devserver/`).

To run SSR locally: `npm run dev:ssr` (with mock) or `npm run dev:cert` (trusted HTTPS via mkcert).

## NgRx state organization

- **Global state setup** — in `libs/core/` (`StoreModule.forRoot`, root effects)
- **Feature state** — co-located with each feature module in `libs/modules/<feature>/`
- **Persisted slices** — via `ngrx-store-localstorage`
- **Router state** — `@ngrx/router-store` synced with Angular Router
- **Local UI state** — sometimes via `@ngrx/component-store` instead of global store

Typical structure inside a feature module:
```
libs/modules/basket/
├── src/lib/
│   ├── components/
│   ├── pages/
│   ├── services/
│   ├── store/                    # NgRx slice
│   │   ├── basket.actions.ts
│   │   ├── basket.reducer.ts
│   │   ├── basket.effects.ts
│   │   ├── basket.selectors.ts
│   │   └── index.ts
│   ├── models/
│   └── basket.routes.ts
└── project.json (nx config)
```

## i18n (Transloco)

- Languages: `ru`, `en`, `kz`
- Translation files: typically in `libs/core/i18n/<lang>.json` (verify exact path)
- Template usage: `{{ 'key.path' | transloco }}` or via service

## Storybook

Three storybooks exist:
- **ui** — `nx run ui:storybook` (port determined by config)
- **ui-kit** — `nx run ui-kit:storybook`
- **shared** — `nx run shared:storybook`

Stories are co-located: `*.stories.ts` next to components.

## Cypress e2e

One e2e project per locale: `apps/site-{ru,en,kz}-e2e/`. Runs against a serving app. Triggered via `nx run site-ru-e2e:e2e` (or similar).

## Mock API for development

`.devserver/` contains a NestJS-based mock server. Started with `npm run serve:api`. Endpoints respond with canned data — useful when developing without backend access.

## What links where

Site talks to backend via `libs/data-access/`. The real targets:
- **Integration service** (`platform/integration/`) — for checkout, cart sync
- **ENSI customers-api-web** (`platform/ensi/apps/customers-api-web/`) — for public catalog, customer profile, etc.

Most likely the calls go through `Integration` which fans out to ENSI internally (the user's original description).

## Where it gets deployed

DevOps in `site-front/devops/{helm-chart,helm-values,gitlab-ci}` (not cloned). Check `.gitlab-ci.yml` here for the build pipeline. Production deploys via `site-front/prod-deploy-ci` workflow.

## Anti-patterns

- Putting feature logic in `apps/site-<locale>/` — should be in `libs/`
- Importing from `deprecated/` — don't, it's legacy
- Cross-feature direct imports (e.g. `basket` directly importing from `catalog`) — Nx enforces module boundaries; route through `libs/shared/` or `libs/core/`
- Manual changes to `apps/site-*/project.json` without using nx generators (you'll fight nx)
