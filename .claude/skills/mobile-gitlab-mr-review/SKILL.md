---
name: mobile-gitlab-mr-review
description: "Use when reviewing a GitLab Merge Request in mobapp/gj-app or mobapp/mobapp-api-types, including React Native/TypeScript, Redux/Saga, UI packages, iOS/Android bridges, YooKassa, analytics, API contracts, build flavors, or mobile release compatibility. Validates alignment with `pattern-development-mobile` where applicable."
---

# Mobile GitLab MR Review

**BASELINE:** Apply `gj-gitlab-mr-review` once if it is not already active; never reload it recursively.

Load `mobile-stack-anatomy` and `mobile-rn-conventions`; add `mobile-build-commands` for CI, build, dependency, or release evidence. Refer to [`pattern-development-mobile`](../pattern-development-mobile.md) when reviewing feature implementation for structured compliance. Consult `mobile-navigator` read-only when ownership is unclear, `mobile-researcher` for legacy/native quirks, and `architect` when a public or cross-system contract changes. Derive versions and layout from the reviewed package, lock, and native files; report stale README/workspace documentation.

## Mobile Architecture Pass

- Identify changes to the app, UI kit, `mobapp-api-types`, `rn-yookassa-sdk`, `rn-analytics-system-sdk`, or several release units. Require compatible versions and publication/install order.
- Trace TS/TSX behavior as `screen/event -> component/hook -> Redux action/reducer -> Saga -> API/native side effect -> persisted state -> UI`. Check cleanup, cancellation, `takeLatest`/`takeEvery`, response ordering, errors, and duplicate taps.
- Keep UI primitives and app features in established boundaries. Check exports, theme, accessibility, localization, safe areas, keyboard behavior, render/list performance, and screen sizes.
- Require versioned migrations and safe defaults for Redux Persist/AsyncStorage. Verify upgrade-over-install, downgrade, corrupt/partial state, logout/deletion, and atomic region/currency/basket/checkout updates.
- Exercise offline, timeout, retry, background/foreground, process death, and repeated actions. Prevent duplicate basket mutations, orders, payments, loyalty operations, and analytics.
- Review token refresh/logout races, secure storage, identifiers, permissions, consent, PII redaction, screenshots/logs, and deletion. Reject hardcoded secrets or production endpoints.
- Reconcile runtime collection and tracking with iOS `PrivacyInfo.xcprivacy`, ATT/Info.plist, Android permissions/Data Safety, and App Store/Google Play privacy declarations whenever identifiers, analytics, advertising, payments, location, contacts, media, or device data change.
- Check deep links and push for cold, warm, background, authenticated, unauthenticated, expired, malformed, and unsupported targets; prevent loops and cross-account exposure.

## Native and Contract Pass

- Inspect iOS and Android independently: bridge lifecycle/threading/callbacks, registration, URL schemes/intents, permissions, background modes, signing, OS targets, and fallbacks.
- Reconcile `package.json`/`yarn.lock`, Podfile/Podfile.lock, Gradle declarations/resolved graph, wrapper manifests, and applicable `patch-package` patches. Missing lock or compatible patch evidence blocks dependency conclusions.
- For YooKassa, trace tokenization, 3DS/SBP return/cancel/failure, dismissal/backgrounding, network loss, double submit, initial/repeat/late payment, and Integration/OMS/fiscal reconciliation.
- Trace `mobapp-api-types` as source OpenAPI -> generated v3/v4/v5 -> published package -> installed app -> runtime parsing/errors. Reject hand-edited generation or released-client breaks; require zero unexplained stub/skipped refs, review generator autofix diffs, and compare the published tarball with the intended source contract.
- Map changed requests, responses, enums, money units, identifiers, flags, and errors to active ENSI/Integration/OMS routes and supported API/app-version fallbacks. Require server-first compatibility or a minimum-version gate.
- Compare `development`, `staging`, and `production` plus iOS schemes/Android variants: endpoints, flags, secret references, push, entitlements, analytics/crash reporting, signing, and release optimization.
- Verify analytics schema, consent, deduplication, attribution, funnel continuity, Crashlytics/Sentry/ANR evidence, and absence of token/payment/customer PII leakage.

## Mobile Rollout Gate

- Treat App Store/Google Play publication as a delayed rollout with a long client tail. Require old/new backend compatibility, mixed-version monitoring, kill switches, staged criteria, and containment because installed binaries cannot roll back instantly.
- Derive verification from the changed surface: `yarn lint`, relevant app/UI-kit/YooKassa/analytics typechecks and tests, generated-package inspection, plus affected iOS/Android flavor builds and device smoke paths. Never treat TypeScript-only success as native, analytics-bridge, API-contract, or store-build evidence.
- Check companion MRs, release branch/build numbers, store policy, crash-free sessions/ANR, auth, checkout/payment conversion, and rollback or forward-fix ownership before calling the change release-safe.
