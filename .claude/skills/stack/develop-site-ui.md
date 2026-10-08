---
name: develop-site-ui
version: 1.0.0
layer: stack
platform: Site
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---

# 🎨 develop-site-ui.md

**Категория:** [DEVELOPMENT]  
**Платформа:** Site (gj-ng-front)  
**Версия:** 1.0  
**Статус:** Production-ready  
**Автор:** Claude Haiku 4.5 + team

---

## 📋 Описание

**Разработка UI-компонентов и визуальных элементов** в Site (Angular 20 + Material + Nx + Storybook).

Этот скил описывает как **правильно** добавлять новые компоненты, модифицировать существующие, стилизовать их и документировать в Storybook.

**Когда использовать:**
- Добавляешь новый компонент (карточка, кнопка, форма, модальное окно)
- Меняешь существующий компонент
- Обновляешь стили (SCSS, CSS modules)
- Документируешь в Storybook
- Работаешь с Material Design CDK

## 🔗 Используй паттерн

**ВСЕГДА следовать:** [pattern-development-flow.md](../orchestration/pattern-development-flow.md)

7 обязательных шагов: ПОНИМАНИЕ → ПЛАН → КОД → SECURITY → ТЕСТЫ → КОММИТ → MR

---

## 🎯 Структура Site UI

### Иерархия компонентов

```
libs/
├── ui-kit/                    # 🟢 Примитивы (кнопки, инпуты, иконки)
│   ├── components/
│   │   ├── buttons/           # Кнопки всех типов
│   │   ├── form-controls/     # Инпуты, селекты, чекбоксы
│   │   ├── typography/        # Заголовки, текст
│   │   ├── icons/             # SVG иконки, Material icons
│   │   └── layout/            # Grid, flex, container
│   ├── styles/                # Глобальные переменные (colors, sizes)
│   ├── storybook/             # Истории примитивов
│   └── types/                 # Общие TS типы для UI
│
├── ui/                        # 🟠 Модульные компоненты (высокоуровневые)
│   ├── components/
│   │   ├── basket-summary/    # Компонент сводки корзины
│   │   ├── product-card/      # Карточка товара
│   │   ├── checkout-form/     # Форма чекаута
│   │   ├── header/            # Шапка сайта
│   │   └── footer/            # Подвал
│   ├── modals/                # Модальные окна
│   ├── drawers/               # Боковые панели
│   ├── storybook/             # Истории модульных компонентов
│   └── styles/                # Локальные переопределения
│
└── modules/{basket,catalog,checkout,home,profile}/
    ├── components/            # Специфичные для модуля компоненты
    ├── styles/                # Модуль-специфичные стили
    └── templates/             # Пейджи
```

### Размещение нового компонента

**Правило:** Где компонент используется?

| Используется | Размещение | Пример |
|-------------|------------|--------|
| В одном месте | В том же модуле | `modules/basket/components/basket-empty/` |
| 2-3 модуля | `libs/ui/components/` | `product-card/` |
| Везде + примитив | `libs/ui-kit/components/` | `button-primary/` |
| Специфичный ввод | `libs/ui-kit/form-controls/` | `phone-input/` |

**Не допускается:**
- Копировать компонент в разные места
- Хранить UI-специфичные компоненты в `modules/*/services/`
- Дублировать стили

---

## 🛠️ 7 шагов разработки UI-компонента

### 1️⃣ ПОНИМАНИЕ

**Спросить себя:**

```
✅ ЧТО компонент делает?
   "Показывает сумму товаров в корзине с иконкой и количеством"

✅ ГДЕ используется?
   "На главной странице, в меню, в модальном окне → libs/ui/components/"

✅ ЧТО принимает (Input)?
   {
     quantity: number;        // кол-во товаров
     totalPrice: Currency;    // сумма
     isLoading?: boolean;     // показать спиннер?
   }

✅ ЧТО отправляет (Output)?
   @Output() click = new EventEmitter<void>();  // клик

✅ Есть ли [BLOCKER]?
   → Нет, могу писать
```

**Не начинать код до полного ПОНИМАНИЯ!**

---

### 2️⃣ ПЛАН

**Определить:**

- [ ] Путь компонента
- [ ] Импорты (Material, общие библиотеки)
- [ ] Зависимости от других компонентов
- [ ] Стили (scss, css, tailwind?)
- [ ] Storybook истории
- [ ] Тесты (unit + snapshot)

**Пример плана:**

