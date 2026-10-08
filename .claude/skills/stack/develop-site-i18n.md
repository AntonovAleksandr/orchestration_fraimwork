# 🌍 develop-site-i18n.md

**Категория:** [DEVELOPMENT]  
**Платформа:** Site (gj-ng-front)  
**Версия:** 1.0  
**Статус:** Production-ready  
**Автор:** Claude Haiku 4.5 + team

---

## 📋 Описание

**Интернационализация (i18n) и локализация** в Site (Transloco для ru/en/kz, переводы, дата/время/валюта).

Этот скил описывает как **правильно** добавлять переводы, переключать языки и форматировать текст для разных локалей.

**Когда использовать:**
- Добавляешь новый компонент с текстом
- Добавляешь новые ключи переводов
- Работаешь с датой/временем/валютой в разных языках
- Переключаешь язык приложения
- Работаешь с параметризованными строками

## 🔗 Используй паттерн

**ВСЕГДА следовать:** [pattern-development-flow.md](../orchestration/pattern-development-flow.md)

7 обязательных шагов: ПОНИМАНИЕ → ПЛАН → КОД → SECURITY → ТЕСТЫ → КОММИТ → MR

---

## 🎯 Архитектура i18n в Site

### Поддерживаемые языки

```
RU - Русский (основной)
EN - English
KZ - Қазақша

Каждый язык имеет свой набор переводов и локаль
```

### Структура файлов

```
platform/site/gj-ng-front/
├── libs/
│   ├── core/
│   │   ├── i18n/
│   │   │   ├── transloco.config.ts    # Конфиг Transloco
│   │   │   ├── i18n.service.ts         # Сервис смены языка
│   │   │   └── locale.service.ts       # Форматирование по локали
│   │   │
│   │   └── services/
│   │       └── language.service.ts     # История языка (localStorage)
│   │
│   └── shared/
│       ├── pipes/
│       │   ├── translate.pipe.ts       # Transloco pipe
│       │   ├── currency.pipe.ts        # Валюта по локали
│       │   ├── date-locale.pipe.ts     # Дата по локали
│       │   └── number-locale.pipe.ts   # Числа по локали
│       │
│       └── directives/
│           └── translate.directive.ts  # Директива для ключей
│
└── libs/core/i18n/locales/
    ├── ru.json          # Переводы на русском
    ├── en.json          # Переводы на английском
    └── kz.json          # Переводы на казахском
```

### Структура файла перевода

```json
{
  "common": {
    "appName": "Gloria Jeans",
    "buttons": {
      "add": "Добавить",
      "remove": "Удалить",
      "save": "Сохранить",
      "cancel": "Отмена"
    }
  },
  "catalog": {
    "title": "Каталог товаров",
    "filters": {
      "price": "Цена",
      "size": "Размер",
      "color": "Цвет"
    },
    "product": {
      "addToBasket": "Добавить в корзину",
      "inStock": "В наличии",
      "outOfStock": "Нет в наличии"
    }
  },
  "basket": {
    "title": "Корзина",
    "empty": "Корзина пуста",
    "total": "Итого: {{ price }}",
    "checkout": "Перейти к оформлению"
  }
}
```

---

## 🛠️ 7 шагов разработки локализированного компонента

### 1️⃣ ПОНИМАНИЕ

```
✅ ЧТО компонент показывает?
   "Товар в каталоге: название, описание, цена"

✅ КАКИЕ тексты нужно перевести?
   - Название товара (из API, не переводится)
   - "Добавить в корзину" (статический текст)
   - "В наличии" / "Нет в наличии" (статический)
   - Цена (форматирование по локали)
   - Дата обновления (дата по локали)

✅ Динамические переводы (параметры)?
   - "{{ quantity }} товаров в корзине" (параметр: quantity)

✅ Есть ли [BLOCKER]?
   → Нет, могу писать
```

---

### 2️⃣ ПЛАН

**Определить:**

