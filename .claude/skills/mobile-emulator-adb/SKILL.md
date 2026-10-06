---
name: mobile-emulator-adb
description: Use when running, installing, debugging, or testing the Gloria Jeans mobile app (React Native) on an Android emulator via adb — booting AVDs, adb install/launch/logcat/reverse/screenshot/input, the build→run→verify loop, unit/detox tests on a device. Triggers on "запусти на эмуляторе", "adb", "logcat", "поставь apk", "почему не коннектится к metro", "сделай скриншот экрана", "прогони тесты на девайсе". Supports verification step of `pattern-development-mobile`.
---

# Mobile Emulator + adb (Android)

**See also:** [`pattern-development-mobile.md`](../pattern-development-mobile.md) — use this skill in step 6 (Verification) to test changes on a device.

Всё про запуск/отладку **gj-app** на Android-эмуляторе. Для чистых yarn-скриптов и iOS — см. `mobile-build-commands`. Стек и раскладка репо — `mobile-stack-anatomy`.

Рабочая директория yarn: `platform/mobile-app/gj-app/`.
Android-проект: `platform/mobile-app/gj-app/packages/gj/android/`.

## Ключевые факты (не переоткрывать)

| Что | Значение |
|-----|----------|
| SDK | `~/Library/Android/sdk` (`ANDROID_HOME` уже выставлен) |
| adb | `~/Library/Android/sdk/platform-tools/adb` |
| emulator | `~/Library/Android/sdk/emulator/emulator` |
| appId development | `com.gloriajeans.mobile.development` |
| appId staging | `com.gloriajeans.mobile.staging` |
| appId production | `com.gloriajeans.mobile` |
| Launcher Activity | `<appId>/com.gloriajeans.mobile.MainActivity` (класс всегда без суффикса) |
| Metro порт | `8081` (нужен `adb reverse`) |
| env-файлы | `packages/gj/.env.{development,staging,production}` |
| flavor dimension | `environment` → gradle-варианты `developmentDebug`, `stagingDebug`, `productionDebug` (+`*Release`) |

Если `adb`/`emulator` не в PATH — вызывай по полному пути или `export PATH="$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"`.

## Эмулятор: жизненный цикл

```bash
emulator -list-avds                       # какие AVD есть
emulator -avd <AVD> -netdelay none -netspeed full &   # запуск в фоне
# headless / CI: добавь -no-window -no-snapshot -gpu swiftshader_indirect
adb devices                               # проверить, что появился emulator-5554
```

Дождаться полной загрузки перед install (иначе INSTALL_FAILED):

```bash
adb wait-for-device
until [ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; do sleep 2; done
echo "booted"
```

> Долгий `emulator ... &` и `until`-ожидание запускай через фоновый режим Bash, не блокируй сессию `sleep`.

## Сборка + запуск на эмуляторе

Проще всего — yarn-скрипт (сам соберёт gradle, поставит apk, поднимет metro):

```bash
cd platform/mobile-app/gj-app
yarn gj:start &                # Metro (--reset-cache), в фоне
yarn gj:android:development    # developmentDebug на активный девайс
# staging / production:
yarn gj:android:staging
yarn gj:android:production
```

`run-android` сам ставит нужный вариант и делает launch. Если девайсов несколько — задай цель:

```bash
export ANDROID_SERIAL=emulator-5554     # адресует ВСЕ adb/run-android команды
```

### Ручной цикл (когда apk уже собран)

```bash
# apk после gradle-сборки лежат тут:
ls packages/gj/android/app/build/outputs/apk/development/debug/

adb install -r packages/gj/android/app/build/outputs/apk/development/debug/app-development-debug.apk
adb shell am start -n com.gloriajeans.mobile.development/com.gloriajeans.mobile.MainActivity
```

Gradle напрямую (без run-android):

```bash
cd packages/gj/android
./gradlew assembleDevelopmentDebug        # только сборка apk
./gradlew installDevelopmentDebug         # сборка + install на девайс
./gradlew clean                           # при странных ошибках сборки
```

## Metro connection (частый затык)

Эмулятор не видит `localhost:8081` хоста без reverse-проброса:

```bash
adb reverse tcp:8081 tcp:8081
```

Делай после каждого `boot`/переподключения девайса. Открыть dev-меню: `adb shell input keycode 82`. Reload: в dev-меню или `adb shell input text "RR"` в фокусе приложения не сработает — жми Reload из меню (keycode 82 → Reload).

## adb-шпаргалка

```bash
# Девайсы / состояние
adb devices -l
adb -s emulator-5554 <cmd>                # адресно, если девайсов много

# Приложение
adb install -r <apk>                       # переустановить, сохранив данные
adb uninstall com.gloriajeans.mobile.development
adb shell pm clear com.gloriajeans.mobile.development   # сброс данных/логина
adb shell am force-stop com.gloriajeans.mobile.development
adb shell monkey -p com.gloriajeans.mobile.development -c android.intent.category.LAUNCHER 1  # launch

# Диагностика
adb shell dumpsys package com.gloriajeans.mobile.development | grep -i version
adb shell pidof com.gloriajeans.mobile.development     # запущен ли процесс

# UI / ввод
adb shell input tap <x> <y>
adb shell input text "hello"               # ТОЛЬКО латиница/ASCII
adb shell input keycode 82                 # dev-меню
adb shell input keycode 4                  # BACK
adb exec-out screencap -p > /tmp/shot.png  # скриншот (exec-out = без CRLF-порчи)
adb shell screenrecord /sdcard/rec.mp4     # запись (Ctrl-C, потом adb pull)

# Deeplink (тест роутинга)
adb shell am start -a android.intent.action.VIEW -d "<scheme://path>" com.gloriajeans.mobile.development
```

