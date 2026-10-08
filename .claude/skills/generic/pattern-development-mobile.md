---
name: pattern-development-mobile
version: 1.0.0
layer: generic
platform: Mobile
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---

# 📱 pattern-development-mobile.md

**Категория:** [PATTERNS]  
**Платформа:** Mobile (gj-app — React Native 0.74.1)  
**Версия:** 1.0  
**Статус:** Production-ready  
**Автор:** Claude Haiku 4.5 + mobile team

---

## 📋 Описание

**Явный паттерн мобильной разработки** — как разработчик пишет React Native код по постановке.

Разработчик **ДОЛЖЕН ВСЕГДА** следовать этим 7 шагам. Нет импровизации.

**Специфика Mobile:**
- Две платформы одновременно (iOS + Android)
- Нативный код (Swift, Kotlin) когда нужно
- Различия в поведении между платформами
- Ограничения памяти и производительности
- TestID для Detox E2E тестов
- Build flavors: development, staging, production

---

## 🎯 7 обязательных шагов

### 1️⃣ ПОНИМАНИЕ (Understanding)

**Что делать:**
- Прочитать ПОЛНУЮ постановку (ЧТО, ГДЕ, КАК, РИСКИ)
- Понять требование
- Понять ограничения (iOS vs Android)
- Понять верификацию
- Понять риски

**Процесс:**
```
ЧТО? "Добавить поле "Комментарий к заказу" в чекауте"
      ✅ Понял: новый TextInput компонент

ГДЕ? "В packages/gj/src/screens/CheckoutScreen"
     "В packages/ui-kit/components/FormInput для переиспользования"
      ✅ Понял: 2 места

ПЛАТФОРМЫ? "iOS — native keyboard, Android — showSoftInput"
           "Разное поведение для длинного текста"
            ✅ Понял: нужны platform checks

КАК? "Jest unit тесты, Detox E2E в CI"
      ✅ Понял: как проверяем

РИСКИ? "[BLOCKER] нет, [NB] большое поле может съесть место"
       ✅ Понял: могу начинать писать

✅ ПОНИМАНИЕ ЗАВЕРШЕНО → переход на шаг 2
```

**Если не понял:**
- Спросить аналитика
- Не начинать писать "наугад"
- Обратить внимание на iOS/Android особенности

---

### 2️⃣ ПЛАН (Planning)

**Что делать:**
- Какие файлы трогаем? (TS, стили, тесты)
- Работаем ли с нативным кодом? (Swift/Kotlin)
- Какой порядок имплементации?
- Есть ли зависимости?
- Работает ли на обеих платформах?

**Процесс:**
```
Файлы (TS):
✅ packages/ui-kit/components/FormInput/FormInput.tsx
✅ packages/ui-kit/components/FormInput/FormInput.test.tsx
✅ packages/gj/src/screens/CheckoutScreen.tsx
✅ packages/gj/src/types/checkout.types.ts

Файлы (Стили):
✅ packages/ui-kit/components/FormInput/FormInput.styles.ts (styled-components)
✅ packages/gj/src/screens/CheckoutScreen.styles.ts

Файлы (Нативный код):
❌ iOS Swift — не нужен
❌ Android Kotlin — не нужен

Порядок:
1. Типы (checkout.types.ts) — основа
2. UI компонент (FormInput.tsx) — реиспользуемый
3. Тесты для компонента (FormInput.test.tsx)
4. Интеграция в ExportScreen (CheckoutScreen.tsx)
5. Тесты для экрана (E2E Detox)

Платформы:
✅ iOS — текстовое поле, native keyboard
✅ Android — текстовое поле, showSoftInput
✅ Оба: стили, поведение одинаковое

[NB] вопросы:
- Максимальная длина текста? (500 символов?)
- Нужна ли валидация? (не более 500)
- Нужна ли отправка на бэк? (да, в POST /checkout)
```

---

### 3️⃣ КОД (Implementation)

**Что делать:**
- Писать TypeScript код
- Следовать mobile-rn-conventions (naming, structure)
- Комментарии только "ПОЧЕМУ", не "ЧТО"
- Функции компонентов <50 строк (логика в hooks)
- Использовать hooks: useState, useEffect, useContext

**Правила:**
- shared-code-style обязателен
- Нет `any` типов (используй Generics)
- Нет закомментированного кода
- Нет console.log (только DEBUG при разработке)
- Нет magic numbers (использовать const)