```
Файлы:
✅ libs/ui/components/basket-summary/basket-summary.component.ts
✅ libs/ui/components/basket-summary/basket-summary.component.html
✅ libs/ui/components/basket-summary/basket-summary.component.scss
✅ libs/ui/components/basket-summary/basket-summary.component.spec.ts
✅ libs/ui/components/basket-summary/basket-summary.stories.ts
✅ libs/ui/components/basket-summary/index.ts (экспорт)

Импорты:
✅ @angular/core (Component, Input, Output, EventEmitter)
✅ @angular/material/button
✅ @shared/types (Currency, PriceFormatter)
✅ @shared/icons (CartIcon)

Storybook:
✅ История с разными количествами (0, 1, 10, 999)
✅ История с загрузкой (isLoading=true)
✅ История с кликом (проверить emit)

Тесты:
✅ Компонент создаётся
✅ Отображает правильное количество
✅ Эмитит click при клике
✅ Snapshot для внешнего вида
```

---

### 3️⃣ КОД

#### TypeScript (компонент)

```typescript
// libs/ui/components/basket-summary/basket-summary.component.ts

import { Component, Input, Output, EventEmitter, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { PriceFormatterPipe } from '@shared/pipes/price-formatter.pipe';
import { Currency } from '@shared/types/currency';
import { CartIcon } from '@shared/icons/cart.icon';

@Component({
  selector: 'gj-basket-summary',
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    PriceFormatterPipe,
    CartIcon,
  ],
  templateUrl: './basket-summary.component.html',
  styleUrls: ['./basket-summary.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BasketSummaryComponent {
  // Входные параметры
  @Input() quantity: number = 0;
  @Input() totalPrice: Currency | null = null;
  @Input() isLoading: boolean = false;

  // Выходные события
  @Output() click = new EventEmitter<void>();

  // Метод для обработки клика
  onBasketClick(): void {
    // Проверка: не отправляем событие если загружается
    if (!this.isLoading) {
      this.click.emit();
    }
  }

  // Вычисляемое свойство: есть ли товары в корзине?
  get hasItems(): boolean {
    return this.quantity > 0;
  }

  // Форматирование количества для отображения
  get displayQuantity(): string {
    if (this.quantity > 99) {
      return '99+';
    }
    return this.quantity.toString();
  }
}
```

**Правила кода:**
- ✅ `ChangeDetectionStrategy.OnPush` для оптимизации
- ✅ Standalone компонент (Angular 15+)
- ✅ CommonModule для *ngIf, *ngFor
- ✅ Комментарии только почему (не повторяют имена переменных)
- ✅ Методы < 20 строк
- ✅ Нет magic strings/numbers

#### HTML (шаблон)

```html
<!-- libs/ui/components/basket-summary/basket-summary.component.html -->

<button
  mat-icon-button
  [disabled]="isLoading"
  (click)="onBasketClick()"
  aria-label="Открыть корзину"
  class="basket-button"
  [class.basket-button--has-items]="hasItems"
>
  <!-- Иконка корзины -->
  <mat-icon svgIcon="cart" class="basket-icon"></mat-icon>

  <!-- Спиннер загрузки -->
  <mat-spinner
    *ngIf="isLoading"
    diameter="20"
    strokeWidth="2"
    class="basket-spinner"
  ></mat-spinner>

  <!-- Бадж с количеством товаров -->
  <span
    *ngIf="hasItems && !isLoading"
    class="basket-badge"
    [attr.aria-label]="'В корзине ' + quantity + ' товаров'"
  >
    {{ displayQuantity }}
  </span>

  <!-- Цена (для режима с большой иконкой) -->
  <span
    *ngIf="totalPrice && !isLoading"
    class="basket-price"
  >
    {{ totalPrice | priceFormatter }}
  </span>
</button>
```

**Правила HTML:**
- ✅ Доступность: `aria-label`, `disabled`
- ✅ Нет inline styles
- ✅ Нет {{}} кроме простых вычислений
- ✅ Логика в компоненте (*.ts), не в шаблоне

#### SCSS (стили)