Скриншот удобно прочитать инструментом Read (`/tmp/shot.png`) для верификации UI-изменений.

### Ввод текста: кириллица НЕ идёт через adb
`adb shell input text` принимает только латиницу/ASCII. На кириллице падает с `NullPointerException: Attempt to get length of null array` и НИЧЕГО не вводит — добавленная в системе русская раскладка это не чинит (ограничение самого `input text`, не клавиатуры). ADBKeyBoard в образе обычно не установлен.

**Правило:** НЕ пытайся слать кириллицу в `adb input text` (не трать на это попытки). Для полей, где нужен русский текст (адрес, ФИО, поиск), **печатай транслитом** — `adb shell input text "Polyarnaya"`. Если экран/подсказки требуют именно кириллицу (напр. dadata-подсказки улиц по РФ) и транслит не даёт результата — попроси пользователя набрать текст вручную на эмуляторе, затем сделай скриншот.

## logcat — экономно по токенам

Сырой logcat = тысячи строк. **Всегда фильтруй.** RN JS-логи идут через `ReactNativeJS`.

```bash
adb logcat -c                              # очистить буфер ПЕРЕД воспроизведением
# ... воспроизвести баг ...
adb logcat -d ReactNativeJS:V "*:S"        # -d = дамп и выход; только JS-логи
adb logcat -d "*:E"                        # только ошибки (краши, нативные)
adb logcat -d | grep -iE "gloriajeans|fatal|exception" | tail -50
adb logcat -d --pid=$(adb shell pidof com.gloriajeans.mobile.development)  # только наш процесс
```

- `-d` (дамп) вместо стрима — иначе команда не завершится и съест контекст.
- Никогда не лей полный `adb logcat` в ответ; бери `tail -N` или grep по симптому.
- Нативный краш: ищи `FATAL EXCEPTION` / `AndroidRuntime` / `signal 11`.

## Тесты

```bash
cd platform/mobile-app/gj-app
yarn gj:test                 # jest (весь) — НЕ требует эмулятора
yarn workspace GloriaJeans test:unit    # jest.unit.config.js

# Detox (e2e) — yarn-скрипты есть только под iOS-симулятор:
yarn gj:ios:detox:debug:build
yarn gj:ios:detox:debug:test
```

`packages/gj/.detoxrc.js` содержит и Android-конфигурации (`android.emu.debug` — AVD `Pixel_3a_API_30_x86`, `android.att.debug`), но yarn-скрипта под них нет, а `binaryPath`/`build` там generic (`assembleDebug`, а не flavored `assembleDevelopmentDebug`) — то есть под текущую флейвор-раскладку Android detox «из коробки» не поедет, нужна доводка конфига. Запуск вручную: `yarn workspace GloriaJeans detox test --configuration android.emu.debug`. Для быстрой функциональной проверки — ручной цикл выше (install → launch → adb input/screenshot → logcat).

## Стандартный цикл «проверь изменение на эмуляторе»

1. `adb devices` — есть живой эмулятор? нет → подними AVD, дождись `boot_completed`.
2. `adb reverse tcp:8081 tcp:8081`.
3. `yarn gj:start &` (если Metro не запущен).
4. `yarn gj:android:development` (сборка+install+launch) — или `adb install -r` + `am start`, если apk актуален.
5. `adb logcat -c` → воспроизвести → `adb logcat -d ReactNativeJS:V "*:S"`.
6. `adb exec-out screencap -p > /tmp/shot.png` → Read для визуальной проверки.
7. Перед «готово»: `yarn lint && yarn gj:ts` (см. `mobile-build-commands`).

## Troubleshooting

| Симптом | Причина / фикс |
|---------|----------------|
| `INSTALL_FAILED_*` сразу после boot | эмулятор не догрузился → ждать `sys.boot_completed=1` |
| `Unable to load script` / красный экран | нет Metro или reverse → `yarn gj:start` + `adb reverse tcp:8081 tcp:8081` |
| `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | другой подписи apk → `adb uninstall <appId>` затем install |
| несколько девайсов, команда падает | задать `ANDROID_SERIAL` или `adb -s <serial>` |
| старый JS после правок | Metro-кеш → `yarn gj:clean-cache && yarn gj:start` |
| gradle-мусор / странная сборка | `cd packages/gj/android && ./gradlew clean` |
| скриншот с битыми байтами | использовать `adb exec-out screencap -p` (не `adb shell ... >`) |
| logcat не завершается | забыл `-d` (дамп) |
| приложение стартует и падает молча | `adb logcat -d "*:E"` + смотреть `FATAL EXCEPTION` |

## Anti-patterns

- Полный `adb logcat` без `-d`/grep/tail в ответ — сжигает контекст.
- `adb install` до полной загрузки эмулятора.
- Забыть `adb reverse` и чинить «баг сети», которого нет.
- Прямой `pod install` / `npm install` — ломает bundler/lockfile (см. `mobile-build-commands`).
- Придумывать Android detox-конфиг, которого нет в репо.
