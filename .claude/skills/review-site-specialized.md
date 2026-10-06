# 🔍 review-site-specialized.md

**Категория:** [REVIEW]  
**Платформа:** Site (gj-ng-front)  
**Версия:** 1.0  
**Статус:** Production-ready  
**Автор:** Claude Haiku 4.5 + team

---

## 📋 Описание

**Специализированный ревью для Site frontend-MR** (Angular best practices, Nx boundaries, state management, performance).

Этот скил используется **ревьюерами** для быстрого анализа MR по Site-компонентам.

**Когда использовать:**
- Ревьюить MR с изменениями в `libs/ui/`, `libs/core/`, `libs/modules/`
- Проверять соблюдение Nx module boundaries
- Анализировать state management паттерны
- Проверять тесты и покрытие
- Подтверждать выполнение pattern-development-flow

## 🔗 Используй паттерн

**ВСЕГДА следовать:** [pattern-review-standard.md](../orchestration/pattern-review-standard.md)

Reviewer-1: AC → Архит → Контракты → Расширяемость → Полнота
Reviewer-2: Security → Performance → Design → Readability → Tests

---

## 🎯 Чеклист ревью Site MR

### ФАЗА 1: Быстрая ориентация (2 мин)

```
☐ Читаю MR title и description
☐ Смотрю измененные файлы (list)
☐ Определяю scope: UI / State / Routing / Testing / etc
☐ Проверяю CI status (зелёные ли тесты?)

Для себя:
"Это фича X, меняет Y файлов, в основном в libs/ui/components/catalog/"
```

### ФАЗА 2: Архитектура (5 мин)

**Проверяю:**

```
Nx Module Boundaries

☐ Не нарушены ли границы между libs/?
  - libs/ui-kit/ → примитивы (кнопка, инпут)
  - libs/ui/ → модульные компоненты (корзина, товар)
  - libs/modules/ → feature-модули (их own компоненты)
  - libs/core/ → сервисы и store (не компоненты)
  
  ❌ Плохо: libs/modules/catalog импортирует из libs/modules/basket
  ✅ Хорошо: оба импортируют из libs/ui/components/shared

☐ Использует ли path aliases правильно?
  ✅ @ui, @ui-kit, @modules, @core, @shared
  ❌ '../../', '../../../'

Структура файлов

☐ Компонент в правильном месте?
  - new component в libs/ui-kit/ → примитив
  - new component в libs/ui/ → переиспользуемый
  - new component в libs/modules/X/ → feature-specific

☐ Index файлы обновлены для экспорта?
  ✅ libs/ui/src/index.ts содержит новый компонент
  ❌ Компонент есть, но не экспортирован

State Management (если есть изменения в store)

☐ Используется ли pattern: models → actions → reducer → effects → selectors?
☐ Effects: есть ли catchError обработка?
☐ Reducers: pure функции без mutations?
☐ Selectors: мемоизированы ли?
☐ Компоненты: используют ли селекторы (не $.subscribe)?
```

### ФАЗА 3: Компоненты (8 мин)

**Проверяю код:**

```typescript
// Структура компонента ✅
@Component({
  selector: 'gj-product-card',
  standalone: true,        // ← Angular 15+
  imports: [...],
  changeDetection: ChangeDetectionStrategy.OnPush,  // ← Оптимизация
})

// ✅ Правильно
☐ Standalone: true (не NgModule)
☐ ChangeDetectionStrategy.OnPush
☐ Inputs/Outputs типизированы
☐ Нет any типов
☐ Методы <20 строк
☐ Нет magic strings/numbers (использует const/enum)

// ❌ Неправильно
- @Component без standalone
- Default ChangeDetectionStrategy
- any типы
- Методы >50 строк
- Magic numbers: if (x > 10) {...}

// Template правила ✅
☐ *ngIf / *ngFor используют async pipe где нужно
☐ Нет {{ }} для сложной логики (в компоненте, не в template)
☐ Нет [innerHTML] (XSS уязвимость)
☐ Aria атрибуты для доступности
☐ Стили в .scss, не inline

// ❌ Template проблемы
- <div [innerHTML]="userInput"></div>
- {{ product?.name || product?.title || 'N/A' }}
- <button style="color: red;">OK</button>
- Отсутствие aria-label на иконках

// Стили (SCSS) ✅
☐ Используется @use (не @import)
☐ Переменные из shared (не hardcoded цвета)
☐ CSS Grid/Flexbox (не absolute positioning)
☐ Responsive через media queries
☐ BEM naming: .product-card__image-wrapper

// ❌ SCSS проблемы
- @import '@styles/colors'
- color: #FF0000 (hardcoded)
- position: absolute; top: 50px; left: 100px;
- .product-card_image (неправильный naming)
```

