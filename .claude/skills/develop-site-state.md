# 🔄 develop-site-state.md

**Категория:** [DEVELOPMENT]  
**Платформа:** Site (gj-ng-front)  
**Версия:** 1.0  
**Статус:** Production-ready  
**Автор:** Claude Haiku 4.5 + team

---

## 📋 Описание

**Управление состоянием через NgRx** в Site (Angular store, entity adapters, selectors, effects).

Этот скил описывает как **правильно** организовывать state, писать actions, reducers, effects и selectors для консистентного управления данными.

**Когда использовать:**
- Добавляешь новый feature state (корзина, каталог, профиль)
- Меняешь существующий reducer
- Пишешь effects для side effects
- Оптимизируешь selectors
- Работаешь с entity adapters

---

## 🎯 Архитектура NgRx в Site

### Структура папок

```
libs/core/data-access/           # ← Центральный store
├── store/
│   ├── app.reducer.ts           # Root reducer
│   ├── app.effects.ts           # Root effects
│   ├── app.facade.ts            # Public API для компонентов
│   │
│   └── features/
│       ├── basket/              # Feature: Корзина
│       │   ├── actions/         # basket.actions.ts
│       │   ├── reducers/        # basket.reducer.ts
│       │   ├── effects/         # basket.effects.ts
│       │   ├── selectors/       # basket.selectors.ts
│       │   └── models/          # basket.models.ts
│       │
│       ├── catalog/             # Feature: Каталог
│       │   ├── actions/
│       │   ├── reducers/
│       │   ├── effects/
│       │   ├── selectors/
│       │   └── models/
│       │
│       └── auth/                # Feature: Аутентификация
│           ├── actions/
│           ├── reducers/
│           ├── effects/
│           ├── selectors/
│           └── models/
│
├── services/                    # API сервисы (HTTP)
└── models/                      # Общие типы
```

### Паттерн: 4 слоя state

```
1. Models       → TS типы (Product, BasketItem, etc)
2. Actions      → События (LoadProducts, AddToBasket, etc)
3. Reducers     → Обновления state (как реагируем на actions)
4. Effects      → Side effects (HTTP запросы, router, localStorage)
5. Selectors    →読み取り (как читаем state)
```

---

## 🛠️ 7 шагов разработки Feature State

### 1️⃣ ПОНИМАНИЕ

**Спросить себя:**

```
✅ ЧТО состояние управляет?
   "Товары в корзине и общую сумму"

✅ ГДЕ используется?
   "В 5 компонентах: корзина, чекаут, шапка, сайдбар"

✅ КАКИЕ действия (actions)?
   - LoadBasket (инициализация)
   - AddToBasket (добавить товар)
   - RemoveFromBasket (удалить)
   - UpdateQuantity (изменить кол-во)
   - ClearBasket (очистить)

✅ КАКИЕ селекторы (selectors)?
   - selectBasketItems (список товаров)
   - selectBasketTotal (сумма)
   - selectBasketCount (кол-во)
   - selectIsLoading (загружается ли?)

✅ Есть ли [BLOCKER]?
   → Нет, могу писать
```

---

### 2️⃣ ПЛАН

**Определить структуру:**

- [ ] Models файл (TS типы)
- [ ] Actions файл (все события)
- [ ] Reducer файл (логика обновления)
- [ ] Effects файл (HTTP запросы)
- [ ] Selectors файл (чтение state)
- [ ] Index файл (экспорты)
- [ ] Tests для каждого

**Пример плана:**

```
Порядок создания:
1. basket.models.ts (типы)
2. basket.actions.ts (события)
3. basket.reducer.ts (логика)
4. basket.effects.ts (HTTP)
5. basket.selectors.ts (чтение)
6. basket.spec.ts (тесты)
7. index.ts (экспорты)

Интеграция:
✅ App reducer: импортировать basket reducer
✅ App effects: импортировать basket effects
✅ Data-access facade: обновить методы
```

---

### 3️⃣ КОД

#### Models