```scss
// libs/ui/components/basket-summary/basket-summary.component.scss

@use '@shared/styles/variables' as *;
@use '@shared/styles/mixins' as *;

// Используем переменные из theme
.basket-button {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: $spacing-xs;

  // Базовый цвет из Material palette
  color: var(--primary-color, #333);
  transition: all 200ms ease-in-out;

  &:hover:not(:disabled) {
    color: var(--primary-dark, #111);
    background-color: rgba(0, 0, 0, 0.04);
  }

  &:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }

  // Состояние: есть товары в корзине
  &--has-items {
    color: var(--accent-color, #e91e63);
    font-weight: 600;
  }
}

.basket-icon {
  font-size: 24px;
  width: 24px;
  height: 24px;
}

// Бадж с количеством
.basket-badge {
  position: absolute;
  top: -8px;
  right: -8px;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 4px;
  background-color: var(--error-color, #f44336);
  color: white;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 700;
  animation: badgeAppear 200ms ease-out;
}

@keyframes badgeAppear {
  from {
    transform: scale(0);
    opacity: 0;
  }
  to {
    transform: scale(1);
    opacity: 1;
  }
}

// Спиннер загрузки
.basket-spinner {
  position: absolute;
  opacity: 0.7;
}

// Цена товаров
.basket-price {
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
}

// Responsive: на мобилке скрыть цену
@media (max-width: $breakpoint-md) {
  .basket-price {
    display: none;
  }
}
```

**Правила SCSS:**
- ✅ Используем `@use` (не @import)
- ✅ Переменные через `var(--custom-prop)` для динамических тем
- ✅ Breakpoints из переменных
- ✅ Нет абсолютных px (использовать $spacing-*, $size-*)
- ✅ Вложенность максимум 3 уровня

---

### 4️⃣ SECURITY

**Что проверяем:**

```
✅ XSS: не используем [innerHTML]
   ❌ <span [innerHTML]="userInput"></span>
   ✅ <span>{{ userInput }}</span>

✅ Нет hardcoded URL/API ключей
   ❌ const API_KEY = "sk-123abc";
   ✅ Читаем из environment

✅ ARIA доступность (не только красота)
   ✅ aria-label для иконок
   ✅ aria-disabled для disabled состояния

✅ Нет sensitive данных в console/logs
   ❌ console.log('userEmail:', email);
   ✅ console.log('User data loaded');
```

**Автоматические проверки:**
```bash
cd libs/ui
npm run lint:scss  # stylelint
npm run lint:ts    # eslint
```

---

### 5️⃣ ТЕСТЫ

```typescript
// libs/ui/components/basket-summary/basket-summary.component.spec.ts

import { ComponentFixture, TestBed } from '@angular/core/testing';
import { BasketSummaryComponent } from './basket-summary.component';
import { Currency } from '@shared/types/currency';

describe('BasketSummaryComponent', () => {
  let component: BasketSummaryComponent;
  let fixture: ComponentFixture<BasketSummaryComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [BasketSummaryComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(BasketSummaryComponent);
    component = fixture.componentInstance;
  });

  it('должен создаться', () => {
    expect(component).toBeTruthy();
  });

  describe('displayQuantity', () => {
    it('должен отобразить количество < 100', () => {
      component.quantity = 5;
      expect(component.displayQuantity).toBe('5');
    });

    it('должен показать 99+ для количества > 99', () => {
      component.quantity = 150;
      expect(component.displayQuantity).toBe('99+');
    });
  });

  describe('hasItems', () => {
    it('должен вернуть true если quantity > 0', () => {
      component.quantity = 1;
      expect(component.hasItems).toBe(true);
    });

    it('должен вернуть false если quantity = 0', () => {
      component.quantity = 0;
      expect(component.hasItems).toBe(false);
    });
  });

  describe('onBasketClick()', () => {
    it('должен эмитить click событие', (done) => {
      component.isLoading = false;
      component.click.subscribe(() => {
        expect(true).toBe(true);
        done();
      });

      component.onBasketClick();
    });

    it('должен не эмитить если isLoading=true', () => {
      component.isLoading = true;
      spyOn(component.click, 'emit');

      component.onBasketClick();

      expect(component.click.emit).not.toHaveBeenCalled();
    });
  });

  describe('Snapshot тест', () => {
    it('должен совпадать с snapshot', () => {
      component.quantity = 3;
      component.totalPrice = { value: 1500, currency: 'RUB' };
      fixture.detectChanges();

      expect(fixture.debugElement.nativeElement).toMatchSnapshot();
    });
  });
});
```

**Coverage:**
```
Statements   : 95% (20/21)
Branches     : 90% (9/10)
Functions    : 100% (4/4)
Lines        : 95% (19/20)
```

---

### 6️⃣ STORYBOOK

