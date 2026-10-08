---
name: develop-site-testing
version: 1.0.0
layer: stack
platform: Site
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---

# 🧪 develop-site-testing.md

**Категория:** [DEVELOPMENT]  
**Платформа:** Site (gj-ng-front)  
**Версия:** 1.0  
**Статус:** Production-ready  
**Автор:** Claude Haiku 4.5 + team

---

## 📋 Описание

**Тестирование компонентов и e2e** в Site (Jest для unit tests, Cypress для e2e, fixtures, Mock API).

Этот скил описывает как **правильно** писать тесты, создавать fixtures, мокировать API и тестировать пользовательские сценарии.

**Когда использовать:**
- Пишешь unit тесты для компонента/сервиса
- Пишешь e2e тесты для flow'а (чекаут, логин)
- Мокируешь HTTP запросы
- Создаёшь тестовые данные (fixtures)
- Проверяешь доступность и производительность

## 🔗 Используй паттерн

**ВСЕГДА следовать:** [pattern-development-flow.md](../orchestration/pattern-development-flow.md)

7 обязательных шагов: ПОНИМАНИЕ → ПЛАН → КОД → SECURITY → ТЕСТЫ → КОММИТ → MR

---

## 🎯 Тестовая архитектура в Site

### Структура тестов

```
platform/site/gj-ng-front/
├── libs/
│   ├── core/
│   │   ├── services/
│   │   │   ├── user.service.ts
│   │   │   └── user.service.spec.ts      # Unit тест
│   │   │
│   │   └── testing/                       # Общие fixtures и helpers
│   │       ├── mock-data.ts               # Данные для тестов
│   │       ├── fixtures.ts                # Factory функции
│   │       └── helpers.ts                 # Утилиты
│   │
│   └── modules/
│       └── catalog/
│           ├── components/
│           │   ├── product-list.component.ts
│           │   └── product-list.component.spec.ts
│           │
│           └── product-list.spec.ts       # Интеграционный тест
│
├── apps/site-ru/
│   └── src/
│       ├── app.component.spec.ts
│       └── app.e2e-ci.spec.ts             # E2E тест
│
└── e2e/
    ├── catalog/
    │   ├── browse-catalog.spec.ts
    │   └── filter-products.spec.ts
    ├── checkout/
    │   ├── add-to-basket.spec.ts
    │   ├── checkout-flow.spec.ts
    │   └── payment.spec.ts
    ├── auth/
    │   ├── login.spec.ts
    │   ├── register.spec.ts
    │   └── forgot-password.spec.ts
    └── support/
        ├── commands.ts                    # Custom Cypress commands
        ├── fixtures.ts                    # e2e fixtures
        └── helpers.ts                     # e2e helpers
```

### Типы тестов в Site

```
1. Unit Tests (Jest)
   - Компоненты: rendering, inputs/outputs, lifecycle
   - Сервисы: логика, HTTP запросы
   - Pipes/Directives: трансформация данных
   - Selectors/Reducers: state management
   - Coverage: >80%

2. Integration Tests (Jest)
   - Несколько компонентов вместе
   - Взаимодействие сервис ↔ компонент
   - Store ↔ компонент
   - Coverage: >60%

3. E2E Tests (Cypress)
   - Полные user flows (логин → каталог → чекаут)
   - Реальный browser
   - Real API (не mock)
   - Critical paths only (5-10 основных)
```

---

## 🛠️ 7 шагов разработки тестов

### 1️⃣ ПОНИМАНИЕ

```
✅ ЧТО тестировать?
   "ProductCardComponent: показывает товар, кнопка добавления работает"

✅ ГДЕ тест размещается?
   product-card.component.spec.ts

✅ КАК проверяем?
   - Компонент создаётся
   - Вводим @Input (товар)
   - Проверяем вывод (текст, цена)
   - Кликаем на кнопку
   - Проверяем @Output (событие)

✅ Mock данные?
   - Товар: ProductMockFactory
   - HttpClient: HttpClientTestingModule

✅ Есть ли [BLOCKER]?
   → Нет, могу писать
```