- [ ] Какие ключи переводов нужны?
- [ ] Где они размещаются в JSON? (common, catalog, basket, etc)
- [ ] Есть ли параметры? ({{ param }})
- [ ] Нужно ли форматировать валюту/дату/числа?
- [ ] Где использовать pipe vs directive vs service?

**Пример:**

```
Компонент: ProductCard
Переводы:
✅ common.buttons.add → "Добавить"
✅ catalog.product.inStock → "В наличии"
✅ catalog.product.addToBasket → "Добавить в корзину"

Форматирование:
✅ Цена: currencyPipe (по локали)
✅ Дата обновления: dateLocale pipe

Параметры:
✅ "{{ quantity }} товаров" → количество динамическое
```

---

### 3️⃣ КОД

#### Файл перевода

```json
// libs/core/i18n/locales/ru.json

{
  "common": {
    "appName": "Gloria Jeans",
    "language": "Язык",
    "buttons": {
      "add": "Добавить",
      "remove": "Удалить",
      "save": "Сохранить",
      "cancel": "Отмена",
      "close": "Закрыть",
      "more": "Ещё"
    },
    "status": {
      "loading": "Загружается...",
      "error": "Ошибка",
      "success": "Успешно"
    }
  },
  "catalog": {
    "title": "Каталог товаров",
    "filters": {
      "title": "Фильтры",
      "price": "Цена",
      "size": "Размер",
      "color": "Цвет",
      "brand": "Бренд",
      "reset": "Сбросить фильтры"
    },
    "product": {
      "addToBasket": "Добавить в корзину",
      "inStock": "В наличии",
      "outOfStock": "Нет в наличии",
      "itemsLeft": "Осталось {{ count }} шт.",
      "selected": "Выбран: {{ value }}",
      "colors": "Доступные цвета",
      "sizes": "Доступные размеры"
    }
  },
  "basket": {
    "title": "Корзина",
    "empty": "Корзина пуста",
    "itemsCount": "{{ count }} товаров",
    "subtotal": "Сумма: {{ total }}",
    "shipping": "Доставка: {{ cost }}",
    "total": "Итого: {{ total }}",
    "checkout": "Оформить заказ",
    "continueShopping": "Продолжить покупки"
  },
  "checkout": {
    "title": "Оформление заказа",
    "personalInfo": "Личные данные",
    "deliveryAddress": "Адрес доставки",
    "deliveryMethod": "Способ доставки",
    "paymentMethod": "Способ оплаты",
    "orderSummary": "Итоговая сумма",
    "completeOrder": "Завершить заказ",
    "thankYou": "Спасибо за заказ!"
  }
}
```

```json
// libs/core/i18n/locales/en.json

{
  "common": {
    "appName": "Gloria Jeans",
    "language": "Language",
    "buttons": {
      "add": "Add",
      "remove": "Remove",
      "save": "Save",
      "cancel": "Cancel",
      "close": "Close",
      "more": "More"
    },
    "status": {
      "loading": "Loading...",
      "error": "Error",
      "success": "Success"
    }
  },
  "catalog": {
    "title": "Catalog",
    "filters": {
      "title": "Filters",
      "price": "Price",
      "size": "Size",
      "color": "Color",
      "brand": "Brand",
      "reset": "Reset filters"
    },
    "product": {
      "addToBasket": "Add to Cart",
      "inStock": "In Stock",
      "outOfStock": "Out of Stock",
      "itemsLeft": "{{ count }} left in stock",
      "selected": "Selected: {{ value }}",
      "colors": "Available colors",
      "sizes": "Available sizes"
    }
  },
  "basket": {
    "title": "Cart",
    "empty": "Your cart is empty",
    "itemsCount": "{{ count }} items",
    "subtotal": "Subtotal: {{ total }}",
    "shipping": "Shipping: {{ cost }}",
    "total": "Total: {{ total }}",
    "checkout": "Proceed to Checkout",
    "continueShopping": "Continue Shopping"
  },
  "checkout": {
    "title": "Checkout",
    "personalInfo": "Personal Information",
    "deliveryAddress": "Delivery Address",
    "deliveryMethod": "Delivery Method",
    "paymentMethod": "Payment Method",
    "orderSummary": "Order Summary",
    "completeOrder": "Complete Order",
    "thankYou": "Thank you for your order!"
  }
}
```