### ФАЗА 4: Тесты (5 мин)

**Проверяю:**

```
Unit Tests (Jest)

☐ Есть ли .spec.ts файл для нового кода?
☐ Coverage: >80% для компонентов, >75% для сервисов?

Количество тестов (правило):
- Новый компонент: минимум 8-10 тестов
- Новый сервис: минимум 6-8 тестов
- Новая pipe: минимум 4 теста

Качество тестов

☐ Не просто проверяет что код работает, а тестирует поведение
  ❌ it('должен создаться', () => { expect(component).toBeTruthy(); })
  ✅ it('должен показать "В наличии" если quantity > 0', () => {...})

☐ Есть ли edge-case тесты?
  ✅ Empty state (quantity = 0)
  ✅ Null/undefined inputs
  ✅ Большие значения (1000+ items)

☐ Mocking: правильно ли мокированы зависимости?
  ✅ HttpClientTestingModule для HTTP
  ✅ provideMockStore для NgRx store
  ✅ jasmine.createSpyObj для сервисов

E2E Tests (Cypress)

☐ Если MR меняет user-facing flow: есть ли e2e тест?
  ✅ checkout flow новый → e2e тест обязателен
  ✅ UI измена на кнопке → unit тест достаточно

☐ E2E использует ли data-testid атрибуты?
  ✅ cy.get('[data-testid="add-to-basket-btn"]')
  ❌ cy.get('button').first()  // flaky

Coverage Report

☐ CI показывает coverage? (должно быть в артефактах)
☐ Новый код покрыт? (>80%)
☐ Понизилось ли общее coverage? (красный флаг)
```

### ФАЗА 5: Security (3 мин)

**Проверяю:**

```
XSS защита

☐ Нет [innerHTML] без sanitizer
  ❌ <div [innerHTML]="userContent"></div>
  ✅ <div [innerHTML]="userContent | safeHtml"></div>

☐ Параметры в URL экранированы
  ❌ `/product?name={{ product.name }}`
  ✅ constructor(private route: ActivatedRoute) { ... }

Secrets & Credentials

☐ Нет hardcoded API ключей/passwords
  ❌ const API_KEY = 'sk-123abc'
  ✅ // Читать из environment

☐ Sensitive данные не логируются
  ❌ console.log('user email:', user.email)
  ✅ console.log('User loaded')

Interceptors & HTTPS

☐ Если добавлен новый HTTP client: использует ли interceptor?
  ✅ auth.interceptor добавляет авторизацию
  ✅ error.interceptor обрабатывает ошибки

CORS & Headers

☐ Не добавлены ли opaque headers?
  ✅ headers.set('Authorization', 'Bearer ...')
  ❌ headers.set('X-Custom', 'value') // может быть проблема
```

### ФАЗА 6: Performance (3 мин)

**Проверяю:**