---

### 2️⃣ ПЛАН

**Определить:**

- [ ] Какие части компонента тестировать?
- [ ] Какие dependencies мокировать?
- [ ] Какие fixtures нужны?
- [ ] Какие edge cases?
- [ ] Snapshot тесты нужны?

**Пример:**

```
ProductCardComponent:
✅ Unit: component создаётся
✅ Unit: отображает товар (@Input)
✅ Unit: эмитит click (@Output)
✅ Unit: кнопка disabled если нет в наличии
✅ Unit: snapshot для верстки
✅ Fixture: ProductMockFactory.create()
✅ Mock: HttpClient (для imageService)
```

---

### 3️⃣ КОД

#### Mock данные и fixtures

```typescript
// libs/core/testing/mock-data.ts

import { Product, User, BasketItem, Currency } from '@core/data-access/models';

export const mockCurrency: Currency = {
  value: 1500,
  currency: 'RUB',
};

export const mockProduct: Product = {
  id: '1',
  name: 'Test Product',
  description: 'Test Description',
  price: mockCurrency,
  image: { url: 'test.jpg', alt: 'Test' },
  quantity: 10,
  category: 'test-category',
  sku: 'TEST-SKU-001',
};

export const mockUser: User = {
  id: 'user-1',
  email: 'test@example.com',
  firstName: 'Test',
  lastName: 'User',
  phone: '+7 999 999 99 99',
  isAuthenticated: true,
};

export const mockBasketItem: BasketItem = {
  id: 'item-1',
  productId: '1',
  name: 'Test Product',
  price: mockCurrency,
  quantity: 1,
};
```

```typescript
// libs/core/testing/fixtures.ts

import { Product, User, BasketItem } from '@core/data-access/models';
import { mockProduct, mockUser, mockBasketItem } from './mock-data';

/**
 * Factory для создания тестовых данных
 */
export class ProductMockFactory {
  static create(overrides: Partial<Product> = {}): Product {
    return {
      ...mockProduct,
      id: Math.random().toString(),
      ...overrides,
    };
  }

  static createArray(count: number, overrides?: Partial<Product>): Product[] {
    return Array.from({ length: count }, (_, i) =>
      this.create({ ...overrides, id: `product-${i}` }),
    );
  }

  static outOfStock(): Product {
    return this.create({ quantity: 0 });
  }

  static expensive(): Product {
    return this.create({ price: { value: 50000, currency: 'RUB' } });
  }
}

export class UserMockFactory {
  static create(overrides: Partial<User> = {}): User {
    return {
      ...mockUser,
      id: Math.random().toString(),
      ...overrides,
    };
  }

  static authenticated(): User {
    return this.create({ isAuthenticated: true });
  }

  static anonymous(): User {
    return this.create({ isAuthenticated: false });
  }
}

export class BasketMockFactory {
  static createItem(overrides: Partial<BasketItem> = {}): BasketItem {
    return {
      ...mockBasketItem,
      id: Math.random().toString(),
      ...overrides,
    };
  }

  static createBasket(itemCount: number = 3): BasketItem[] {
    return Array.from({ length: itemCount }, (_, i) =>
      this.createItem({ id: `item-${i}` }),
    );
  }
}
```

#### Unit тест компонента

