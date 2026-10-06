---
name: mobile-stack-anatomy
description: Use when working with the Gloria Jeans mobile app (React Native). Explains the monorepo layout (gj-app yarn workspaces + mobapp-api-types), key directories, native integration points (iOS Pods, Android gradle), env flavors, and the role of ui-kit / rn-yookassa-sdk packages. Trigger on anything related to platform/mobile-app/. Pairs with `pattern-development-mobile` for structured feature development.
---

# Mobile App Anatomy

**See also:** [`pattern-development-mobile.md`](../pattern-development-mobile.md) — the structured 7-step development pattern that uses this anatomy for feature implementation.

The mobile codebase lives in `platform/mobile-app/` — two cloned repos:

```
platform/mobile-app/
├── gj-app/                # main RN monorepo (mobapp/gj-app)
└── mobapp-api-types/      # shared TS types (mobapp/mobapp-api-types)
```

## `gj-app/` — yarn workspaces monorepo

Root `package.json` declares workspaces:
- `packages/gj` — main RN application (workspace name: `GloriaJeans`)
- `packages/ui-kit` — reusable UI primitives, styles, assets
- `packages/rn-yookassa-sdk` — payments SDK wrapper

Top-level config:
- `lefthook.yml`, `lint-staged.config.js` — git hooks
- `.eslintrc.js`, `.prettierrc.js`, `tsconfig.base.json`
- `patches/` — patch-package output (repo-level)
- `yarn.lock` — yarn 1.22 (NOT berry / not pnpm)

## `packages/gj` — main RN app

```
packages/gj/
├── android/                # Android native: gradle, java/kotlin, AndroidManifest.xml
├── ios/                    # iOS native: Xcode project, Podfile, Info.plist, AppDelegate
├── src/                    # TypeScript source — main app code
├── patches/                # patch-package patches for upstream libs
├── .env.development
├── .env.staging
├── .env.production
├── app.json                # RN app metadata
├── babel.config.js         # Metro / Babel plugins
├── metro.config.js
├── react-native.config.js  # autolinking config
├── firebase.json
├── Gemfile / Gemfile.lock  # for Cocoapods (`bundle exec pod install`)
├── ReactotronConfig.js
├── declarations.d.ts
└── tsconfig.json
```

App tree: workspace name in Yarn is **`GloriaJeans`** (note caps). Yarn scripts like `yarn workspace GloriaJeans <cmd>` use this name.

## `packages/ui-kit` — design system

```
packages/ui-kit/
├── assets/        # icons, images, fonts
├── components/    # reusable RN components (Buttons, Modals, Inputs, ...)
├── constants/     # colors, spacing, etc.
├── styles/        # shared styled-components patterns
├── types/         # shared TS types
├── utils/         # helpers
├── index.ts       # public exports
└── package.json
```

Import in main app: `import { Button } from '@gj/ui-kit'` (or similar — check the actual import alias in `tsconfig.json` and `metro.config.js`).

## `packages/rn-yookassa-sdk`

Wrapper around YooKassa native SDK (payment provider). Has native bindings on iOS/Android side. Bootstrap with `yarn yookassa:prepare`.

## `mobapp-api-types/`

Standalone repo with TypeScript types for the API contract between mobile and backend. Likely generated from OpenAPI specs of integration / customers-api-web (ENSI). Used by `gj-app` either as a path-dep or published package.

## Build flavors

Three environments, each with its own `.env.*`:
- `development` — local dev, points to dev API
- `staging` — pre-prod environment
- `production` — production environment

Selected via the yarn script: `yarn gj:ios:staging` etc. See `mobile-build-commands` skill for exact commands.

## Native integration points

### iOS
- `ios/Podfile` — Cocoapods deps
- `ios/<App>.xcworkspace` — Xcode workspace (open after `pod install`)
- `ios/<App>/AppDelegate.{h,mm,swift}` — bootstraps RN, registers native modules
- `ios/<App>/Info.plist` — permissions, URL schemes, etc.

### Android
- `android/build.gradle` — root gradle
- `android/app/build.gradle` — app gradle (deps, flavor configs)
- `android/app/src/main/AndroidManifest.xml` — permissions, intents
- `android/app/src/main/java/.../MainApplication.{java,kt}` — RN bootstrap, native module registration

## Things that aren't here

- **OMS** = `platform/starfish24/` (not cloned)
- **ENSI** = `platform/ensi/` (cloned, separate stack — PHP)
- **Site (web)** = `platform/site/` (not cloned)

Mobile talks to backend via integration service and customers-api-web (ENSI).