**Процесс:**
```typescript
// ✅ ХОРОШО: ясные типы, понятные имена, компонент фокусирован
import React, { useState } from 'react';
import { TextInput, View } from 'react-native';
import styled from 'styled-components/native';

interface CommentInputProps {
  value: string;
  onChange: (text: string) => void;
  maxLength?: number;
  testID?: string;
}

const MAX_COMMENT_LENGTH = 500;
const COMMENT_CONTAINER_HEIGHT = 100; // dp

const InputContainer = styled(View)`
  min-height: ${COMMENT_CONTAINER_HEIGHT}px;
  padding: 12px;
`;

const StyledInput = styled(TextInput)`
  font-size: 16px;
  color: #000;
  flex: 1;
`;

export const CommentInput: React.FC<CommentInputProps> = ({
  value,
  onChange,
  maxLength = MAX_COMMENT_LENGTH,
  testID = 'comment-input',
}) => {
  return (
    <InputContainer>
      <StyledInput
        testID={testID}
        multiline
        maxLength={maxLength}
        value={value}
        onChangeText={onChange}
        placeholder="Добавьте комментарий (опционально)"
        placeholderTextColor="#999"
      />
    </InputContainer>
  );
};
```

**Платформо-специфичный код:**
```typescript
// ✅ ХОРОШО: явные проверки платформ, не закомментированный код
import { Platform } from 'react-native';

// iOS и Android используют разные подходы для подписей keyboard
const keyboardBehavior = Platform.select({
  ios: 'padding' as const,
  android: 'height' as const,
});

// В компоненте
<KeyboardAvoidingView behavior={keyboardBehavior}>
  <CommentInput value={comment} onChange={setComment} />
</KeyboardAvoidingView>
```

**Документация типов (JSDoc):**
```typescript
/**
 * Компонент текстового поля для комментариев.
 * 
 * Особенности:
 * - Поддерживает многострочный текст
 * - Ограничение по длине (по умолчанию 500)
 * - Отличается поведение keyboard между iOS и Android
 * 
 * @example
 * <CommentInput
 *   value={comment}
 *   onChange={setComment}
 *   maxLength={500}
 *   testID="order-comment"
 * />
 */
```

---

### 4️⃣ SECURITY (Security Checks)

**Что проверять:**

| Проверка | Мобильная специфика | Действие |
|----------|-------------------|---------|
| **Нет secrets in code** | API ключи в `.env.development` (не коммитить) | Use environment configs |
| **Нет PII in logs** | Не логируем user_id, email, phone в консоль | Используй react-native-logger или Sentry |
| **Нет hardcoded URLs** | API endpoints в конфиге, не в коде | Читать из config файла |
| **Деньги** | Yookassa token, платежи только на HTTPS | Использовать rn-yookassa-sdk обёртку |
| **Permissions** | iOS/Android требуют явных прав (камера, микро, местоположение) | Запрашивать только необходимое |
| **Сохранение данных** | Не сохранять пароли, tokens в AsyncStorage (незашифрованно) | Использовать react-native-keychain |

**Процесс:**
```typescript
// ✅ ХОРОШО: secrets в config, не в коде
// config.ts
export const API_CONFIG = {
  baseUrl: process.env.REACT_APP_API_URL || 'https://api.gj.dev',
  yooKassaId: process.env.REACT_APP_YOOKASSA_ID,
};

// ❌ ПЛОХО: hardcoded URL
const response = await fetch('https://api.prod.com/checkout');

// ✅ ХОРОШО: явные логирования без PII
logger.debug('Order created', { orderId: '123' }); // ✅ только ID
logger.debug('User email:', user.email); // ❌ PII!

// ✅ ХОРОШО: использовать Keychain для tokens
import * as SecureStore from 'react-native-secure-store';
await SecureStore.setItem('auth_token', token);
```

**Проверка permissions:**
```typescript
// ✅ ХОРОШО: явный запрос прав перед использованием
import { PermissionsAndroid } from 'react-native';

const requestCameraPermission = async () => {
  try {
    const granted = await PermissionsAndroid.request(
      PermissionsAndroid.PERMISSIONS.CAMERA,
      {
        title: 'Доступ к камере',
        message: 'Нам нужен доступ к камере',
        buttonPositive: 'OK',
      },
    );
    return granted === PermissionsAndroid.RESULTS.GRANTED;
  } catch (err) {
    logger.error('Camera permission error', err);
    return false;
  }
};
```

---

### 5️⃣ ТЕСТЫ (Testing)

**Что писать:**