```typescript
// libs/ui/components/basket-summary/basket-summary.stories.ts

import { Meta, StoryObj } from '@storybook/angular';
import { action } from '@storybook/addon-actions';
import { BasketSummaryComponent } from './basket-summary.component';
import { Currency } from '@shared/types/currency';

const meta: Meta<BasketSummaryComponent> = {
  title: 'UI / Basket Summary',
  component: BasketSummaryComponent,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
  },
};

export default meta;
type Story = StoryObj<BasketSummaryComponent>;

// История: пустая корзина
export const Empty: Story = {
  args: {
    quantity: 0,
    totalPrice: null,
    isLoading: false,
  },
};

// История: несколько товаров
export const WithItems: Story = {
  args: {
    quantity: 3,
    totalPrice: { value: 5500, currency: 'RUB' } as Currency,
    isLoading: false,
  },
};

// История: много товаров (99+)
export const ManyItems: Story = {
  args: {
    quantity: 150,
    totalPrice: { value: 45000, currency: 'RUB' } as Currency,
    isLoading: false,
  },
};

// История: загрузка
export const Loading: Story = {
  args: {
    quantity: 3,
    totalPrice: { value: 5500, currency: 'RUB' } as Currency,
    isLoading: true,
  },
};

// История: интерактивный клик
export const Interactive: Story = {
  args: {
    quantity: 5,
    totalPrice: { value: 8000, currency: 'RUB' } as Currency,
    isLoading: false,
  },
  render: (args) => ({
    props: {
      ...args,
      click: action('basket-click'),
    },
  }),
};
```

**Запуск Storybook:**
```bash
cd libs/ui
npm run storybook
# Open http://localhost:6006
```

---

### 7️⃣ ЭКСПОРТ И РЕГИСТРАЦИЯ

**Файл: `libs/ui/components/index.ts`**

```typescript
// Экспортируем новый компонент
export * from './basket-summary/basket-summary.component';
export * from './basket-summary/index';
```

**Файл: `libs/ui/src/index.ts`** (для симметрии)

```typescript
export * from './lib/components';
export * from './lib/modals';
export * from './lib/drawers';
```

**Использование в модулях:**

```typescript
// modules/basket/basket.module.ts

import { BasketSummaryComponent } from '@ui/components';

@NgModule({
  imports: [BasketSummaryComponent],
})
export class BasketModule {}
```

---

## 📝 Общие правила UI-компонентов

### Styling

| ✅ Делать | ❌ Не делать |
|-----------|-------------|
| Использовать CSS переменные для тем | Hardcoded цвета |
| SCSS переменные для размеров | Магические числа (px) |
| Material Design переменные | Inline styles |
| Responsive через breakpoints | Fixed width/height |
| CSS Grid / Flexbox | Абсолютное позиционирование |

### Компонентизация

| ✅ Делать | ❌ Не делать |
|-----------|-------------|
| Маленькие компоненты (<100 строк) | Монолиты >300 строк |
| ChangeDetectionStrategy.OnPush | Default change detection |
| Standalone компоненты | NgModule для каждого |
| Типизированные Inputs/Outputs | any типы |
| Доступность (aria) с начала | Доступность потом |

### Документация

| ✅ Делать | ❌ Не делать |
|-----------|-------------|
| JSDoc комментарии для публичных методов | Отсутствие документации |
| Storybook истории для всех состояний | Только один вариант |
| README в компоненте | Предположения как это работает |
| Примеры в Storybook | Примеры в коде |
| Типы для всех Input/Output | Неявные типы |

---

## 🔧 Частые задачи

### Добавить новый Input

```typescript
@Input() customData?: CustomType;

// Обновить тест:
it('должен принять customData', () => {
  component.customData = { id: 1, name: 'test' };
  expect(component.customData).toBeDefined();
});

// Обновить Storybook:
export const WithCustomData: Story = {
  args: {
    customData: { id: 1, name: 'test' },
  },
};
```

### Добавить новый Output

```typescript
@Output() customEvent = new EventEmitter<CustomType>();

// Использование в parent:
<gj-component (customEvent)="onCustomEvent($event)"></gj-component>
```

### Использовать Material компонент

```typescript
// Импорт
import { MatDialogModule } from '@angular/material/dialog';

// Standalone
standalone: true,
imports: [MatDialogModule],

// Использование
<button mat-button (click)="openDialog()">Open</button>
```

---

## 📚 Ресурсы

- **Material Design:** https://material.angular.io
- **Angular docs:** https://angular.io/docs
- **Storybook:** https://storybook.js.org/docs/angular
- **Site Architecture:** `.claude/skills/site-stack-anatomy/SKILL.md`
- **Site Conventions:** `.claude/skills/site-angular-conventions/SKILL.md`
- **Nx monorepo:** `.claude/skills/site-nx-commands/SKILL.md`

---

**Версия:** 1.0  
**Дата:** 2026-10-06  
**Платформа:** gj-ng-front (Angular 20)  
**Статус:** Production-ready  