```json
// libs/core/i18n/locales/kz.json

{
  "common": {
    "appName": "Gloria Jeans",
    "language": "Тіл",
    "buttons": {
      "add": "Қосу",
      "remove": "Өшіру",
      "save": "Сохранить",
      "cancel": "Орындалмау",
      "close": "Жабу",
      "more": "Тағы да"
    },
    "status": {
      "loading": "Жүктеліп жатыр...",
      "error": "Қате",
      "success": "Сәтті"
    }
  },
  "catalog": {
    "title": "Каталог",
    "filters": {
      "title": "Сүзгілер",
      "price": "Баға",
      "size": "Өлшем",
      "color": "Түсі",
      "brand": "Бренд",
      "reset": "Сүзгілерді сбросить"
    },
    "product": {
      "addToBasket": "Сөрөге қосу",
      "inStock": "Қолда бар",
      "outOfStock": "Қолда жоқ",
      "itemsLeft": "{{ count }} қалды",
      "selected": "Таңдалған: {{ value }}",
      "colors": "Қолда бар түстер",
      "sizes": "Қолда бар өлшемдер"
    }
  },
  "basket": {
    "title": "Сөрө",
    "empty": "Сөрө бос",
    "itemsCount": "{{ count }} тауар",
    "subtotal": "Ішінара сумма: {{ total }}",
    "shipping": "Жеткізу: {{ cost }}",
    "total": "Барлығы: {{ total }}",
    "checkout": "Сатыныңызды растау",
    "continueShopping": "Сатыныңызды құрау"
  },
  "checkout": {
    "title": "Сатыныңызды растау",
    "personalInfo": "Жеке ақпарат",
    "deliveryAddress": "Жеткізу мекенжайы",
    "deliveryMethod": "Жеткізу әдісі",
    "paymentMethod": "Төлем әдісі",
    "orderSummary": "Заказ қорытындысы",
    "completeOrder": "Заказды аяқтау",
    "thankYou": "Заказ үшін рахмет!"
  }
}
```

**Правила:**
- ✅ Группировать ключи по модулям (common, catalog, basket)
- ✅ Использовать camelCase для ключей
- ✅ {{ param }} для динамических значений
- ✅ Одинаковая структура для всех языков

#### i18n Service

```typescript
// libs/core/i18n/i18n.service.ts

import { Injectable } from '@angular/core';
import { TranslocoService } from '@ngnx/transloco';
import { BehaviorSubject, Observable } from 'rxjs';
import { tap } from 'rxjs/operators';

export type Locale = 'ru' | 'en' | 'kz';

@Injectable({
  providedIn: 'root',
})
export class I18nService {
  private availableLocales: Locale[] = ['ru', 'en', 'kz'];
  private currentLocale$ = new BehaviorSubject<Locale>('ru');

  constructor(
    private transloco: TranslocoService,
  ) {}

  // Получить текущий язык
  getCurrentLocale(): Locale {
    return this.transloco.getActiveLang() as Locale;
  }

  // Получить текущий язык как Observable
  getCurrentLocale$(): Observable<Locale> {
    return this.currentLocale$.asObservable();
  }

  // Сменить язык
  setLocale(locale: Locale): Observable<any> {
    return this.transloco.selectTranslation(locale).pipe(
      tap(() => {
        this.transloco.setActiveLang(locale);
        this.currentLocale$.next(locale);
        
        // Сохранить выбор в localStorage
        localStorage.setItem('locale', locale);
        
        // Обновить direction для RTL языков (если будут)
        document.documentElement.lang = locale;
      }),
    );
  }

  // Получить перевод ключа (без подписки)
  translate(key: string, params?: Record<string, any>): string {
    return this.transloco.translate(key, params);
  }

  // Список доступных локалей
  getAvailableLocales(): Locale[] {
    return this.availableLocales;
  }

  // Инициализировать: загрузить сохранённый язык
  initializeLocale(): Observable<any> {
    // Попробовать загрузить из localStorage
    const savedLocale = localStorage.getItem('locale') as Locale | null;
    
    // Или определить из browser locale
    const browserLocale = this.detectBrowserLocale();
    
    // Или использовать ru по умолчанию
    const localeToUse = savedLocale || browserLocale || 'ru';

    return this.setLocale(localeToUse);
  }

  // Определить язык браузера
  private detectBrowserLocale(): Locale | null {
    const browserLocale = navigator.language.split('-')[0].toLowerCase();
    
    if (browserLocale === 'ru') return 'ru';
    if (browserLocale === 'en') return 'en';
    if (browserLocale === 'kk') return 'kz';  // Казахский код 'kk'
    
    return null;
  }
}
```