```
Change Detection

☐ ChangeDetectionStrategy.OnPush везде?
  ✅ Компонент OnPush → быстрее
  ❌ Default change detection → замедляет app

☐ Нет бесконечных циклов подписок?
  ❌ ngOnInit() { this.data$.subscribe(d => this.data = d); }
      // Каждый раз трубочка пересоздаётся
  ✅ ngOnInit() { this.data$ = this.service.getData(); }
      // Подписка в template через async pipe

Memoization

☐ Selectors из NgRx мемоизированы?
  ✅ export const selectItems = createSelector(...)
  ❌ constructor(private store: Store) {
       this.items$ = this.store.pipe(
         map(s => s.items)  // Пересчитывается каждый раз
       );
     }

Bundle Size

☐ Добавлены ли тяжёлые зависимости без причины?
  ❌ npm install moment (200KB unminified)
  ✅ Использовать встроенный Intl API

Lazy Loading

☐ Большие модули lazy-loaded?
  ✅ {path: 'catalog', loadChildren: () => import('@modules/catalog')}
  ❌ import { CatalogModule } from '@modules/catalog';  // Eagerly loaded
```

### ФАЗА 7: Standards & Conventions (4 мин)

**Проверяю:**

```
Code Style

☐ eslint/stylelint проходят?
  ✅ CI зелёный
  ❌ Warning'и в коммитах

☐ Naming соглашения соблюдены?
  ✅ selector: 'gj-product-card'  // gj- префикс
  ✅ const productCount$ ($ для Observable)
  ✅ private _cache (_ для private)

☐ Комментарии только "почему", не "что"?
  ✅ // Используем OnPush для оптимизации change detection
  ❌ // Увеличиваем счётчик
  ❌ // TODO: переделать позже

Documentation

☐ Компоненты документированы для Storybook?
  ✅ *.stories.ts файлы есть для new UI компонентов
  ❌ Новый компонент есть, но нет story

☐ API документирована?
  ✅ @Input / @Output имеют JSDoc комментарии
  ❌ @Input() data: any;  // Что это вообще?

Git & MR

☐ Commits読める?
  ✅ "feat(catalog): add product card component"
  ❌ "fix", "update", "aaa", "WIP"

☐ Branch name correct?
  ✅ feature/OPSOMN002-XXX, fix/OPSOMN002-XXX
  ❌ my-branch, feature-new-thing

☐ MR description полная?
  ✅ "Добавляем X, меняем Y, закрывает OPSOMN002-XXX"
  ❌ "Fixes #123" (без контекста)

Pattern-Development-Flow

☐ Все 7 шагов выполнены?
  ✅ 1. Понимание → 2. План → 3. Код → 4. Security → 5. Тесты → 6. Коммит → 7. MR
  ❌ "Написал код, сделал коммит" (шаги пропущены)
```

### ФАЗА 8: Проверка на типичные ошибки Site (5 мин)

**Антипаттерны Site:**

```
Route Guards & SSR

☐ Защищённые маршруты имеют AuthGuard?
  ✅ { path: 'checkout', canActivate: [AuthGuard] }
  ❌ { path: 'checkout' }  // Любой может зайти

☐ Компоненты проверяют platformService перед window/localStorage?
  ✅ if (this.platformService.browser) { localStorage.setItem(...) }
  ❌ localStorage.setItem(...)  // Падает на сервере

State Management

☐ Данные в Store или в Component state?
  ✅ Глобальное состояние (user, auth, basket) → Store
  ✅ Local UI состояние (dropdown open/close) → @State() in component
  ❌ Важные данные в Component state без сохранения

☐ Effects правильно обрабатывают ошибки?
  ✅ switchMap(...).pipe(catchError(...))
  ❌ Без catchError (может зависнуть)

i18n & Localization

☐ Все текст пользователя переведены?
  ✅ {{ 'catalog.product.addToBasket' | translate | async }}
  ❌ <button>Add to Basket</button>  // Только на английском

☐ Используются ли форматирование по локали?
  ✅ {{ price | currencyLocale }}
  ❌ {{ price }}  // Без форматирования по языку

Integration Issues

☐ API контракты не сломаны?
  ✅ Меняем компонент, API contracts остаются same
  ❌ Меняем DTO название, но backend не обновили

☐ BFF endpoint существует?
  ✅ /api/v2/catalog/products ← существует
  ❌ /api/v3/catalog/items ← новый endpoint, не создан

TypeScript

☐ Нет any типов?
  ✅ function process(data: Product[]): string { ... }
  ❌ function process(data: any): any { ... }

☐ Union типы используются правильно?
  ✅ type Status = 'pending' | 'success' | 'error'
  ❌ type Status = string  // Потеряна type safety
```