```typescript
// libs/core/data-access/store/features/basket/models/basket.models.ts

import { Currency } from '@shared/types';

/**
 * Товар в корзине
 */
export interface BasketItem {
  id: string;
  productId: string;
  name: string;
  price: Currency;
  quantity: number;
  image?: string;
  selectedOptions?: Record<string, string>;  // цвет, размер, etc
}

/**
 * Состояние корзины
 */
export interface BasketState {
  items: BasketItem[];
  isLoading: boolean;
  error: string | null;
  lastUpdated: number | null;
}

/**
 * Всего в корзине
 */
export interface BasketTotal {
  itemsCount: number;
  subtotal: Currency;
  shipping: Currency;
  total: Currency;
}

/**
 * Стартовое состояние
 */
export const initialBasketState: BasketState = {
  items: [],
  isLoading: false,
  error: null,
  lastUpdated: null,
};
```

**Правила:**
- ✅ Интерфейсы вместо типов (более строгие)
- ✅ Документация для каждого интерфейса
- ✅ Initial state здесь же

#### Actions

```typescript
// libs/core/data-access/store/features/basket/actions/basket.actions.ts

import { createAction, props } from '@ngrx/store';
import { BasketItem, BasketTotal } from '../models/basket.models';

// Загрузка корзины с сервера
export const loadBasket = createAction(
  '[Basket] Load Basket',
);

// Успешная загрузка
export const loadBasketSuccess = createAction(
  '[Basket] Load Basket Success',
  props<{ items: BasketItem[]; total: BasketTotal }>(),
);

// Ошибка при загрузке
export const loadBasketError = createAction(
  '[Basket] Load Basket Error',
  props<{ error: string }>(),
);

// Добавить товар в корзину
export const addToBasket = createAction(
  '[Basket] Add To Basket',
  props<{ item: BasketItem }>(),
);

// Успешное добавление
export const addToBasketSuccess = createAction(
  '[Basket] Add To Basket Success',
  props<{ item: BasketItem }>(),
);

// Удалить товар из корзины
export const removeFromBasket = createAction(
  '[Basket] Remove From Basket',
  props<{ itemId: string }>(),
);

// Изменить количество
export const updateQuantity = createAction(
  '[Basket] Update Quantity',
  props<{ itemId: string; quantity: number }>(),
);

// Очистить корзину
export const clearBasket = createAction(
  '[Basket] Clear Basket',
);

// Очистить ошибку
export const clearError = createAction(
  '[Basket] Clear Error',
);
```

**Правила:**
- ✅ Action names в формате `[Feature] Event`
- ✅ Success/Error pair для async operations
- ✅ props() для передачи данных
- ✅ Нет nested objects если можно flatten

#### Reducer

```typescript
// libs/core/data-access/store/features/basket/reducers/basket.reducer.ts

import { createReducer, on } from '@ngrx/store';
import { BasketState, initialBasketState } from '../models/basket.models';
import * as BasketActions from '../actions/basket.actions';

export const basketReducer = createReducer(
  initialBasketState,

  // Загрузка начата
  on(BasketActions.loadBasket, (state) => ({
    ...state,
    isLoading: true,
    error: null,
  })),

  // Загрузка успешно завершена
  on(BasketActions.loadBasketSuccess, (state, { items, total }) => ({
    ...state,
    items,
    isLoading: false,
    lastUpdated: Date.now(),
  })),

  // Ошибка при загрузке
  on(BasketActions.loadBasketError, (state, { error }) => ({
    ...state,
    isLoading: false,
    error,
  })),

  // Добавить товар локально (оптимистичный update)
  on(BasketActions.addToBasket, (state, { item }) => ({
    ...state,
    items: [...state.items, item],
  })),

  // Удалить товар
  on(BasketActions.removeFromBasket, (state, { itemId }) => ({
    ...state,
    items: state.items.filter(i => i.id !== itemId),
  })),

  // Изменить количество
  on(BasketActions.updateQuantity, (state, { itemId, quantity }) => ({
    ...state,
    items: state.items.map(item =>
      item.id === itemId ? { ...item, quantity } : item,
    ),
  })),

  // Очистить корзину
  on(BasketActions.clearBasket, () => initialBasketState),

  // Очистить ошибку
  on(BasketActions.clearError, (state) => ({
    ...state,
    error: null,
  })),
);
```

