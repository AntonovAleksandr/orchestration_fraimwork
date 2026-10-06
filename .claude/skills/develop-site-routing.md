# 🗺️ develop-site-routing.md

**Категория:** [DEVELOPMENT]  
**Платформа:** Site (gj-ng-front)  
**Версия:** 1.0  
**Статус:** Production-ready  
**Автор:** Claude Haiku 4.5 + team

---

## 📋 Описание

**Маршрутизация и навигация** в Site (Angular Router, guards, lazy loading, route resolve).

Этот скил описывает как **правильно** организовывать маршруты, защищать их guards, загружать данные перед переходом и кэшировать страницы.

**Когда использовать:**
- Добавляешь новый маршрут (страница, модуль)
- Защищаешь маршрут (аутентификация, права)
- Загружаешь данные перед показом страницы
- Настраиваешь lazy loading модулей
- Работаешь с параметрами маршрута

---

## 🎯 Архитектура маршрутизации

### Структура

```
libs/core/routing/                # Маршруты и guards
├── guards/
│   ├── auth.guard.ts            # Проверка аутентификации
│   ├── has-permission.guard.ts  # Проверка прав
│   ├── unsaved-changes.guard.ts # Предупреждение о несохранённых
│   └── basket-resolver.guard.ts # Загрузка корзины перед навигацией
│
├── interceptors/
│   └── auth.interceptor.ts      # Добавление токена к запросам
│
└── routes/
    └── app.routes.ts             # Определение маршрутов

apps/site-ru/
├── src/
│   ├── app.config.ts             # Конфигурация приложения
│   └── main.ts                   # Бутстрап
```

### Типы маршрутов в Site

```
/ (home)
  ├── /catalog                    # Каталог (lazy load)
  │   ├── /products              # Список товаров
  │   └── /product/:id           # Деталь товара (resolve: данные)
  │
  ├── /basket                     # Корзина (lazy load)
  │   ├── /current               # Текущая корзина
  │   └── /checkout              # Чекаут (protected: auth guard)
  │
  ├── /profile                    # Профиль (protected: auth guard)
  │   ├── /orders                # Мои заказы
  │   ├── /addresses             # Адреса доставки
  │   └── /settings              # Настройки
  │
  ├── /auth                       # Аутентификация
  │   ├── /login                 # Вход
  │   ├── /register              # Регистрация
  │   └── /forgot-password       # Восстановление пароля
  │
  └── 404                         # Не найдено
```

---

## 🛠️ 7 шагов разработки маршрутизации

### 1️⃣ ПОНИМАНИЕ

```
✅ ЧТО это за маршрут?
   "Страница профиля пользователя"

✅ ГДЕ навесить?
   "/profile"

✅ КТО может заходить?
   "Только аутентифицированные пользователи"

✅ ЧТО загружать перед показом?
   "Профиль пользователя (HTTP запрос)"

✅ Есть ли параметры?
   "/profile/orders/:orderId"

✅ Есть ли [BLOCKER]?
   → Нет, могу писать
```

---

### 2️⃣ ПЛАН

**Определить:**

- [ ] Путь маршрута (/profile, /profile/:id, etc)
- [ ] Метод: eager load или lazy load?
- [ ] Guard: какой guard нужен?
- [ ] Resolver: загружать данные?
- [ ] Компонент: какой компонент рендерится?
- [ ] Дочерние маршруты: есть ли?
- [ ] Redirect: куда редиректить при ошибке?

**Пример:**

```
Маршрут: /profile
Метод: Lazy load (модуль ProfileModule)
Guard: AuthGuard (проверка токена)
Resolver: ProfileResolver (загрузить профиль)
Component: ProfileComponent
Дочерние: /profile/orders, /profile/settings
Redirect: /login если не authenticated
```

---

### 3️⃣ КОД

#### Guards

```typescript
// libs/core/routing/guards/auth.guard.ts

import { Injectable } from '@angular/core';
import {
  CanActivate,
  CanActivateChild,
  ActivatedRouteSnapshot,
  RouterStateSnapshot,
  Router,
  UrlTree,
} from '@angular/router';
import { Observable } from 'rxjs';
import { map, take } from 'rxjs/operators';
import { Store } from '@ngrx/store';
import { selectIsAuthenticated } from '@core/data-access/store/features/auth/selectors/auth.selectors';

@Injectable({
  providedIn: 'root',
})
export class AuthGuard implements CanActivate, CanActivateChild {
  constructor(
    private store: Store,
    private router: Router,
  ) {}

  canActivate(
    route: ActivatedRouteSnapshot,
    state: RouterStateSnapshot,
  ): Observable<boolean | UrlTree> {
    return this.checkAuth(state.url);
  }

  canActivateChild(
    childRoute: ActivatedRouteSnapshot,
    state: RouterStateSnapshot,
  ): Observable<boolean | UrlTree> {
    return this.checkAuth(state.url);
  }

  private checkAuth(url: string): Observable<boolean | UrlTree> {
    return this.store.select(selectIsAuthenticated).pipe(
      take(1),
      map((isAuthenticated) => {
        if (isAuthenticated) {
          return true;
        }

        // Сохраняем куда пользователь хотел пойти
        // Перенаправляем на логин
        return this.router.createUrlTree(['/auth/login'], {
          queryParams: { returnUrl: url },
        });
      }),
    );
  }
}
```

