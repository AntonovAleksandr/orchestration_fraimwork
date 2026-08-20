---
name: site-gitlab-mr-review
description: "Use when reviewing a GitLab Merge Request in site-front/gj-ng-front or related Site API-types, shared-library, build, or DevOps repositories, including Angular/Nx/NgRx, NestJS SSR, storefront flows, locale/profile behavior, or backend contract changes."
---

# Site GitLab MR Review

**BASELINE:** Apply `gj-gitlab-mr-review` once if it is not already active; never reload it recursively.

Load `site-stack-anatomy`, `site-angular-conventions`, and `site-nx-commands`. Consult `site-navigator` read-only when ownership is unclear and `architect` when a public or cross-system contract changes.

## Site Architecture Pass

- Resolve the actual source and target branches; remember that the repository default is `release/production`, while active development commonly targets `develop`.
- Derive Angular, Nx, NgRx, TypeScript, Node, and dependency constraints from the reviewed `package.json`, lockfile, Volta/config, and CI revision; do not substitute potentially stale documentation.
- Map changed files to thin locale apps, feature/data-access/core/server/shared/UI libraries, Nx dependency boundaries, and every transitively affected project. Reject new dependencies on `deprecated/` or feature logic placed in app shells.
- Review Angular code against the surrounding architecture. Check standalone/NgModule compatibility, OnPush and signal semantics, template control flow, forms and validation, Material/CDK behavior, and Transloco keys without demanding unrelated modernization.
- Trace NgRx actions -> reducers -> selectors -> effects -> API/UI outcomes. Check normalized state, stale selectors, duplicate effects, optimistic rollback, error/reset paths, and account, basket, region, and route transitions.
- Verify RxJS cancellation, ordering, deduplication, teardown, retry, and sharing semantics under rapid navigation, repeated submits, slow responses, and component destruction.
- Review SSR, CSR, prerender, and hydration separately. Check browser globals, request-scoped state, cookies/headers, TransferState or duplicate requests, deterministic HTML, timezone/locale differences, memory leaks, and hydration mismatches.
- Check RU, EN, and KZ routes, translations, assets, formatting, legal copy, feature availability, and locale-specific configuration. Check every affected `development`, `demo`, `testing`, `staging`, and `production` profile.
- For GrowthBook or other flags, verify enabled, disabled, default, targeting, and fallback paths; check SSR/client consistency, old sessions, kill switch, and the deployed configuration source.
- For persisted NgRx state, local/session storage, or cookies, verify schema migration, stale tabs, logout/account switching, basket and regional-context atomicity, SSR guards, expiry/domain/SameSite/Secure rules, and PII or token exposure.
- Inventory changed API calls and types in `libs/data-access` and related API-type repositories. Match URL, method, auth, version, DTO, optionality, units, errors, timeout, cancellation, and fallback to active ENSI/Integration/OMS implementations.
- Compare `.devserver` mocks, fixtures, interceptors, and Storybook data with production contracts. Never treat a mock-only success as backend compatibility evidence.
- For basket, checkout, identity, money, discounts, payment, delivery, stock, or order changes, trace stable IDs, units, country/region/store context, duplicate submit, partial success, recovery, and reconciliation through the complete business flow.
- Review analytics events for schema, consent, deduplication, SSR/CSR identity, PII leakage, attribution/session continuity, and changed business-metric meaning.
- Review accessibility, responsive and keyboard behavior, focus management, ARIA semantics, loading/error/empty states, and regressions in shared UI components.
- Review performance and SEO where reachable: lazy loading, bundle growth, render/change-detection cost, repeated network calls, images, Core Web Vitals, status/redirects, metadata, canonical/alternate links, structured data, robots, and sitemap behavior.
- Review XSS and unsafe HTML/URLs, open redirects, authorization assumptions, cookie/session handling, client-exposed secrets, CSP-sensitive changes, dependency integrity, and logging of personal data.

## Boundary and Rollout Pass

- Trace each changed Site contract to the exact Integration or ENSI route/version and onward to OMS or async consumers when applicable; verify active, legacy, fallback, feature-flag, and mixed-deployment paths in consumer code.
- Require companion backend, API-type, analytics, configuration, or `site-front/devops/{helm-chart,helm-values,gitlab-ci}` MRs when compatibility cannot be preserved within the Site change.
- Treat cached HTML/assets, an old open tab, persisted state, and old/new SSR pods or API versions as concurrent clients during rollout. Check chunk/cache invalidation and rollback compatibility.
- Derive verification from the Nx affected graph and changed surfaces: relevant lint/stylelint, Jest, Cypress, Storybook, locale/profile builds, SSR boot, hydration/browser smoke, and bundle analysis. Do not require unrelated suites.
- Verify `.gitlab-ci.yml`, `prod-deploy-ci`, runtime endpoints, environment injection, secret references, ingress/CDN/cache behavior, observability, feature-flag rollout, and rollback for deployment-affecting changes.
- Separate verified behavior from unavailable environment, browser, locale, backend, or deployment evidence; use `BLOCKED BY EVIDENCE` while a required active business path remains unreviewed.