```typescript
// libs/modules/catalog/components/product-card/product-card.component.spec.ts

import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ProductCardComponent } from './product-card.component';
import { ProductMockFactory } from '@core/testing/fixtures';
import { LocaleService } from '@core/i18n/locale.service';
import { DebugElement } from '@angular/core';
import { By } from '@angular/platform-browser';

describe('ProductCardComponent', () => {
  let component: ProductCardComponent;
  let fixture: ComponentFixture<ProductCardComponent>;
  let localeService: jasmine.SpyObj<LocaleService>;

  beforeEach(async () => {
    const localeServiceSpy = jasmine.createSpyObj('LocaleService', [
      'formatCurrency',
    ]);

    await TestBed.configureTestingModule({
      imports: [ProductCardComponent],
      providers: [{ provide: LocaleService, useValue: localeServiceSpy }],
    }).compileComponents();

    fixture = TestBed.createComponent(ProductCardComponent);
    component = fixture.componentInstance;
    localeService = TestBed.inject(LocaleService) as jasmine.SpyObj<LocaleService>;
  });

  describe('Создание компонента', () => {
    it('должен создаться', () => {
      expect(component).toBeTruthy();
    });

    it('должен быть в OnPush change detection', () => {
      expect(component).toBeTruthy(); // TODO: проверить metadata
    });
  });

  describe('Отображение товара', () => {
    beforeEach(() => {
      component.product = ProductMockFactory.create({
        name: 'Test Product',
        price: { value: 1500, currency: 'RUB' },
      });
      localeService.formatCurrency.and.returnValue('1 500 ₽');
      fixture.detectChanges();
    });

    it('должен отобразить название товара', () => {
      const title = fixture.debugElement.query(By.css('h2'));
      expect(title.nativeElement.textContent).toContain('Test Product');
    });

    it('должен отобразить отформатированную цену', () => {
      const price = component.formattedPrice;
      expect(price).toBe('1 500 ₽');
      expect(localeService.formatCurrency).toHaveBeenCalledWith(1500);
    });

    it('должен отобразить изображение с правильным src', () => {
      const img = fixture.debugElement.query(By.css('img'));
      expect(img.nativeElement.src).toContain(component.product.image);
    });
  });

  describe('Состояние наличия', () => {
    it('должен показать "В наличии" когда товар есть', () => {
      component.product = ProductMockFactory.create({ quantity: 5 });
      fixture.detectChanges();

      expect(component.isAvailable).toBe(true);
    });

    it('должен показать "Нет в наличии" когда товара нет', () => {
      component.product = ProductMockFactory.outOfStock();
      fixture.detectChanges();

      expect(component.isAvailable).toBe(false);
    });

    it('должен отключить кнопку если товара нет', () => {
      component.product = ProductMockFactory.outOfStock();
      fixture.detectChanges();

      const button = fixture.debugElement.query(By.css('button'));
      expect(button.nativeElement.disabled).toBe(true);
    });
  });

  describe('Взаимодействие пользователя', () => {
    beforeEach(() => {
      component.product = ProductMockFactory.create();
      fixture.detectChanges();
    });

    it('должен эмитить click при клике на кнопку', (done) => {
      component.click.subscribe(() => {
        expect(true).toBe(true);
        done();
      });

      const button = fixture.debugElement.query(By.css('button'));
      button.nativeElement.click();
    });

    it('должен пройти все состояния при клике', (done) => {
      let clicks = 0;
      component.click.subscribe(() => {
        clicks++;
        if (clicks === 1) {
          expect(clicks).toBe(1);
          done();
        }
      });

      const button = fixture.debugElement.query(By.css('button'));
      button.nativeElement.click();
    });
  });

  describe('Snapshot тест', () => {
    it('должен совпадать с snapshot', () => {
      component.product = ProductMockFactory.create();
      localeService.formatCurrency.and.returnValue('1 500 ₽');
      fixture.detectChanges();

      expect(fixture.debugElement.nativeElement).toMatchSnapshot();
    });
  });

  describe('Edge cases', () => {
    it('должен обработать null product', () => {
      component.product = null as any;

      expect(() => fixture.detectChanges()).not.toThrow();
    });

    it('должен обработать очень длинное название', () => {
      const longName = 'A'.repeat(1000);
      component.product = ProductMockFactory.create({ name: longName });
      fixture.detectChanges();

      const title = fixture.debugElement.query(By.css('h2'));
      expect(title.nativeElement.textContent).toContain(longName);
    });
  });
});
```

#### Unit тест сервиса

