---
name: SKILL
version: 1.0.0
layer: mobile-build-commands
platform: Generic
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---


# Mobile Build Commands

**See also:** [`pattern-development-mobile.md`](../pattern-development-mobile.md) — the structured 7-step development pattern for React Native features.

All commands run from `platform/mobile-app/gj-app/` (yarn workspaces root).

## First-time setup

```bash
cd platform/mobile-app/gj-app

# Install all node_modules across workspaces
yarn

# Bootstrap YooKassa (must be run before first iOS build)
yarn yookassa:prepare

# Install iOS pods
yarn gj:pod-install
```

If `gj:pod-install` fails: ensure Ruby + bundler are installed (Gemfile uses bundler), and Cocoapods is installed (`gem install cocoapods` or via bundler).

## Day-to-day development

### Start Metro bundler
```bash
yarn gj:start          # starts Metro with cache reset
```

### Run on iOS
```bash
yarn gj:ios:development   # dev API, debug build
yarn gj:ios:staging       # staging API
yarn gj:ios:production    # production API
```

### Run on Android
```bash
yarn gj:android:development
yarn gj:android:staging
yarn gj:android:staging-release   # release build pointed at staging
yarn gj:android:production
```

## Maintenance

```bash
# Reinstall yarn deps inside packages/gj only
yarn gj:yarn-install

# Clean Metro cache
yarn gj:clean-cache

# Wipe ALL node_modules across the monorepo (nuclear)
yarn clean:modules

# Re-install pods (e.g. after adding an iOS dep)
yarn gj:pod-install
yarn gj:npxpod-install   # alternative using npx pod-install
```

## Quality gates

```bash
yarn lint              # eslint across .js/.jsx/.ts/.tsx (quiet mode)
yarn gj:ts             # typecheck main app
yarn ui-kit:ts         # typecheck ui-kit package
yarn yookassa:ts       # typecheck rn-yookassa-sdk
```

Run `yarn lint && yarn gj:ts` before declaring any change done.

## Build flavors quick reference

| Flavor | Env file | iOS script | Android script |
|--------|----------|-----------|---------------|
| development | `.env.development` | `gj:ios:development` | `gj:android:development` |
| staging | `.env.staging` | `gj:ios:staging` | `gj:android:staging` + `gj:android:staging-release` |
| production | `.env.production` | `gj:ios:production` | `gj:android:production` |

When asked to "build for X", run the appropriate script. When investigating behavior — check the matching `.env.*`.

## Hooks (auto-run)

- **husky + lefthook** triggered on commit
- **lint-staged** runs eslint on staged files
- Failure blocks commit. Don't bypass with `--no-verify` unless user explicitly asks.

## Troubleshooting

| Problem | Try |
|---------|-----|
| Metro stale cache | `yarn gj:clean-cache && yarn gj:start` |
| iOS Pods out of sync | `yarn gj:pod-install` |
| node_modules corruption | `yarn clean:modules && yarn` |
| `patch-package` errors | check `gj-app/patches/` and `gj-app/packages/gj/patches/`, ensure target lib versions match |
| Linux/WSL CRLF issues in `packages/gj/patches/` | convert CRLF → LF (README notes Windows pitfall) |
| Build fails on staging only | check `.env.staging` for missing keys; compare with `.env.development` |

## Anti-patterns

- Running `npm install` instead of `yarn` — breaks lockfile parity
- Running `pod install` directly in `ios/` instead of `yarn gj:pod-install` — bypasses bundler / patch hooks
- Hard-resetting `patches/` — those are intentional fixes, don't delete
- Skipping `yookassa:prepare` before first iOS build — pod install will fail