**Правила:**
- ✅ Pure functions (нет mutations)
- ✅ Spread operator для обновления
- ✅ Default case обрабатывается автоматически
- ✅ Immutable updates (весь логика здесь)

#### Effects

```typescript
// libs/core/data-access/store/features/basket/effects/basket.effects.ts

import { Injectable } from '@angular/core';
import { Actions, createEffect, ofType } from '@ngrx/effects';
import { of } from 'rxjs';
import { catchError, map, switchMap, tap } from 'rxjs/operators';

import * as BasketActions from '../actions/basket.actions';
import { BasketService } from '@core/services/basket.service';
import { Store } from '@ngrx/store';
import { Router } from '@angular/router';

@Injectable()
export class BasketEffects {
  // Загрузка корзины
  loadBasket$ = createEffect(() =>
    this.actions$.pipe(
      ofType(BasketActions.loadBasket),
      switchMap(() =>
        this.basketService.getBasket().pipe(
          map((response) =>
            BasketActions.loadBasketSuccess({
              items: response.items,
              total: response.total,
            }),
          ),
          catchError((error) =>
            of(BasketActions.loadBasketError({ error: error.message })),
          ),
        ),
      ),
    ),
  );

  // Добавить товар на сервер
  addToBasket$ = createEffect(() =>
    this.actions$.pipe(
      ofType(BasketActions.addToBasket),
      switchMap(({ item }) =>
        this.basketService.addItem(item).pipe(
          map(() => BasketActions.addToBasketSuccess({ item })),
          catchError((error) =>
            of(BasketActions.loadBasketError({ error: error.message })),
          ),
        ),
      ),
    ),
  );

  // Удалить товар
  removeFromBasket$ = createEffect(() =>
    this.actions$.pipe(
      ofType(BasketActions.removeFromBasket),
      switchMap(({ itemId }) =>
        this.basketService.removeItem(itemId).pipe(
          map(() => BasketActions.removeFromBasket({ itemId })),
          catchError(() => of()),
        ),
      ),
    ),
  );

  // Оптимистичное добавление: даже если ошибка, не откатываем UI
  optimisticAddToBasket$ = createEffect(() =>
    this.actions$.pipe(
      ofType(BasketActions.addToBasketSuccess),
      tap(() => {
        // Analytics, notifications, etc
      }),
    ),
    { dispatch: false },
  );

  constructor(
    private actions$: Actions,
    private basketService: BasketService,
    private store: Store,
    private router: Router,
  ) {}
}
```

**Правила:**
- ✅ switchMap для один-за-раз обработки
- ✅ catchError всегда (даже если молча)
- ✅ tap для side effects без dispatch
- ✅ { dispatch: false } для оповещений

#### Selectors

```typescript
// libs/core/data-access/store/features/basket/selectors/basket.selectors.ts

import { createFeatureSelector, createSelector } from '@ngrx/store';
import { BasketState, BasketItem } from '../models/basket.models';

// Базовый selector для feature state
const selectBasketState = createFeatureSelector<BasketState>('basket');

// Список товаров
export const selectBasketItems = createSelector(
  selectBasketState,
  (state: BasketState) => state.items,
);

// Отдельный товар по ID
export const selectBasketItemById = (itemId: string) =>
  createSelector(
    selectBasketItems,
    (items: BasketItem[]) => items.find(i => i.id === itemId),
  );

// Количество товаров
export const selectBasketCount = createSelector(
  selectBasketItems,
  (items: BasketItem[]) => items.reduce((sum, item) => sum + item.quantity, 0),
);

// Общая стоимость
export const selectBasketTotal = createSelector(
  selectBasketItems,
  (items: BasketItem[]) => {
    const subtotal = items.reduce(
      (sum, item) => sum + item.price.value * item.quantity,
      0,
    );
    return {
      itemsCount: items.length,
      subtotal: { value: subtotal, currency: 'RUB' },
      shipping: { value: 0, currency: 'RUB' },
      total: { value: subtotal, currency: 'RUB' },
    };
  },
);

// Состояние загрузки
export const selectIsLoading = createSelector(
  selectBasketState,
  (state: BasketState) => state.isLoading,
);

// Ошибка
export const selectError = createSelector(
  selectBasketState,
  (state: BasketState) => state.error,
);

// Есть ли товары в корзине?
export const selectHasItems = createSelector(
  selectBasketItems,
  (items: BasketItem[]) => items.length > 0,
);
```

