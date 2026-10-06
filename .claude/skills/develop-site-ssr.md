# 🖥️ develop-site-ssr.md

**Категория:** [DEVELOPMENT]  
**Платформа:** Site (gj-ng-front)  
**Версия:** 1.0  
**Статус:** Production-ready  
**Автор:** Claude Haiku 4.5 + team

---

## 📋 Описание

**Server-Side Rendering (SSR) и Universal** в Site (NestJS + Angular Universal, platform-specific, transfer state).

Этот скил описывает как **правильно** писать код который работает и на сервере и в браузере, передавать state, и избегать серверных ошибок.

**Когда использовать:**
- Разработка компонентов которые рендерятся на сервере
- Работа с localStorage/sessionStorage (не существует на сервере)
- Передача данных между сервером и браузером
- Оптимизация SEO (мета-теги, Open Graph)
- Обработка платформ (browser vs server)

---

## 🎯 Архитектура SSR в Site

### Server vs Browser differences

```typescript
// ❌ На сервере не работает:
- window, document, navigator (undefined)
- localStorage, sessionStorage (не существует)
- WebSocket, EventSource
- navigator.mediaDevices, DeviceOrientationEvent
- requestAnimationFrame
- Перенаправление через window.location

// ✅ Используем вместо этого:
- DOCUMENT token вместо document
- WINDOW token вместо window
- TransferState для передачи данных
- Router для перенаправления
- platform-specific checks
```

### Структура Site

```
platform/site/gj-ng-front/
├── libs/
│   ├── core/
│   │   ├── server/                # Код специфичный для сервера
│   │   │   ├── ssr.config.ts      # NestJS конфигурация
│   │   │   └── server.module.ts   # Серверный модуль
│   │   │
│   │   └── services/
│   │       ├── platform.service.ts # Проверка платформы
│   │       └── transfer-state.service.ts # Передача state
│   │
│   └── shared/
│       ├── guards/
│       │   └── browser-only.guard.ts  # Только в браузере
│       │
│       └── utils/
│           └── platform.utils.ts # Утилиты для платформы
│
└── apps/site-ru/
    ├── src/
    │   ├── main.ts              # Browser bootstrap
    │   ├── main.server.ts       # Server bootstrap
    │   ├── app.component.ts     # Root компонент
    │   └── styles.scss          # Глобальные стили
    │
    └── server.ts               # NestJS сервер
```

---

## 🛠️ 7 шагов разработки SSR-компонента

### 1️⃣ ПОНИМАНИЕ

```
✅ ЧТО компонент делает?
   "Показывает текущего пользователя из localStorage"

✅ Работает ли на сервере?
   → НЕТ (localStorage не существует на сервере)

✅ Нужна ли передача state?
   → ДА (сервер должен знать текущего пользователя)

✅ Как передавать?
   → TransferState API (state передаётся в HTML)

✅ Есть ли [BLOCKER]?
   → Нет, могу писать
```

---

### 2️⃣ ПЛАН

**Определить:**

- [ ] Работает ли на сервере? Если нет, обернуть в platform check
- [ ] Нужна ли передача state? Если да, использовать TransferState
- [ ] Есть ли HTTP запросы? Если да, они выполнятся на сервере
- [ ] Нужны ли guard? Если компонент зависит от браузера
- [ ] SSR meta tags? Если важен SEO

**Пример:**

```
Компонент: UserHeaderComponent
Зависимости: localStorage (браузер), HTTP (сервер+браузер)
План:
1. Получить user из store (HTTP на сервере)
2. TransferState: передать user с сервера
3. Browser-only: текущий user из localStorage
4. Meta tags: для SEO (если нужно)
```

---

### 3️⃣ КОД

#### Platform Service (проверка платформы)

```typescript
// libs/core/services/platform.service.ts

import { Injectable } from '@angular/core';
import { isPlatformBrowser, isPlatformServer } from '@angular/common';
import { PLATFORM_ID } from '@angular/core';
import { Inject } from '@angular/core';

@Injectable({
  providedIn: 'root',
})
export class PlatformService {
  private isBrowser: boolean;
  private isServer: boolean;

  constructor(@Inject(PLATFORM_ID) private platformId: Object) {
    this.isBrowser = isPlatformBrowser(this.platformId);
    this.isServer = isPlatformServer(this.platformId);
  }

  get browser(): boolean {
    return this.isBrowser;
  }

  get server(): boolean {
    return this.isServer;
  }
}
```

