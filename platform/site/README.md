# Platform: Site

Публичный сайт Gloria Jeans (RU + EN + KZ) — `gj-ng-front`.

## Что здесь должно лежать

```
site/
└── gj-ng-front/        # Nx monorepo — branch: release/production (⚠️)
    ├── apps/
    │   ├── site-ru/, site-en/, site-kz/          # 3 локализованных Angular apps
    │   └── site-{ru,en,kz}-e2e/                  # Cypress e2e
    ├── libs/
    │   ├── core/, data-access/, routing/, server/ (NestJS SSR), shared/, analytics/
    │   ├── modules/{basket,catalog,checkout,home,profile}/  # feature-модули
    │   └── ui/, ui-kit/  (with Storybook)
    ├── tools/generators/, configs/, .devserver/ (mock API), .storybook/, deprecated/
    └── nx.json / package.json (npm) / tsconfig.base.json
```

## GitLab

- Группа: https://gitlab.gloria.aaanet.ru/site-front
- Главный репо: `site-front/gj-ng-front`

В группе ещё репо (greensight-lib, gj-front-external-configurator, mobile-dummy, DevOps) — по умолчанию не клонируются.

## ⚠️ Default branch

`release/production` (нестандартно). Активная разработка обычно на `develop` и feature-ветках.

## Setup

См. `<workspace>/README.md` → раздел **Bootstrap → Site**.

## Стек

**Angular 20** + Angular SSR (Universal) + Material/CDK · **Nx 21 monorepo** · **NestJS 11** (хостит SSR + mock API) · **NgRx 20** (store/effects/entity/component-store/router) · **TypeScript 5.9** · **Transloco** (ru/en/kz) · **SCSS** + stylelint · **Storybook 9** · **Jest** + **Cypress 13** · **GrowthBook** · **npm** + **Volta** (Node 20.9).

5 build-флейворов: `development` / `demo` / `testing` / `staging` / `production`.

## Агенты

- `site-navigator` — где живёт компонент / lib / NgRx state / маршрут
- `site-engineer` — Angular / NgRx / NestJS SSR код с учётом 3 site-* скиллов