**Правила:**
- ✅ BehaviorSubject для текущего языка
- ✅ Сохранять выбор в localStorage
- ✅ Определять язык браузера при инициализации
- ✅ Observable для подписки на смену языка

#### Pipe для перевода

```typescript
// libs/shared/pipes/translate.pipe.ts

import { Pipe, PipeTransform } from '@angular/core';
import { TranslocoService } from '@ngnx/transloco';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';

@Pipe({
  name: 'translate',
  standalone: true,
})
export class TranslatePipe implements PipeTransform {
  constructor(private transloco: TranslocoService) {}

  transform(
    key: string,
    params?: Record<string, any>,
  ): Observable<string> {
    // Возвращаем Observable которая переподписывается при смене языка
    return this.transloco.selectTranslate(key, params);
  }
}
```

**Использование:**

```html
<!-- Простой перевод -->
<h1>{{ 'common.appName' | translate | async }}</h1>

<!-- С параметрами -->
<p>{{ 'basket.itemsCount' | translate: { count: 5 } | async }}</p>

<!-- В атрибутах (нужен directive) -->
<button [i18nAttr]="'common.buttons.add'">Добавить</button>
```

#### Locale Service для форматирования

```typescript
// libs/core/i18n/locale.service.ts

import { Injectable } from '@angular/core';
import { I18nService, Locale } from './i18n.service';

@Injectable({
  providedIn: 'root',
})
export class LocaleService {
  private localeMap: Record<Locale, string> = {
    ru: 'ru-RU',
    en: 'en-US',
    kz: 'kk-KZ',
  };

  constructor(private i18n: I18nService) {}

  // Форматировать валюту
  formatCurrency(value: number, currency: string = 'RUB'): string {
    const locale = this.localeMap[this.i18n.getCurrentLocale()];
    
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency,
    }).format(value);
  }

  // Форматировать дату
  formatDate(date: Date, format: 'short' | 'long' = 'short'): string {
    const locale = this.localeMap[this.i18n.getCurrentLocale()];
    
    const options: Intl.DateTimeFormatOptions =
      format === 'short'
        ? { year: 'numeric', month: 'short', day: 'numeric' }
        : { year: 'numeric', month: 'long', day: 'numeric' };

    return new Intl.DateTimeFormat(locale, options).format(date);
  }

  // Форматировать числа
  formatNumber(value: number, decimals: number = 0): string {
    const locale = this.localeMap[this.i18n.getCurrentLocale()];
    
    return new Intl.NumberFormat(locale, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(value);
  }

  // Форматировать время
  formatTime(date: Date): string {
    const locale = this.localeMap[this.i18n.getCurrentLocale()];
    
    return new Intl.DateTimeFormat(locale, {
      hour: '2-digit',
      minute: '2-digit',
    }).format(date);
  }
}
```

#### Компонент с переводами