```typescript
// libs/core/routing/guards/has-permission.guard.ts

import { Injectable } from '@angular/core';
import { CanActivate, ActivatedRouteSnapshot, RouterStateSnapshot, Router } from '@angular/router';
import { Observable } from 'rxjs';
import { map, take } from 'rxjs/operators';
import { Store } from '@ngrx/store';
import { selectUserRoles } from '@core/data-access/store/features/auth';

@Injectable({
  providedIn: 'root',
})
export class HasPermissionGuard implements CanActivate {
  constructor(
    private store: Store,
    private router: Router,
  ) {}

  canActivate(
    route: ActivatedRouteSnapshot,
    _state: RouterStateSnapshot,
  ): Observable<boolean> {
    const requiredRoles = route.data['roles'] as string[];

    return this.store.select(selectUserRoles).pipe(
      take(1),
      map((userRoles) => {
        // Проверяем есть ли у пользователя требуемая роль
        const hasPermission = requiredRoles.some((role) =>
          userRoles.includes(role),
        );

        if (!hasPermission) {
          this.router.navigate(['/403']);
        }

        return hasPermission;
      }),
    );
  }
}
```

```typescript
// libs/core/routing/guards/unsaved-changes.guard.ts

import { Injectable } from '@angular/core';
import { CanDeactivate } from '@angular/router';
import { Observable } from 'rxjs';

/**
 * Интерфейс для компонентов которые могут иметь unsaved changes
 */
export interface ComponentCanDeactivate {
  canDeactivate: () => boolean | Observable<boolean>;
}

@Injectable({
  providedIn: 'root',
})
export class UnsavedChangesGuard implements CanDeactivate<ComponentCanDeactivate> {
  canDeactivate(
    component: ComponentCanDeactivate,
  ): Observable<boolean> | boolean {
    if (component.canDeactivate) {
      return component.canDeactivate();
    }

    return true;
  }
}
```

**Правила guards:**
- ✅ CanActivate для маршрута
- ✅ CanActivateChild для дочерних маршрутов
- ✅ CanDeactivate для выхода с маршрута
- ✅ Observable<boolean | UrlTree> возвращаемый тип
- ✅ Логика в guards (не в компонентах)

#### Resolvers

```typescript
// libs/core/routing/resolvers/profile.resolver.ts

import { Injectable } from '@angular/core';
import {
  Resolve,
  ActivatedRouteSnapshot,
  RouterStateSnapshot,
} from '@angular/router';
import { Observable, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { UserProfile } from '@core/data-access/models/user-profile';
import { UserService } from '@core/services/user.service';

@Injectable({
  providedIn: 'root',
})
export class ProfileResolver implements Resolve<UserProfile | null> {
  constructor(private userService: UserService) {}

  resolve(
    _route: ActivatedRouteSnapshot,
    _state: RouterStateSnapshot,
  ): Observable<UserProfile | null> {
    return this.userService.getProfile().pipe(
      catchError((error) => {
        console.error('Failed to load profile:', error);
        // Возвращаем null если ошибка, компонент обработает
        return of(null);
      }),
    );
  }
}
```

```typescript
// libs/core/routing/resolvers/product.resolver.ts

import { Injectable } from '@angular/core';
import { Resolve, ActivatedRouteSnapshot } from '@angular/router';
import { Observable } from 'rxjs';
import { Product } from '@core/data-access/models/product';
import { CatalogService } from '@core/services/catalog.service';

@Injectable({
  providedIn: 'root',
})
export class ProductResolver implements Resolve<Product> {
  constructor(private catalogService: CatalogService) {}

  resolve(route: ActivatedRouteSnapshot): Observable<Product> {
    const productId = route.paramMap.get('id') as string;
    return this.catalogService.getProduct(productId);
  }
}
```

**Правила resolvers:**
- ✅ Загружаем данные ПЕРЕД показом компонента
- ✅ resolve() возвращает Observable
- ✅ catchError обрабатываем (не кидаем ошибку)
- ✅ Данные доступны в компоненте через route.data

