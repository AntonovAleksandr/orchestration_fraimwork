---
name: site-angular-conventions
description: Use when writing or reviewing Angular / NgRx / RxJS / NestJS-SSR code for the Gloria Jeans site. Covers Angular 20 patterns (standalone components, signals, new control flow), NgRx structure (actions/reducers/effects/selectors), RxJS best practices, Transloco i18n, SCSS+stylelint, SSR considerations, and module-boundary discipline in Nx.
---

# Site Angular Conventions

Code lives in `platform/site/gj-ng-front/{apps,libs}/`. Stack: Angular 20 + Nx + NgRx + NestJS SSR.

## Angular 20 — modern patterns

### Components: prefer standalone over NgModule
```ts
@Component({
  selector: 'gj-product-card',
  standalone: true,
  imports: [CommonModule, RouterLink, GjButtonComponent],
  templateUrl: './product-card.html',
  styleUrls: ['./product-card.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProductCardComponent { ... }
```

- `standalone: true` for **new code**
- `changeDetection: OnPush` — almost always (NgRx + signals = OnPush-friendly)
- Templates in `.html` files, styles in `.scss` files (NOT inline) for non-trivial components

### Signals for component-local state
```ts
@Component({ ... })
export class FooComponent {
  count = signal(0);
  doubled = computed(() => this.count() * 2);

  increment() { this.count.update(c => c + 1); }
}
```
Template:
```html
<span>{{ count() }} → {{ doubled() }}</span>
```

### New control flow (`@if`, `@for`, `@switch`)
```html
<!-- prefer this -->
@if (product()) {
  <gj-product-card [product]="product()" />
} @else {
  <gj-skeleton />
}

@for (item of items(); track item.id) {
  <gj-item [item]="item" />
}
```
Over old `*ngIf` / `*ngFor` for new code.

### Inject function (over constructor params) — optional but trendy
```ts
private store = inject(Store);
private route = inject(ActivatedRoute);
```

### Don't refactor existing code unsolicited
If the codebase uses NgModule + constructor injection — match that style in nearby files. Only use new patterns in genuinely new code.

## NgRx patterns

### Slice anatomy
```ts
// basket.actions.ts
export const loadBasket = createAction('[Basket/API] Load');
export const loadBasketSuccess = createAction(
  '[Basket/API] Load Success',
  props<{ basket: Basket }>(),
);

// basket.reducer.ts
export const basketReducer = createReducer(
  initialState,
  on(loadBasketSuccess, (state, { basket }) => ({ ...state, basket })),
);

// basket.selectors.ts
export const selectBasketState = createFeatureSelector<BasketState>('basket');
export const selectItems = createSelector(selectBasketState, s => s.basket?.items ?? []);

// basket.effects.ts
loadBasket$ = createEffect(() => this.actions$.pipe(
  ofType(loadBasket),
  switchMap(() => this.api.getBasket().pipe(
    map(basket => loadBasketSuccess({ basket })),
    catchError(err => of(loadBasketFailure({ error: err }))),
  )),
));
```

### Selectors in templates
```ts
items$ = this.store.select(selectItems);
```
```html
@for (item of items$ | async; track item.id) { ... }
```
Or via signals: `items = toSignal(this.store.select(selectItems), { initialValue: [] });`

### When to use ComponentStore
For UI-local state that doesn't need to be global (modal open/closed, form draft state, pagination). Reduces noise in global store.

### Action naming convention
`[Source] Description` or `[Feature/Source] Description`. Examples: `[Basket Page] Add Item`, `[Basket/API] Load Success`. Sources: Page, API, Component, Effect, etc.

## RxJS

### Always unsubscribe
- `| async` in templates handles this automatically — prefer it.
- For component logic: `takeUntilDestroyed()` (Angular 16+, available in Angular 20) — cleanest.
  ```ts
  ngOnInit() {
    this.store.select(selectFoo)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(...);
  }
  ```

### Composition operators
- `switchMap` — cancel previous (common for API calls)
- `mergeMap` / `concatMap` — keep all (use carefully)
- `exhaustMap` — ignore new emissions while one in flight (e.g. submit buttons)
- `combineLatest` — combine multiple streams (latest from each)
- `shareReplay({ bufferSize: 1, refCount: true })` — cache last value with refcount