**Правила:**
- ✅ Инжектируем PLATFORM_ID
- ✅ Используем isPlatformBrowser / isPlatformServer
- ✅ Проверяем перед использованием window/document

#### Transfer State Service

```typescript
// libs/core/services/transfer-state.service.ts

import { Injectable } from '@angular/core';
import { makeStateKey, TransferState } from '@angular/platform-browser';
import { Observable, of } from 'rxjs';
import { tap } from 'rxjs/operators';
import { PlatformService } from './platform.service';

@Injectable({
  providedIn: 'root',
})
export class TransferStateService {
  constructor(
    private transferState: TransferState,
    private platformService: PlatformService,
  ) {}

  /**
   * Получить значение из transferred state
   * Если в браузере и найдено, вернуть из state
   * Если на сервере, вернуть null (будет set позже)
   */
  get<T>(key: string): T | null {
    const stateKey = makeStateKey<T>(key);

    // На браузере: получить из перенесённого state
    if (this.platformService.browser) {
      const value = this.transferState.get(stateKey, null);
      // Удалить из state чтобы не сохранялся в HTML
      this.transferState.remove(stateKey);
      return value;
    }

    return null;
  }

  /**
   * Установить значение в transferred state
   * На браузере: установит state
   * На сервере: заполнит HTML для браузера
   */
  set<T>(key: string, value: T): void {
    const stateKey = makeStateKey<T>(key);
    this.transferState.set(stateKey, value);
  }

  /**
   * Логика: попробовать получить из state, если нет - выполнить HTTP и передать
   */
  withTransfer<T>(
    key: string,
    httpCall$: Observable<T>,
  ): Observable<T> {
    const cached = this.get<T>(key);

    if (cached) {
      return of(cached);
    }

    // На сервере: выполнить HTTP и передать state
    return httpCall$.pipe(
      tap((value) => {
        if (this.platformService.server) {
          this.set(key, value);
        }
      }),
    );
  }
}
```

**Правила:**
- ✅ makeStateKey для уникального ключа
- ✅ На браузере: получить и удалить
- ✅ На сервере: установить для передачи
- ✅ withTransfer для удобства

#### SSR-компонент

```typescript
// libs/modules/profile/components/user-header/user-header.component.ts

import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Observable } from 'rxjs';
import { User } from '@core/data-access/models/user';
import { UserService } from '@core/services/user.service';
import { TransferStateService } from '@core/services/transfer-state.service';
import { PlatformService } from '@core/services/platform.service';

@Component({
  selector: 'gj-user-header',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './user-header.component.html',
  styleUrls: ['./user-header.component.scss'],
})
export class UserHeaderComponent implements OnInit {
  user$: Observable<User | null>;
  isLoading = false;

  constructor(
    private userService: UserService,
    private transferState: TransferStateService,
    private platformService: PlatformService,
  ) {
    // На браузере: попробовать получить из localStorage
    if (this.platformService.browser) {
      const cachedUser = localStorage.getItem('currentUser');
      if (cachedUser) {
        this.user$ = of(JSON.parse(cachedUser));
        return;
      }
    }

    // На сервере и браузере: использовать HTTP с TransferState
    this.user$ = this.transferState.withTransfer(
      'user-profile',
      this.userService.getCurrentUser(),
    );
  }

  ngOnInit(): void {
    this.user$.subscribe((user) => {
      // На браузере: кэшировать в localStorage
      if (user && this.platformService.browser) {
        localStorage.setItem('currentUser', JSON.stringify(user));
      }
    });
  }

  logout(): void {
    // Проверяем что это браузер перед использованием localStorage
    if (this.platformService.browser) {
      localStorage.removeItem('currentUser');
    }

    this.userService.logout().subscribe(() => {
      // Перенаправить через router (работает везде)
      // this.router.navigate(['/auth/login']);
    });
  }
}
```

**Правила:**
- ✅ Проверяем platformService перед window/document/localStorage
- ✅ TransferState для данных между сервером и браузером
- ✅ Не используем localStorage без проверки
- ✅ HTTP запросы сами работают везде

#### Browser-Only Guard

