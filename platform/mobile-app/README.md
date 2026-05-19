# Platform: Mobile App

Мобильное приложение Gloria Jeans (React Native).

## Что здесь должно лежать

```
mobile-app/
├── gj-app/                           # React Native monorepo (yarn workspaces)
│   ├── packages/gj/                  # основное RN-приложение (workspace "GloriaJeans")
│   │   ├── android/, ios/            # нативные платформы
│   │   ├── src/                      # TS source
│   │   └── .env.{development,staging,production}
│   ├── packages/ui-kit/              # компоненты, ассеты, стили, типы
│   └── packages/rn-yookassa-sdk/     # обёртка YooKassa (платежи)
└── mobapp-api-types/                 # общие TS-типы для API-контрактов
```

## GitLab

- Группа: https://gitlab.gloria.aaanet.ru/mobapp
- Репозитории: `mobapp/gj-app` + `mobapp/mobapp-api-types`

## Setup

См. `<workspace>/README.md` → раздел **Bootstrap → Mobile App**.

## Стек

**React Native 0.74.1** + React 18 + TypeScript 5 · **yarn workspaces** · **styled-components 6** · Firebase · Reactotron · **patch-package** · **YooKassa SDK**.

3 build-flavor: `development` / `staging` / `production`. iOS через Cocoapods (Gemfile + Podfile), Android через gradle. Hooks: husky + lefthook + lint-staged.

## Агенты

- `mobile-navigator` — где живёт экран / компонент / native bridge / env-config
- `mobile-engineer` — RN / TS / styled-components код с учётом 3 mobile-* скиллов