| Тип | Что тестировать | Инструмент |
|-----|-----------------|-----------|
| **Unit** | Функции, hooks, utils | Jest + React Testing Library |
| **Component** | Рендер компонента, props, callbacks | Jest + @testing-library/react-native |
| **Platform-specific** | iOS vs Android различия | Platform.select проверка |
| **E2E** | Полный пользовательский flow | Detox (на CI для staging) |
| **Performance** | Нет memory leaks, listview оптимизирован | Reactotron, React Profiler |

**Процесс:**

```typescript
// Unit тесты
import { render, fireEvent } from '@testing-library/react-native';
import { CommentInput } from './CommentInput';

describe('CommentInput', () => {
  it('должен отрендериться с правильными props', () => {
    const { getByTestId } = render(
      <CommentInput 
        value=""
        onChange={() => {}}
        testID="comment-input"
      />
    );
    expect(getByTestId('comment-input')).toBeTruthy();
  });

  it('должен вызвать onChange при вводе текста', () => {
    const onChange = jest.fn();
    const { getByTestId } = render(
      <CommentInput 
        value=""
        onChange={onChange}
      />
    );
    const input = getByTestId('comment-input');
    fireEvent.changeText(input, 'hello');
    expect(onChange).toHaveBeenCalledWith('hello');
  });

  it('должен ограничивать длину до maxLength', () => {
    const { getByTestId } = render(
      <CommentInput 
        value=""
        onChange={() => {}}
        maxLength={10}
      />
    );
    const input = getByTestId('comment-input');
    expect(input.props.maxLength).toBe(10);
  });

  it('должен правильно обрабатывать пустое значение', () => {
    const { getByTestId } = render(
      <CommentInput 
        value=""
        onChange={() => {}}
      />
    );
    expect(getByTestId('comment-input').props.value).toBe('');
  });
});

// E2E тесты (Detox)
describe('Checkout Comment Flow', () => {
  beforeAll(async () => {
    await device.launchApp();
  });

  beforeEach(async () => {
    await device.reloadReactNative();
  });

  it('должен заполнить комментарий и отправить заказ', async () => {
    await element(by.text('Оформить заказ')).tap();
    
    // Найти поле комментария
    await element(by.id('comment-input')).typeText('Позвоните перед доставкой');
    
    // Нажать кнопку подтверждения
    await element(by.id('submit-order')).tap();
    
    // Проверить что отправилось
    await expect(element(by.text('Заказ создан'))).toBeVisible();
  });
});
```

**Правила тестирования:**
- ✅ Каждый компонент имеет unit тесты
- ✅ Каждый сложный экран имеет E2E тест
- ✅ Coverage >80%
- ✅ Тесты используют testID для Detox
- ✅ Мокируем API с MSW (mock service worker) или jest.mock()
- ✅ Нет флакящих тестов (используй waitFor вместо sleep)

---

### 6️⃣ КОММИТ (Commit)