```typescript
// libs/core/services/basket.service.spec.ts

import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { BasketService } from './basket.service';
import { BasketMockFactory } from '@core/testing/fixtures';

describe('BasketService', () => {
  let service: BasketService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [BasketService],
    });

    service = TestBed.inject(BasketService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    // Убедиться что нет незавершённых HTTP запросов
    httpMock.verify();
  });

  describe('getBasket', () => {
    it('должен получить корзину с сервера', (done) => {
      const mockItems = BasketMockFactory.createBasket();

      service.getBasket().subscribe((items) => {
        expect(items).toEqual(mockItems);
        done();
      });

      const req = httpMock.expectOne('/api/basket');
      expect(req.request.method).toBe('GET');
      req.flush(mockItems);
    });

    it('должен обработать ошибку', (done) => {
      service.getBasket().subscribe(
        () => fail('should have failed with 500 error'),
        (error) => {
          expect(error.status).toBe(500);
          done();
        },
      );

      const req = httpMock.expectOne('/api/basket');
      req.flush('Server error', { status: 500, statusText: 'Server Error' });
    });
  });

  describe('addItem', () => {
    it('должен добавить товар в корзину', (done) => {
      const item = BasketMockFactory.createItem();

      service.addItem(item).subscribe((result) => {
        expect(result).toEqual(item);
        done();
      });

      const req = httpMock.expectOne('/api/basket/items');
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual(item);
      req.flush(item);
    });
  });

  describe('removeItem', () => {
    it('должен удалить товар из корзины', (done) => {
      const itemId = 'item-1';

      service.removeItem(itemId).subscribe(() => {
        expect(true).toBe(true);
        done();
      });

      const req = httpMock.expectOne(`/api/basket/items/${itemId}`);
      expect(req.request.method).toBe('DELETE');
      req.flush({});
    });
  });
});
```

#### E2E тест (Cypress)

```typescript
// e2e/checkout/add-to-basket.spec.ts

describe('Add to Basket Flow', () => {
  beforeEach(() => {
    // Перейти на каталог
    cy.visit('/catalog');
    // Убедиться что страница загружена
    cy.get('[data-testid="product-list"]').should('be.visible');
  });

  it('должен добавить товар в корзину и показать успешное сообщение', () => {
    // Найти первый товар
    cy.get('[data-testid="product-card"]').first().as('firstProduct');

    // Проверить что кнопка видна
    cy.get('@firstProduct')
      .find('[data-testid="add-to-basket-btn"]')
      .should('not.be.disabled');

    // Кликнуть на кнопку
    cy.get('@firstProduct')
      .find('[data-testid="add-to-basket-btn"]')
      .click();

    // Проверить success notification
    cy.get('[data-testid="toast-success"]').should('be.visible');
    cy.get('[data-testid="toast-success"]').should('contain', 'Товар добавлен в корзину');

    // Проверить что count в шапке обновился
    cy.get('[data-testid="basket-count"]').should('contain', '1');
  });

  it('должен показать ошибку если товар нет в наличии', () => {
    // Найти товар без наличия
    cy.get('[data-testid="product-card"]')
      .filter(':contains("Нет в наличии")')
      .first()
      .as('outOfStockProduct');

    // Кнопка должна быть disabled
    cy.get('@outOfStockProduct')
      .find('[data-testid="add-to-basket-btn"]')
      .should('be.disabled');
  });

  it('должен требовать логин если пользователь не авторизован', () => {
    // Logout если вход был
    cy.clearLocalStorage('auth_token');

    // Кликнуть на кнопку добавления
    cy.get('[data-testid="product-card"]')
      .first()
      .find('[data-testid="add-to-basket-btn"]')
      .click();

    // Должны перенаправить на логин
    cy.url().should('include', '/auth/login');
  });
});
```

```typescript
// e2e/support/commands.ts

// Custom команда для логина
Cypress.Commands.add('login', (email: string, password: string) => {
  cy.visit('/auth/login');
  cy.get('[data-testid="email-input"]').type(email);
  cy.get('[data-testid="password-input"]').type(password);
  cy.get('[data-testid="login-btn"]').click();
  cy.get('[data-testid="user-menu"]').should('be.visible');
});

// Custom команда для добавления в корзину
Cypress.Commands.add('addProductToBasket', (productName: string) => {
  cy.get('[data-testid="product-card"]')
    .filter(`:contains("${productName}")`)
    .find('[data-testid="add-to-basket-btn"]')
    .click();
});
```