```typescript
// libs/modules/catalog/components/product-card/product-card.component.ts

import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslatePipe } from '@shared/pipes/translate.pipe';
import { LocaleService } from '@core/i18n/locale.service';
import { Product } from '@core/data-access/models/product';

@Component({
  selector: 'gj-product-card',
  standalone: true,
  imports: [CommonModule, TranslatePipe],
  templateUrl: './product-card.component.html',
  styleUrls: ['./product-card.component.scss'],
})
export class ProductCardComponent {
  @Input() product!: Product;

  constructor(public locale: LocaleService) {}

  // Вычисляемое свойство: в наличии ли?
  get isAvailable(): boolean {
    return this.product.quantity > 0;
  }

  // Отформатированная цена
  get formattedPrice(): string {
    return this.locale.formatCurrency(this.product.price);
  }
}
```

```html
<!-- product-card.component.html -->

<div class="product-card">
  <img [src]="product.image" [alt]="product.name" />

  <h2>{{ product.name }}</h2>
  <p class="price">{{ formattedPrice }}</p>

  <!-- Статус наличия -->
  <span
    class="status"
    [class.in-stock]="isAvailable"
    [class.out-of-stock]="!isAvailable"
  >
    {{
      (isAvailable ? 'catalog.product.inStock' : 'catalog.product.outOfStock')
        | translate
        | async
    }}
  </span>

  <!-- Кол-во осталось -->
  <p *ngIf="product.quantity > 0 && product.quantity < 5" class="items-left">
    {{ 'catalog.product.itemsLeft' | translate: { count: product.quantity } | async }}
  </p>

  <!-- Кнопка добавить в корзину -->
  <button
    [disabled]="!isAvailable"
    (click)="addToBasket()"
  >
    {{ 'catalog.product.addToBasket' | translate | async }}
  </button>
</div>
```

---

### 4️⃣ SECURITY

```
✅ Не хранить sensitive данные в переводах
   ❌ 'user.password': 'секретный ключ API'
   ✅ Только UI текст

✅ Escape HTML в параметрах
   ✅ params: { name: sanitizer.sanitize(name) }

✅ RTL поддержка для будущих языков
   ✅ Подготовить [dir]="'rtl'" атрибуты
```

---

### 5️⃣ ТЕСТЫ

```typescript
// libs/core/i18n/i18n.service.spec.ts

import { TestBed } from '@angular/core/testing';
import { TranslocoService } from '@ngnx/transloco';
import { I18nService, Locale } from './i18n.service';

describe('I18nService', () => {
  let service: I18nService;
  let translocoService: TranslocoService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        I18nService,
        {
          provide: TranslocoService,
          useValue: {
            selectTranslation: jasmine.createSpy().and.returnValue(of({})),
            getActiveLang: jasmine.createSpy().and.returnValue('ru'),
            setActiveLang: jasmine.createSpy(),
            translate: jasmine.createSpy(),
            selectTranslate: jasmine.createSpy(),
          },
        },
      ],
    });

    service = TestBed.inject(I18nService);
    translocoService = TestBed.inject(TranslocoService);
  });

  it('должен получить текущий язык', () => {
    expect(service.getCurrentLocale()).toBe('ru');
  });

  it('должен сменить язык', (done) => {
    service.setLocale('en').subscribe(() => {
      expect(translocoService.setActiveLang).toHaveBeenCalledWith('en');
      done();
    });
  });

  it('должен сохранить язык в localStorage', (done) => {
    spyOn(localStorage, 'setItem');

    service.setLocale('kz').subscribe(() => {
      expect(localStorage.setItem).toHaveBeenCalledWith('locale', 'kz');
      done();
    });
  });
});
```

---

### 6️⃣ КОММИТ

```bash
git add libs/core/i18n/ libs/shared/pipes/

git commit -m "feat(i18n): добавить интернационализацию (ru/en/kz)

- I18nService: смена языка с сохранением
- LocaleService: форматирование валюты/дата/время
- TranslatePipe: перевод в шаблонах
- Файлы переводов: ru.json, en.json, kz.json
- Инициализация: детект browser locale
- Tests: >85% coverage

AC выполнены:
- Смена языка работает ✅
- Переводы загружаются ✅
- Форматирование по локали работает ✅
- localStorage сохраняет выбор ✅

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

---

### 7️⃣ Инициализация в приложении

#### Вариант 1: Провайдер при bootstrap

```typescript
// main.ts