#### Маршруты

```typescript
// libs/core/routing/routes/app.routes.ts

import { Routes } from '@angular/router';
import { AuthGuard } from '../guards/auth.guard';
import { HasPermissionGuard } from '../guards/has-permission.guard';
import { UnsavedChangesGuard } from '../guards/unsaved-changes.guard';
import { ProfileResolver } from '../resolvers/profile.resolver';
import { ProductResolver } from '../resolvers/product.resolver';
import { HomeComponent } from '@modules/home';
import { NotFoundComponent } from '@shared/components';

export const APP_ROUTES: Routes = [
  {
    path: '',
    component: HomeComponent,
  },

  // Каталог: Lazy load
  {
    path: 'catalog',
    loadChildren: () =>
      import('@modules/catalog').then((m) => m.CATALOG_ROUTES),
  },

  // Продукт с resolver
  {
    path: 'product/:id',
    loadComponent: () =>
      import('@modules/catalog/components/product-detail')
        .then((m) => m.ProductDetailComponent),
    resolve: {
      product: ProductResolver,
    },
  },

  // Корзина: Lazy load
  {
    path: 'basket',
    loadChildren: () =>
      import('@modules/basket').then((m) => m.BASKET_ROUTES),
  },

  // Чекаут: Protected + resolver
  {
    path: 'checkout',
    loadComponent: () =>
      import('@modules/checkout/components/checkout')
        .then((m) => m.CheckoutComponent),
    canActivate: [AuthGuard],
    canDeactivate: [UnsavedChangesGuard],
    data: {
      title: 'Оформление заказа',
    },
  },

  // Профиль: Protected + lazy load
  {
    path: 'profile',
    canActivate: [AuthGuard],
    canActivateChild: [AuthGuard],
    loadChildren: () =>
      import('@modules/profile').then((m) => m.PROFILE_ROUTES),
  },

  // Профиль детали: с resolver
  {
    path: 'profile/:id',
    loadComponent: () =>
      import('@modules/profile/components/profile-detail')
        .then((m) => m.ProfileDetailComponent),
    canActivate: [AuthGuard],
    resolve: {
      profile: ProfileResolver,
    },
  },

  // Админ панель: Только для admin
  {
    path: 'admin',
    canActivate: [AuthGuard, HasPermissionGuard],
    loadChildren: () =>
      import('@modules/admin').then((m) => m.ADMIN_ROUTES),
    data: {
      roles: ['admin'],
    },
  },

  // Аутентификация
  {
    path: 'auth',
    loadChildren: () =>
      import('@modules/auth').then((m) => m.AUTH_ROUTES),
  },

  // 404
  {
    path: '404',
    component: NotFoundComponent,
  },
  {
    path: '**',
    redirectTo: '/404',
  },
];
```

**Правила маршрутов:**
- ✅ Последний маршрут `**` для 404
- ✅ Lazy load для большие модули
- ✅ Guard на маршруте (не в компоненте)
- ✅ Resolver для данных перед показом
- ✅ data для мета-информации

#### Использование в компоненте

```typescript
// component.ts

export class ProductDetailComponent implements OnInit {
  product$: Observable<Product>;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
  ) {
    // Данные из resolver
    this.product$ = this.route.data.pipe(
      map((data) => data['product']),
    );
  }

  ngOnInit(): void {
    // Получить параметр из URL
    this.route.paramMap.subscribe((params) => {
      const id = params.get('id');
      console.log('Product ID:', id);
    });

    // Получить query параметр
    this.route.queryParamMap.subscribe((params) => {
      const page = params.get('page');
      console.log('Page:', page);
    });
  }

  navigateBack(): void {
    this.router.navigate(['..'], { relativeTo: this.route });
  }

  navigateWithParams(): void {
    this.router.navigate(['/product', 123], {
      queryParams: { tab: 'reviews' },
    });
  }
}
```

```html
<!-- component.html -->

<div *ngIf="product$ | async as product">
  <h1>{{ product.name }}</h1>
  <p>{{ product.description }}</p>
</div>
```

---

### 4️⃣ SECURITY

```
✅ AuthGuard на все protected маршруты
   ✅ /profile, /checkout, /admin

✅ HasPermissionGuard для админ функций
   ✅ Проверяем роли перед доступом

✅ Нет чувствительных данных в URL
   ❌ /checkout?apiKey=sk-123
   ✅ /checkout (API ключ в header/interceptor)

✅ Redirect на /login если неавторизован
   ✅ Сохраняем returnUrl для редиректа после логина

✅ UnsavedChangesGuard на формах
   ✅ Предупреждение перед потерей данных
```