```typescript
// libs/shared/guards/browser-only.guard.ts

import { Injectable } from '@angular/core';
import { CanActivate, Router } from '@angular/router';
import { PlatformService } from '@core/services/platform.service';

@Injectable({
  providedIn: 'root',
})
export class BrowserOnlyGuard implements CanActivate {
  constructor(
    private platformService: PlatformService,
    private router: Router,
  ) {}

  canActivate(): boolean {
    // На сервере: предотвратить выполнение компонента
    if (this.platformService.server) {
      this.router.navigate(['/']);
      return false;
    }

    return true;
  }
}
```

**Применение:**

```typescript
// В маршруте
{
  path: 'webcam',
  loadComponent: () => import('@modules/webcam').then(m => m.WebcamComponent),
  canActivate: [BrowserOnlyGuard],
}
```

#### Meta Tags для SEO

```typescript
// libs/core/services/meta.service.ts

import { Injectable } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';

@Injectable({
  providedIn: 'root',
})
export class MetaService {
  constructor(
    private title: Title,
    private meta: Meta,
  ) {}

  setPageMeta(options: {
    title: string;
    description: string;
    keywords?: string;
    image?: string;
    url?: string;
  }): void {
    // Title для браузера и поисковиков
    this.title.setTitle(options.title);

    // Meta теги
    this.meta.updateTag({
      name: 'description',
      content: options.description,
    });

    if (options.keywords) {
      this.meta.updateTag({
        name: 'keywords',
        content: options.keywords,
      });
    }

    // Open Graph для социальных сетей
    this.meta.updateTag({
      property: 'og:title',
      content: options.title,
    });

    this.meta.updateTag({
      property: 'og:description',
      content: options.description,
    });

    if (options.image) {
      this.meta.updateTag({
        property: 'og:image',
        content: options.image,
      });
    }

    if (options.url) {
      this.meta.updateTag({
        property: 'og:url',
        content: options.url,
      });
    }
  }

  setProductMeta(product: { name: string; description: string; image: string; url: string }): void {
    this.setPageMeta({
      title: product.name,
      description: product.description,
      image: product.image,
      url: product.url,
    });
  }
}
```

**Использование в компоненте:**

```typescript
export class ProductDetailComponent implements OnInit {
  product$: Observable<Product>;

  constructor(private metaService: MetaService) {}

  ngOnInit(): void {
    this.product$.subscribe((product) => {
      this.metaService.setProductMeta({
        name: product.name,
        description: product.description,
        image: product.image?.url || '',
        url: `https://gj.ru/product/${product.id}`,
      });
    });
  }
}
```

---

### 4️⃣ SECURITY

```
✅ Нет sensitive данных в TransferState
   ❌ transfer state: { userPassword, apiKey }
   ✅ transfer state: { userId, userName }

✅ Валидация данных при transfer
   ✅ response.data instanceof Product (typecheck)
   ❌ Просто присвоить без проверки

✅ Secure HttpOnly cookies для auth
   ✅ Браузер не может читать (защита от XSS)
   ❌ Хранить токен в localStorage

✅ CSP meta tags для XSS защиты
   <meta http-equiv="Content-Security-Policy" ...>
```

---

### 5️⃣ ТЕСТЫ

```typescript
// libs/core/services/transfer-state.service.spec.ts

import { TestBed } from '@angular/core/testing';
import { TransferState, makeStateKey } from '@angular/platform-browser';
import { TransferStateService } from './transfer-state.service';
import { PlatformService } from './platform.service';

describe('TransferStateService', () => {
  let service: TransferStateService;
  let transferState: TransferState;
  let platformService: PlatformService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        TransferStateService,
        {
          provide: PlatformService,
          useValue: {
            browser: true,
            server: false,
          },
        },
      ],
    });

    service = TestBed.inject(TransferStateService);
    transferState = TestBed.inject(TransferState);
    platformService = TestBed.inject(PlatformService);
  });

  it('должен сохранить и вернуть значение', () => {
    const key = 'test-key';
    const value = { id: 1, name: 'test' };

    service.set(key, value);
    const result = service.get(key);

    expect(result).toEqual(value);
  });

  it('должен вернуть null если значение не установлено', () => {
    const result = service.get('non-existent-key');

    expect(result).toBeNull();
  });

  describe('withTransfer', () => {
    it('должен вернуть cached значение', (done) => {
      const key = 'cached-key';
      const cachedValue = { id: 1 };

      service.set(key, cachedValue);

      service.withTransfer(key, of({ id: 2 })).subscribe((result) => {
        expect(result).toEqual(cachedValue);
        done();
      });
    });

    it('должен выполнить HTTP если нет cache', (done) => {
      const httpValue = { id: 2 };

      service.withTransfer('new-key', of(httpValue)).subscribe((result) => {
        expect(result).toEqual(httpValue);
        done();
      });
    });
  });
});
```

---

### 6️⃣ КОММИТ

```bash
git add libs/core/services/ libs/shared/guards/