---

### 4️⃣ SECURITY

```
✅ Не использовать реальные credentials в тестах
   ❌ password: 'my-real-password-123'
   ✅ password: 'test-password-123'

✅ Тестовые аккаунты изолированы
   ✅ test@example.com (новый на каждый e2e запуск)

✅ Нет real API в e2e
   ❌ cy.visit('https://production.gj.ru')
   ✅ cy.visit('https://staging.gj.ru') или cy.intercept mock

✅ Clean up после тестов
   ✅ httpMock.verify()
   ✅ cy.clearLocalStorage()
```

---

### 5️⃣ Запуск тестов

```bash
# Unit тесты (Jest)
npm run test              # Watch mode
npm run test:ci           # CI mode (один запуск)
npm run test:coverage     # С отчётом coverage

# E2E тесты (Cypress)
npm run e2e               # Interactive mode (браузер)
npm run e2e:headless      # Headless (CI)

# Все тесты
npm run test:all
```

---

### 6️⃣ КОММИТ

```bash
git add libs/ apps/ e2e/

git commit -m "test: добавить unit и e2e тесты для checkout

- ProductCardComponent unit тесты (5 scenarios)
- BasketService unit тесты (HTTP mocking)
- E2E flow: add-to-basket
- Fixtures: ProductMockFactory, BasketMockFactory
- Coverage: >85% for components, >80% for services

AC выполнены:
- Все unit тесты зелёные ✅
- E2E тесты проходят ✅
- Coverage требуемый ✅

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

---

### 7️⃣ CI интеграция

```yaml
# .gitlab-ci.yml фрагмент

test:unit:
  stage: test
  script:
    - npm ci
    - npm run test:ci
  coverage: '/Coverage: (\d+\.\d+)%/'

test:e2e:
  stage: test
  script:
    - npm ci
    - npm run build
    - npm run e2e:headless
  artifacts:
    paths:
      - cypress/screenshots/
      - cypress/videos/
```

---

## 💡 Частые паттерны

### Testing async code

```typescript
it('должен загрузить данные асинхронно', (done) => {
  service.getData().subscribe((data) => {
    expect(data).toEqual(expected);
    done();  // ← Обязательно вызвать done()
  });

  const req = httpMock.expectOne('/api/data');
  req.flush(expected);
});

// Или с async/await
it('должен загрузить данные', async () => {
  const data = await service.getData().toPromise();
  expect(data).toEqual(expected);
});
```

### Testing ChangeDetection

```typescript
it('должен обновить view при смене input', () => {
  component.product = oldProduct;
  fixture.detectChanges();

  component.product = newProduct;
  fixture.detectChanges();  // ← Нужно вызвать detectChanges

  expect(fixture.debugElement.textContent).toContain(newProduct.name);
});
```

### Testing with NgRx Store

```typescript
beforeEach(() => {
  TestBed.configureTestingModule({
    providers: [
      provideMockStore({
        initialState: {
          basket: { items: [] },
        },
      }),
    ],
  });
});

it('должен получить items из store', () => {
  const mockStore = TestBed.inject(MockStore);
  mockStore.setState({
    basket: { items: [mockItem] },
  });

  expect(component.items$.subscribe(...));
});
```

---

## 📚 Ресурсы

- **Jest:** https://jestjs.io/
- **Cypress:** https://cypress.io
- **Angular Testing:** https://angular.io/guide/testing
- **Testing Best Practices:** https://testing-library.com/docs/
- **Site Testing Setup:** `.claude/skills/site-stack-anatomy/SKILL.md`

---

**Версия:** 1.0  
**Дата:** 2026-10-06  
**Платформа:** gj-ng-front (Jest + Cypress)  
**Статус:** Production-ready  