---

## 🎯 Decision Matrix: Approve или Request Changes?

### APPROVE ✅ Если:
- [ ] Все тесты зелёные (CI)
- [ ] Architecture правильна (Nx boundaries OK)
- [ ] Code соответствует conventions
- [ ] Security checks пройдены
- [ ] Performance нормальная
- [ ] 7 шагов pattern-development-flow видны
- [ ] Комментарии конструктивные (максимум 2-3 замечания)

### REQUEST CHANGES 🔴 Если:
- [ ] Tests <75% coverage
- [ ] Нарушены Nx boundaries (критично)
- [ ] XSS или security issues
- [ ] Performance regression (bundle +50KB+)
- [ ] Нет edge-case тестов для critical path
- [ ] 3+ шага pattern-development-flow пропущены
- [ ] Hardcoded secrets/API keys

### COMMENT / SUGGEST 🟡 Если:
- [ ] Можно улучшить (но не критично)
- [ ] Style замечания (линтер не ловит)
- [ ] Predpository suggestions (типо "можешь использовать")
- [ ] Questions про intention

---

## 💬 Типовые комментарии ревьюера

### Позитивные замечания

```
✅ Отличная структура компонента, clean separation of concerns
✅ Tests очень подробные, покрывают edge cases
✅ Performance оптимизация через OnPush хороша
```

### Просьба на исправление

```
🔴 MUST FIX: Не хватает aria-label на иконке (accessibility)
   → Добавьте aria-label="Добавить в корзину"

🔴 MUST FIX: [innerHTML] без sanitizer может быть XSS
   → Используйте safeHtml pipe или textContent

🔴 MUST FIX: Coverage упал с 82% на 73%, нужны тесты
   → Добавьте unit тесты для новой логики
```

### Вопросы

```
🟡 Вопрос: Почему используется switchMap вместо concatMap в effect?
   → Уточните, нужна ли отмена предыдущего запроса

🟡 Вопрос: Product.description может быть null?
   → Проверьте edge case когда description отсутствует
```

### Suggestions (опционально)

```
💡 Подсказка: Можешь использовать createEntityAdapter для селекторов
   → Это упростит код в basket.selectors.ts

💡 Подсказка: Стоит кэшировать результат в localStorage
   → Пользователь не теряет данные при перезагрузке
```

---

## 📊 Метрики ревью

**Запомни:**
- ⏱️ Время ревью: 20-30 мин для типичного MR (200-500 строк)
- 📝 Комментариев: 1-5 замечаний на MR (в среднем)
- ✅ Approval rate: 70%+ MR должны пройти без REQUEST CHANGES
- 🔴 Blocker rate: <20% MR требуют fixes

---

## 🚀 Чек-лист перед Approve

```
Прежде чем нажать "Approve":

☐ Полностью прочитал diff (не пропустил важное)
☐ Все CI checks зелёные
☐ Нет security issues
☐ Code соответствует standards
☐ Tests адекватные
☐ Performance OK
☐ Я смог бы поддерживать этот код в будущем

Если хотя бы одно "нет" → Request Changes или добавить комментарий
```

---

## 📚 Ссылки на скилы Site

- **develop-site-ui.md** — UI компоненты
- **develop-site-state.md** — NgRx state management
- **develop-site-routing.md** — Маршруты и navigation
- **develop-site-ssr.md** — Server-side rendering
- **develop-site-i18n.md** — Интернационализация
- **develop-site-testing.md** — Тесты (Jest + Cypress)
- **site-stack-anatomy.md** — Общая архитектура Site
- **site-angular-conventions.md** — Angular соглашения

---

**Версия:** 1.0  
**Дата:** 2026-10-06  
**Платформа:** gj-ng-front  
**Статус:** Production-ready  
**Время ревью:** ~20-30 мин на MR  