### Don't nest subscriptions
Always use higher-order operators (`switchMap`, etc.) instead of `subscribe` inside `subscribe`.

## i18n (Transloco)

### In templates
```html
<button>{{ 'checkout.submit' | transloco }}</button>
<p [innerHTML]="'product.description' | transloco: { name: product().name }"></p>
```

### In TS
```ts
private transloco = inject(TranslocoService);
this.transloco.selectTranslate('checkout.success').subscribe(text => ...);
```

### Adding keys
Add to all locale JSON files in `libs/core/i18n/` (or wherever the project keeps them). All three: `ru`, `en`, `kz`. Even if EN/KZ values are placeholder, add the key.

## SSR considerations

Angular SSR runs Angular code in Node.js. Common gotchas:
- **No `window`, `document`, `localStorage` directly** — wrap in `isPlatformBrowser(platformId)` checks
- **Avoid `setTimeout`/`setInterval` long-lived** — they'll keep the SSR render alive
- **Avoid heavy work in constructors of services that get bootstrapped server-side**
- **Date/timezone**: server uses its TZ, client uses user's — be explicit (Intl, dayjs with tz, etc.)
- **Static analysis**: `nx build site-ru --configuration production` catches SSR issues that dev mode misses

### Browser-only fragments
```ts
import { isPlatformBrowser } from '@angular/common';
import { PLATFORM_ID, inject } from '@angular/core';

private platformId = inject(PLATFORM_ID);

ngOnInit() {
  if (isPlatformBrowser(this.platformId)) {
    // browser-only code (e.g. localStorage)
  }
}
```

## Styling

### SCSS structure
- Component styles in `<component>.scss` — scoped via Angular's view encapsulation
- Shared variables (colors, breakpoints, mixins) — likely in `libs/ui-kit/styles/` (check)
- Use Angular Material theming when extending Material components
- Stylelint config: `.stylelintrc.json` at root; per-project may extend

### Don't inline styles
```html
<!-- bad -->
<div style="padding: 16px;">...</div>
<!-- good -->
<div class="wrapper">...</div>
```

## Nx module boundaries

Nx enforces `tags` on libraries (in `project.json`). Common pattern:
- `scope:shared`, `scope:basket`, `scope:catalog`, etc.
- `type:ui`, `type:feature`, `type:data-access`, `type:util`

Rules (in `.eslintrc.json` `@nx/enforce-module-boundaries`): e.g. `scope:basket` can only depend on `scope:shared` or own. ESLint will yell if you violate.

**When you get a module-boundary error**: don't suppress it. Either:
1. Route the dependency through `libs/shared/` (lift the common code there)
2. Reconsider the dependency direction

## Tests

### Unit (Jest)
- Co-located `*.spec.ts`
- For components: `TestBed.configureTestingModule({ imports: [StandaloneComponent] })`
- For services calling NgRx: provide `MockStore` from `@ngrx/store/testing`
- For effects: `provideMockActions`, `getTestScheduler` for marble tests

### E2E (Cypress)
- Specs in `apps/site-<locale>-e2e/src/`
- Run `nx run site-ru-e2e:e2e` (headless) or `:e2e --watch` (interactive)

## NestJS SSR server (`libs/server/`)

Note: it's NestJS, but it primarily exists to render Angular SSR. Don't add unrelated REST endpoints here — those belong in `Integration` service. If you need a server-side route specifically for SSR (e.g. preview, SEO sitemaps), it's fine.

## Anti-patterns

- Subscribing in templates without `| async` (memory leaks)
- Heavy logic in templates (move to component class with `computed` / signal)
- Direct `localStorage` access without browser-platform check (SSR crash)
- Manual `subscribe(...)` without unsubscribe (memory leaks)
- Hardcoded strings (use Transloco)
- Inline styles
- `@for` without `track` (performance, also required syntax)
- Suppressing `@nx/enforce-module-boundaries` instead of fixing the dep direction
- Adding files to `deprecated/` paths

## When to escalate

- Where is X → `site-navigator`
- Build / config / Nx target issues → `site-nx-commands` skill
- Cross-system contract → `architect`
- Strange runtime errors only in prod → `logs-detective`