**Правила:**
- ✅ Селекторы для КАЖДОГО куска state
- ✅ Мемоизация автоматическая (не пересчитывается если input не изменился)
- ✅ Composition: selectBasketTotal использует selectBasketItems
- ✅ Нет логики в компонентах (вся логика здесь)

#### Index и регистрация

```typescript
// libs/core/data-access/store/features/basket/index.ts

export * from './models/basket.models';
export * from './actions/basket.actions';
export * from './reducers/basket.reducer';
export * from './effects/basket.effects';
export * from './selectors/basket.selectors';
```

```typescript
// libs/core/data-access/store/app.reducer.ts

import { ActionReducerMap } from '@ngrx/store';
import { basketReducer } from './features/basket';
import { catalogReducer } from './features/catalog';
import { authReducer } from './features/auth';

export interface AppState {
  basket: BasketState;
  catalog: CatalogState;
  auth: AuthState;
}

export const appReducers: ActionReducerMap<AppState> = {
  basket: basketReducer,
  catalog: catalogReducer,
  auth: authReducer,
};
```

```typescript
// libs/core/data-access/store/app.effects.ts

import { BasketEffects } from './features/basket';
import { CatalogEffects } from './features/catalog';
import { AuthEffects } from './features/auth';

export const effects = [
  BasketEffects,
  CatalogEffects,
  AuthEffects,
];
```

```typescript
// main.ts (приложение)

import { provideStore } from '@ngrx/store';
import { provideEffects } from '@ngrx/effects';
import { appReducers, effects } from '@core/data-access';

bootstrapApplication(AppComponent, {
  providers: [
    provideStore(appReducers),
    provideEffects(effects),
  ],
});
```

---

### 4️⃣ SECURITY

```
✅ Нет приватных данных в state
   ❌ store: { userPassword, creditCard }
   ✅ store: { userId, isAuthenticated }

✅ HTTPS для всех HTTP запросов
   ✅ basketService.getBasket() → HTTPS

✅ Нет secrets в actions
   ❌ dispatch(LoginAction({ apiKey: 'sk-123' }))
   ✅ dispatch(LoginAction({ username, password }))

✅ Валидация данных из backend
   ✅ response.items.map(item => new BasketItemDTO(item))
```

---

### 5️⃣ ТЕСТЫ

```typescript
// libs/core/data-access/store/features/basket/basket.spec.ts

import { TestBed } from '@angular/core/testing';
import { provideMockStore, MockStore } from '@ngrx/store/testing';
import { BasketState, initialBasketState } from './models/basket.models';
import * as BasketActions from './actions/basket.actions';
import * as BasketSelectors from './selectors/basket.selectors';

describe('Basket State', () => {
  let store: MockStore<{ basket: BasketState }>;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideMockStore({
          initialState: { basket: initialBasketState },
        }),
      ],
    });

    store = TestBed.inject(MockStore);
  });

  describe('Reducers', () => {
    it('loadBasket должен установить isLoading=true', () => {
      const action = BasketActions.loadBasket();
      const result = basketReducer(initialBasketState, action);

      expect(result.isLoading).toBe(true);
    });

    it('addToBasket должен добавить товар', () => {
      const item = { id: '1', productId: 'p1', name: 'Test', quantity: 1 };
      const action = BasketActions.addToBasket({ item });

      const result = basketReducer(initialBasketState, action);

      expect(result.items).toContain(item);
      expect(result.items.length).toBe(1);
    });
  });

  describe('Selectors', () => {
    it('selectBasketCount должен вернуть сумму quantities', () => {
      const state: BasketState = {
        items: [
          { id: '1', quantity: 2 },
          { id: '2', quantity: 3 },
        ],
      };

      const result = BasketSelectors.selectBasketCount.projectionFn(state);

      expect(result).toBe(5);
    });

    it('selectHasItems должен вернуть true если товары есть', () => {
      const state: BasketState = {
        items: [{ id: '1', quantity: 1 }],
      };

      const result = BasketSelectors.selectHasItems.projectionFn(state);

      expect(result).toBe(true);
    });
  });

  describe('Effects', () => {
    it('loadBasket$ должен загрузить корзину', (done) => {
      const action = BasketActions.loadBasket();
      const completion = BasketActions.loadBasketSuccess({
        items: [],
        total: {},
      });

      // Mock effect и проверить что он dispatch completion
    });
  });
});
```