**Что делать:**
- Правильная ветка: feature/*, fix/*, refactor/*
- Сообщение ясное на русском
- Co-Authored-By добавить
- Все тесты зелёные
- Линтер пройден

**Процесс:**
```bash
# Проверка перед коммитом
git status           # только нужные файлы?
yarn lint            # нет ошибок ESLint?
yarn gj:ts           # TypeScript OK?
yarn test            # все тесты зелёные?

# Формат коммита
git commit -m "feat(checkout): добавить поле комментария

- Создан компонент CommentInput в ui-kit
- Интегрирован в CheckoutScreen
- Отправляется на бэк в POST /checkout
- Поддержаны iOS и Android
- Добавлены unit тесты (coverage 90%)
- Добавлен E2E тест в Detox

AC выполнены:
- CommentInput рендерится ✅
- Максимум 500 символов ✅
- Платформы iOS/Android работают ✅
- Unit тесты: 10/10 ✅
- E2E тесты: ✅

Co-Authored-By: Claude Haiku <noreply@anthropic.com>"
```

**Важно:**
- Коммиты должны быть атомарными (одна фича = один коммит)
- Не смешивать refactor и новые фичи
- Сообщения на русском, чёткие и ясные

---

### 7️⃣ MR (Merge Request)

**Что делать:**
- Правильный target branch (обычно develop, release-* для хотфиксов)
- Описание: ссылка на задачу, что изменилось
- Скриншоты/видео UI изменений
- Все тесты зелёные в CI
- Detox E2E прошли

**Процесс:**
```bash
git push origin feature/checkout-comment

# Создать MR через GitLab
Title: "feat(checkout): добавить поле комментария"

Description:
"## Summary
Добавляем поле комментария в чекаут. Пользователь может написать 
предпочтения для доставки (позвонить перед доставкой, положить на крыльцо и т.д.)

## Changes
- **ui-kit:** Создан компонент CommentInput (переиспользуемый)
- **gj-app:** Интегрирован в CheckoutScreen
- **API:** Отправляется в POST /checkout (field: orderComment)
- **Платформы:** iOS и Android полностью поддерживаются

## Screenshots
[iOS screenshot: поле видно, клавиатура появляется]
[Android screenshot: то же самое, но другой стиль клавиатуры]

## Test plan
- [ ] Unit тесты: yarn test (coverage 90%)
- [ ] Lint: yarn lint (no errors)
- [ ] TypeScript: yarn gj:ts (strict mode)
- [ ] E2E: Detox (Checkout Comment Flow test passed)
- [ ] Manual iOS staging: yarn gj:ios:staging
- [ ] Manual Android staging: yarn gj:android:staging

## Fixes
Closes OPSOMN002-XXX"

✅ MR ГОТОВ → передаём Ревьюерам
```

**Требования к MR:**
- Описание заполнено полностью
- Скриншоты/видео для UI изменений
- Ссылка на задачу
- Все статусы CI зелёные
- testID добавлены для Detox

---

## ✨ Мобильная специфика

### iOS vs Android

**Клавиатура:**
```typescript
import { Platform, KeyboardAvoidingView } from 'react-native';

<KeyboardAvoidingView 
  behavior={Platform.select({
    ios: 'padding',
    android: 'height',
  })}
>
  <CommentInput {...props} />
</KeyboardAvoidingView>
```

**Размеры и отступы:**
```typescript
import { Dimensions, Platform } from 'react-native';

const screenHeight = Dimensions.get('screen').height;
const statusBarHeight = Platform.select({
  ios: 50,      // Safe area + status bar
  android: 24,  // Status bar only
});
```

**Безопасные области (Safe Area):**
```typescript
import { useSafeAreaInsets } from 'react-native-safe-area-context';

const Component = () => {
  const insets = useSafeAreaInsets();
  return (
    <View style={{ paddingTop: insets.top, paddingBottom: insets.bottom }}>
      {/* Автоматически позиционируется с учётом notch/safe area */}
    </View>
  );
};
```

### Build Flavors

```bash
# Development (для разработчика)
yarn gj:start                    # Metro
yarn gj:ios:development          # Xcode simulator
yarn gj:android:development      # Android emulator

# Staging (для QA)
yarn gj:ios:staging
yarn gj:android:staging

# Production (что попадает в App Store / Play Store)
yarn gj:ios:production
yarn gj:android:production
```

**Переменные окружения:**
```bash
# .env.development
REACT_APP_API_URL=https://api.staging.gj.dev
REACT_APP_LOG_LEVEL=debug
REACT_APP_YOOKASSA_ID=test_xxx

# .env.staging
REACT_APP_API_URL=https://api.staging.gj.dev
REACT_APP_LOG_LEVEL=info
REACT_APP_YOOKASSA_ID=staging_xxx

# .env.production
REACT_APP_API_URL=https://api.gj.com
REACT_APP_LOG_LEVEL=error
REACT_APP_YOOKASSA_ID=prod_xxx
```

### Debugging

**Reactotron (встроен в проект):**
```typescript
// Запустить Reactotron desktop app
// Приложение автоматически подключится

// В коде:
import Reactotron from 'reactotron-react-native';

Reactotron.log('Payment status:', status);
Reactotron.display({ name: 'Order', value: order });
```

**React Native Debugger:**
```bash
# Chrome DevTools для JavaScript debugging
yarn gj:start
# Нажать 'd' в Metro, выбрать "Open in Debugger"
```

### Patch-package для зависимостей

Если надо пропатчить зависимость:
```bash
# 1. Отредактировать node_modules/library/file.js
# 2. Создать патч
yarn patch-package library

# 3. Коммитить patches/library+version.patch
git add patches/
git commit -m "fix: patch library"