import { bootstrapApplication } from '@angular/platform-browser';
import { AppComponent } from './app.component';
import { provideTransloco } from '@ngnx/transloco';
import { TranslocoHttpLoader } from '@core/i18n/transloco-loader';
import { I18nService } from '@core/i18n/i18n.service';

bootstrapApplication(AppComponent, {
  providers: [
    // Transloco провайдер
    provideTransloco({
      defaultLanguage: 'ru',
      fallbackLanguage: 'ru',
      availableLanguages: ['ru', 'en', 'kz'],
      loader: TranslocoHttpLoader, // Загрузчик JSON файлов
    }),
    // Остальные провайдеры...
  ],
}).then((componentRef) => {
  // Инициализировать i18n после бутстрапа
  const i18nService = componentRef.injector.get(I18nService);
  i18nService.initializeLocale().subscribe(() => {
    console.log('i18n initialized');
  });
});
```

#### Вариант 2: Через провайдеры функцию

```typescript
// main.ts

import { bootstrapApplication } from '@angular/platform-browser';
import { AppComponent } from './app.component';
import { provideTranslocoConfig } from '@core/i18n/provide-transloco-config';

bootstrapApplication(AppComponent, {
  providers: [
    provideTranslocoConfig(),
    // Остальные провайдеры...
  ],
}).then((componentRef) => {
  const i18nService = componentRef.injector.get(I18nService);
  i18nService.initializeLocale().subscribe();
});
```

#### Загрузчик файлов переводов

```typescript
// libs/core/i18n/transloco-loader.ts

import { Injectable } from '@angular/core';
import { Translation, TranslocoLoader } from '@ngnx/transloco';
import { Observable } from 'rxjs';
import { HttpClient } from '@angular/common/http';

@Injectable({ providedIn: 'root' })
export class TranslocoHttpLoader implements TranslocoLoader {
  constructor(private http: HttpClient) {}

  getTranslation(lang: string): Observable<Translation> {
    // Загружать из libs/core/i18n/locales/{lang}.json
    return this.http.get<Translation>(`/assets/i18n/${lang}.json`);
  }
}
```

**Правила:**
- ✅ Регистрировать Transloco при bootstrap
- ✅ Задать defaultLanguage = 'ru'
- ✅ Передать availableLanguages ['ru', 'en', 'kz']
- ✅ Использовать TranslocoHttpLoader для загрузки JSON
- ✅ Инициализировать I18nService в .then() после bootstrap

---

## 💡 Частые паттерны

### Переводы с параметрами

```typescript
// JSON
"basket.itemsCount": "{{ count }} товаров"

// Использование
{{ 'basket.itemsCount' | translate: { count: items.length } | async }}
```

### Условные переводы

```typescript
// JSON
"common.items": "{{ count }} товар{{ plural }}"

// Использование (или использовать pluralization rule)
{{ 'common.items' | translate: { count: n, plural: n > 1 ? 'ов' : '' } | async }}
```

### Переводы в компоненте (не в шаблоне)

```typescript
// ts
get emptyBasketMessage(): string {
  return this.i18n.translate('basket.empty');
}
```

### Switch язык в navbar

```html
<select
  [value]="(i18n.getCurrentLocale$ | async)"
  (change)="i18n.setLocale($event.target.value)"
>
  <option value="ru">Русский</option>
  <option value="en">English</option>
  <option value="kz">Қазақша</option>
</select>
```

---

## 📚 Ресурсы

- **Transloco:** https://ngnx.io/transloco
- **Intl API:** https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl
- **i18n best practices:** https://github.com/i18next/i18next
- **Site i18n Setup:** `.claude/skills/site-stack-anatomy/SKILL.md`

---

**Версия:** 1.0  
**Дата:** 2026-10-06  
**Платформа:** gj-ng-front (Angular 20 + Transloco)  
**Статус:** Production-ready  