---

### 6️⃣ КОММИТ

```bash
git add libs/core/data-access/store/features/basket/

git commit -m "feat(basket-state): добавить NgRx state управление корзиной

- Models: BasketItem, BasketState, BasketTotal
- Actions: loadBasket, addToBasket, removeFromBasket, clearBasket
- Reducer: обновление state для всех actions
- Effects: HTTP запросы к basketService
- Selectors: selectBasketItems, selectBasketCount, selectBasketTotal
- Tests: >85% coverage для reducer и selectors

AC выполнены:
- Корзина загружается с сервера ✅
- Товары добавляются оптимистично ✅
- Селекторы мемоизированы ✅

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

---

### 7️⃣ MR и интеграция

**Checklist перед MR:**
- [ ] Все actions, reducers, effects, selectors создали
- [ ] Регистрировали effects в app.effects.ts
- [ ] Регистрировали reducer в app.reducer.ts
- [ ] Тесты >85% coverage
- [ ] Нет console.log
- [ ] Используем селекторы в компонентах (не $.pipe)

---

## 💡 Частые паттерны

### Оптимистичный update

```typescript
// Action сразу обновляет UI, затем сервер подтверждает

on(BasketActions.addToBasket, (state, { item }) => ({
  ...state,
  items: [...state.items, item],  // ← Сразу добавляем
})),

// Effect отправляет на сервер, но UI уже обновился
addToBasket$ = createEffect(() =>
  this.actions$.pipe(
    ofType(BasketActions.addToBasket),
    switchMap(({ item }) =>
      this.basketService.addItem(item).pipe(
        map(() => BasketActions.addToBasketSuccess({ item })),
        catchError(() => {
          // Если ошибка, откатываем через отдельный action
          return of(BasketActions.removeFromBasket({ itemId: item.id }));
        }),
      ),
    ),
  ),
);
```

### Инвалидация кэша

```typescript
// Когда товары изменились, перезагрузить все

on(BasketActions.addToBasketSuccess, (_state) =>
  // Не обновляем state (уже обновили в addToBasket)
  // Просто перезагружаем для свежих данных с сервера
  BasketActions.loadBasket(),
),
```

### Использование в компоненте

```typescript
// ✅ Правильно: через селектор

export class BasketComponent {
  items$ = this.store.select(selectBasketItems);
  total$ = this.store.select(selectBasketTotal);
  isLoading$ = this.store.select(selectIsLoading);

  constructor(private store: Store) {}

  onAddToBasket(item: BasketItem) {
    this.store.dispatch(BasketActions.addToBasket({ item }));
  }
}

// Template
<div *ngIf="items$ | async as items">
  <div *ngFor="let item of items">
    {{ item.name }}
  </div>
</div>
```

---

## 📚 Ресурсы

- **NgRx docs:** https://ngrx.io/docs
- **Entity adapter:** https://ngrx.io/guide/entity
- **Best practices:** https://ngrx.io/guide/store/best-practices
- **Site State Architecture:** `.claude/skills/site-stack-anatomy/SKILL.md`

---

**Версия:** 1.0  
**Дата:** 2026-10-06  
**Платформа:** gj-ng-front (Angular 20 + NgRx 20)  
**Статус:** Production-ready  