# 4. Восстановить после install
yarn install  # автоматически применяет patches
```

---

## 📋 Важные правила

### Правило 1: ВСЕГДА 7 шагов
- Нет сокращений
- Нет "напишу как думаю"
- Даже если просто, пройти все 7 шагов

### Правило 2: ПЛАТФОРМЫ ИМЕЮТ ЗНАЧЕНИЕ
- Тестировать на iOS И Android
- Не предполагать что работает везде
- Используй Platform.select() для различий

### Правило 3: testID обязателен для Detox
```typescript
<TextInput testID="comment-input" />  // ✅ Detox может найти
<TextInput />                         // ❌ Detox не видит
```

### Правило 4: TypeScript strict mode
- Нет `any`
- Типизируй props, state, callbacks
- Используй Generics для переиспользуемости

### Правило 5: Стили через styled-components
```typescript
// ✅ ХОРОШО
import styled from 'styled-components/native';
const Container = styled(View)`
  padding: 16px;
`;

// ❌ ПЛОХО
const styles = StyleSheet.create({
  container: { padding: 16 },
});
<View style={styles.container} />  // Нет типизации
```

### Правило 6: Hooks вместо class components
```typescript
// ✅ ХОРОШО
const MyComponent: React.FC<Props> = (props) => {
  const [state, setState] = useState(0);
  return <View />;
};

// ❌ ПЛОХО (legacy)
class MyComponent extends React.Component {
  state = {};
}
```

### Правило 7: Performance matters
- Используй React.memo для статичных компонентов
- Мемоизируй callbacks (useCallback)
- Оптимизируй списки (FlatList, не ScrollView)

---

## 🎓 Полный пример

```
ШАГ 1: ПОНИМАНИЕ
✅ Добавить комментарий в чекаут
✅ Текстовое поле, до 500 символов
✅ iOS + Android должны работать
✅ Нет [BLOCKER]

ШАГ 2: ПЛАН
✅ Создать CommentInput (ui-kit)
✅ Интегрировать в CheckoutScreen
✅ Добавить тесты (Jest + Detox)
✅ Проверить платформы

ШАГ 3: КОД
✅ CommentInput.tsx (компонент с типами)
✅ styled-components стили
✅ Platform.select() для клавиатуры
✅ JSDoc документация

ШАГ 4: SECURITY
✅ API URL из config (не hardcoded)
✅ Нет PII в логах
✅ Платежи через rn-yookassa-sdk

ШАГ 5: ТЕСТЫ
✅ Unit тесты (Jest): 10/10
✅ E2E тест (Detox): Checkout Comment Flow
✅ Coverage: 90%
✅ Нет флакирующих тестов

ШАГ 6: КОММИТ
✅ Ветка feature/checkout-comment
✅ Сообщение ясное
✅ Co-Authored-By добавлен
✅ yarn test, yarn lint пройдены

ШАГ 7: MR
✅ MR создана в develop
✅ Описание полное
✅ Скриншоты iOS + Android
✅ Все CI статусы зелёные

→ ГОТОВО! MR передана ревьюерам
```

---

## 🚀 Как использовать

1. **Ты разработчик мобильного приложения?** → Загрузить этот файл
2. **Получил постановку?** → Следовать 7 шагам ВСЕГДА
3. **Готовишь MR?** → Проверить что все 7 шагов выполнены
4. **Есть вопросы?** → Перечитать этот файл или прочитать:
   - `mobile-rn-conventions.md` — соглашения кода
   - `mobile-build-commands.md` — команды сборки
   - `mobile-stack-anatomy.md` — архитектура стека

---

## 📊 Чеклист перед MR

- [ ] ПОНИМАНИЕ: Прочитал постановку полностью
- [ ] ПЛАН: Определил все файлы и порядок
- [ ] КОД: Написал код по mobile-rn-conventions
- [ ] SECURITY: Нет secrets, PII, hardcoded URLs
- [ ] ТЕСТЫ: Unit тесты (Jest) >80% coverage
- [ ] ТЕСТЫ: E2E тесты (Detox) для пользовательского flow
- [ ] ПЛАТФОРМЫ: Тестировал на iOS И Android
- [ ] СТИЛЬ: yarn lint и yarn gj:ts без ошибок
- [ ] КОММИТ: Правильное сообщение, Co-Authored-By
- [ ] MR: Описание заполнено, скриншоты добавлены
- [ ] CI: Все статусы зелёные (lint, test, type-check)

---

**Версия:** 1.0  
**Дата:** 2026-10-06  
**Статус:** Production-ready  
**Автор:** Claude Haiku 4.5 + mobile team  
**Следующее:** Используй в реальных задачах, собирай метрики

🚀 **ГОТОВО К ИСПОЛЬЗОВАНИЮ!**