git commit -m "feat(ssr): добавить platform-specific services и transfer state

- PlatformService: проверка браузер/сервер
- TransferStateService: передача данных браузер↔сервер
- BrowserOnlyGuard: защита компонентов специфичных для браузера
- MetaService: SEO meta tags и Open Graph
- Tests: >85% coverage

AC выполнены:
- Компоненты работают и на браузере и на сервере ✅
- localStorage безопасно используется (с проверкой) ✅
- State передаётся без перепечатки ✅
- SEO мета-теги обновляются ✅

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

---

### 7️⃣ NestJS SSR конфигурация

```typescript
// apps/site-ru/server.ts

import { ngExpressEngine } from '@nguniversal/express-engine';
import * as express from 'express';
import { join } from 'path';
import { AppServerModule } from './src/main.server';
import { APP_BASE_HREF } from '@angular/common';
import { existsSync } from 'fs';

const PORT = process.env['PORT'] || 4000;
const DIST_FOLDER = join(process.cwd(), 'dist/apps/site-ru/browser');
const SERVER_FOLDER = join(process.cwd(), 'dist/apps/site-ru/server');

// Индекс файл для SSR
const index = require(join(SERVER_FOLDER, 'index.js')).index;

const app = express();

// Express конфигурация
app.engine(
  'html',
  ngExpressEngine({
    bootstrap: AppServerModule,
  }),
);

app.set('view engine', 'html');
app.set('views', DIST_FOLDER);

// Серверные маршруты
app.get('/api/*', (req, res) => {
  res.status(404).send('data only');
});

// Статические файлы
app.get('*.*', express.static(DIST_FOLDER, { maxAge: '1y' }));

// Все остальные маршруты: SSR
app.get('*', (req, res) => {
  res.render('index', {
    req,
    providers: [{ provide: APP_BASE_HREF, useValue: req.baseUrl }],
  });
});

// Запустить сервер
app.listen(PORT, () => {
  console.log(`Node Express server listening on http://localhost:${PORT}`);
});
```

---

## 💡 Частые ошибки SSR

### Ошибка 1: Использование window без проверки

```typescript
// ❌ НЕПРАВИЛЬНО: падает на сервере
export class MyComponent {
  constructor() {
    console.log(window.location.href);  // undefined на сервере
  }
}

// ✅ ПРАВИЛЬНО: с проверкой
export class MyComponent {
  constructor(private platformService: PlatformService) {}

  ngOnInit() {
    if (this.platformService.browser) {
      console.log(window.location.href);
    }
  }
}
```

### Ошибка 2: localStorage без проверки

```typescript
// ❌ НЕПРАВИЛЬНО
localStorage.setItem('key', 'value');  // undefined на сервере

// ✅ ПРАВИЛЬНО
if (this.platformService.browser) {
  localStorage.setItem('key', 'value');
}
```

### Ошибка 3: Забыли передать state

```typescript
// ❌ На браузере перезагружает всё заново (медленно)
this.userService.getUser().subscribe(...)  // Выполнится ещё раз

// ✅ Передаём state
this.transferState.withTransfer('user', this.userService.getUser()).subscribe(...)
```

---

## 📚 Ресурсы

- **Angular Universal:** https://angular.io/guide/universal
- **Platform detection:** https://angular.io/api/common/isPlatformBrowser
- **Transfer State:** https://angular.io/api/platform-browser/TransferState
- **Site SSR Setup:** `.claude/skills/site-stack-anatomy/SKILL.md`

---

**Версия:** 1.0  
**Дата:** 2026-10-06  
**Платформа:** gj-ng-front (Angular Universal + NestJS)  
**Статус:** Production-ready  