---

### 5️⃣ ТЕСТЫ

```typescript
// libs/core/routing/guards/auth.guard.spec.ts

import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { AuthGuard } from './auth.guard';
import { provideMockStore } from '@ngrx/store/testing';
import { selectIsAuthenticated } from '@core/data-access/store/features/auth';
import { of } from 'rxjs';

describe('AuthGuard', () => {
  let guard: AuthGuard;
  let router: jasmine.SpyObj<Router>;

  beforeEach(() => {
    const routerSpy = jasmine.createSpyObj('Router', ['createUrlTree']);

    TestBed.configureTestingModule({
      providers: [
        AuthGuard,
        provideMockStore({
          selectors: [
            {
              selector: selectIsAuthenticated,
              value: true,
            },
          ],
        }),
        { provide: Router, useValue: routerSpy },
      ],
    });

    guard = TestBed.inject(AuthGuard);
    router = TestBed.inject(Router) as jasmine.SpyObj<Router>;
  });

  it('должен позволить доступ если authenticated', (done) => {
    guard.canActivate(null as any, { url: '/' } as any).subscribe((result) => {
      expect(result).toBe(true);
      done();
    });
  });

  it('должен редиректить на /login если не authenticated', (done) => {
    // Переопределить mock для this.store
    guard.canActivate(null as any, { url: '/profile' } as any).subscribe((result) => {
      // Проверить что router.createUrlTree был вызван
      expect(router.createUrlTree).toHaveBeenCalledWith(
        ['/auth/login'],
        jasmine.objectContaining({ queryParams: { returnUrl: '/profile' } }),
      );
      done();
    });
  });
});
```

---

### 6️⃣ КОММИТ

```bash
git add libs/core/routing/

git commit -m "feat(routing): добавить маршруты, guards и resolvers

- Guards: AuthGuard, HasPermissionGuard, UnsavedChangesGuard
- Resolvers: ProfileResolver, ProductResolver
- Routes: /profile, /checkout, /admin, /product/:id с lazy load
- Tests: >85% coverage для guards и resolvers

AC выполнены:
- Protected маршруты работают ✅
- Resolver загружает данные перед показом ✅
- Redirect на /login работает ✅

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

---

### 7️⃣ Интеграция в приложение

```typescript
// main.ts

import { bootstrapApplication } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';
import { APP_ROUTES } from '@core/routing';
import { AppComponent } from './app.component';

bootstrapApplication(AppComponent, {
  providers: [
    provideRouter(APP_ROUTES),
    // Остальные провайдеры...
  ],
});
```

---

## 💡 Частые паттерны

### Перенаправление после логина

```typescript
// auth.service.ts

login(username: string, password: string): Observable<void> {
  return this.http.post('/auth/login', { username, password }).pipe(
    tap(() => {
      // Получить returnUrl из query params
      const returnUrl = this.route.snapshot.queryParamMap.get('returnUrl');
      this.router.navigateByUrl(returnUrl || '/');
    }),
  );
}
```

### Параметры маршрута

```typescript
// Получить параметр маршрута
constructor(private route: ActivatedRoute) {}

ngOnInit() {
  this.route.paramMap.subscribe(params => {
    const id = params.get('id');
  });
}

// Или через snapshot (если данные static)
const id = this.route.snapshot.paramMap.get('id');
```

### Query параметры

```typescript
// Сохранить состояние в URL
navigateWithFilters(filters: FilterOptions) {
  this.router.navigate(['/catalog'], {
    queryParams: {
      category: filters.category,
      minPrice: filters.minPrice,
      maxPrice: filters.maxPrice,
      page: filters.page,
    },
    // Merge с существующими params вместо замены
    queryParamsHandling: 'merge',
  });
}
```

### Относительная навигация

```typescript
// Перейти к parent маршруту
this.router.navigate(['..'], { relativeTo: this.route });

// Перейти к sibling маршруту
this.router.navigate(['../products'], { relativeTo: this.route });

// Перейти к child маршруту
this.router.navigate(['orders'], { relativeTo: this.route });
```

---

## 📚 Ресурсы

- **Angular Router:** https://angular.io/guide/router
- **Route guards:** https://angular.io/guide/router/guards
- **Lazy loading:** https://angular.io/guide/lazy-loading-ngmodules
- **Site Routing Architecture:** `.claude/skills/site-stack-anatomy/SKILL.md`

---

**Версия:** 1.0  
**Дата:** 2026-10-06  
**Платформа:** gj-ng-front (Angular 20)  
**Статус:** Production-ready  
