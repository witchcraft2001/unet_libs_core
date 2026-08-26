# sprinter_unet_libs_core

Языко-нейтральное ядро сетевого стека UNET для Sprinter (Z80 / DSS):
замороженный ABI, вендоренные бекенд-DLL и текстовый справочник API. У
этого репозитория **нет git-сабмодулей**, и он не тянет ничего, кроме
стандартной библиотеки Python, так что любой потребитель может подключить
его, не притащив лишних зависимостей.

Этот репозиторий не предназначен для самостоятельного использования - это
общий фундамент, на котором построены три языковых репозитория:

| Репозиторий | Язык | Что добавляет поверх этого |
| --- | --- | --- |
| [sprinter_unet_libs_asm](https://github.com/witchcraft2001/sprinter_unet_libs_asm) | Z80 asm (SjASMPlus) | загрузчик `unetld.asm`, рабочие примеры |
| [sprinter_unet_libs_pascal](https://github.com/witchcraft2001/sprinter_unet_libs_pascal) | Turbo Pascal | загрузчик `UNETLD.PAS`, примеры |
| [sprinter_unet_libs_c](https://github.com/witchcraft2001/sprinter_unet_libs_c) | Solid C (позже SDCC) | загрузчик `UNETLD.C`, примеры |

Каждый из них подключает этот репозиторий git-сабмодулем в `extern/core`
вместо того, чтобы копировать DLL, ABI-заголовок или доки API - поэтому все
три всегда согласованы по ABI, а перевендоривание новой бекенд-DLL или
исправление опечатки в доке происходит ровно в одном месте.

Вся документация ведётся на двух языках; английские версии - без суффикса
`RU`: [README.md](README.md), [docs/UNETAPI.md](docs/UNETAPI.md),
[docs/UNETLD-SPEC.md](docs/UNETLD-SPEC.md).

## Что здесь есть

```
abi/unet_abi.toml          единый источник истины ABI UNET и кодов
                            загрузчика UNETLD_E_*/UNETLD_F_*
bindings/asm/unet.inc       сгенерировано - заголовок EQU для SjASMPlus
bindings/solidc/UNET.H      сгенерировано - K&R-safe заголовок #define
bindings/pascal/UNET.PUI    сгенерировано - const-only юнит в стиле TP3
dll/UNETESP.DLL             готовый бекенд WiFi/ESP8266
dll/UNETRTL.DLL             готовый бекенд ISA-карты RTL8019A
dll/manifest.json           size/sha256/версия/происхождение обеих DLL
docs/UNETAPI.md             контракт функций UNET (текстовый справочник)
docs/UNETLD-SPEC.md         поведение загрузчика/селектора UNETLD (языко-нейтрально)
tools/gen_bindings.py       рендерит bindings/ из abi/unet_abi.toml
tools/check_dlls.py         сверяет вендоренные DLL с манифестом
tools/update_dlls.sh        инструмент мейнтейнера: перевендорить свежие DLL
tools/udp_echo.py           хостовый UDP echo-хелпер для примера UDPECHO
```

## Подключение как сабмодуля

Напрямую от этого репозитория ожидается зависеть только языковым
репозиториям:

```sh
git submodule add https://github.com/witchcraft2001/sprinter_unet_libs_core.git extern/core
```

Рекурсивно клонировать не требуется - у этого репозитория нет собственных
сабмодулей.

## Источник истины ABI

[abi/unet_abi.toml](abi/unet_abi.toml) - единственное место, где заданы
все номера функций UNET, коды ошибок, биты возможностей, id полей GETINFO,
id SETOPT и коды загрузчика UNETLD (`UNETLD_E_*`/`UNETLD_F_*`), вместе с их
документирующей прозой. Он **заморожен**: существующие пары имя/значение
никогда не меняются, используются только новые зарезервированные слоты.

[tools/gen_bindings.py](tools/gen_bindings.py) рендерит его в
`bindings/<таргет>/`:

```sh
tools/gen_bindings.py gen                  # перегенерировать всё
tools/gen_bindings.py gen --target asm     # только один таргет
tools/gen_bindings.py check                # проверить, что bindings/ соответствует TOML (ненулевой exit при дрейфе)
tools/gen_bindings.py compare --inc FILE   # сверить карту имя->значение старого файла
                                            # "NAME EQU value" с TOML
```

Сгенерированные файлы несут баннер `GENERATED - DO NOT EDIT` - правьте
TOML и перезапускайте `gen`, никогда не редактируйте руками ничего внутри
`bindings/`. `make check` запускает и `gen_bindings.py check`, и
`check_dlls.py`.

Поскольку сгенерированный `bindings/asm/unet.inc` не побайтово идентичен
исходному рукописному `include/unet.inc`, который он заменил (другой
баннер, перегенерированное форматирование комментариев), побайтовое
сравнение здесь не способ ловить дрейф. Вместо него - две проверки:
`gen_bindings.py compare` доказывает, что карта *имя -> значение* точно
совпадает с внешним файлом (используется и как одноразовое доказательство
миграции, и как upstream-tripwire в `update_dlls.sh`, ниже), а собранные
EXE примеров в каждом языковом репозитории должны побайтово совпадать со
своими сборками до миграции (значения констант идентичны, значит идентичен
и собранный код).

## Обновление вендоренных DLL

```sh
tools/update_dlls.sh
```

Копирует свежие `UNETESP.DLL`/`UNETRTL.DLL` из соседних чекаутов проектов-
бекендов (переопределяется переменными среды `UNETESP_SRC`/`UNETRTL_SRC`),
обновляет size/sha256 в `dll/manifest.json` (поле `version` правьте
вручную), перепроверяет и предупреждает, если замороженный ABI в
`abi/unet_abi.toml` разошёлся с исходным `unet.inc`, из которого он был
вендорен (через `gen_bindings.py compare`, а не побайтовый `cmp` - см.
выше).

`tools/check_dlls.py` сам по себе сверяет size и sha256 с манифестом - без
зависимостей сверх этого репозитория. Дополнительно он может запустить
`sprinter_mkdll verify` (более строгую структурную проверку), если указать
`LIBMAN_ROOT` на чекаут libman, например вендоренный `unet_libs_asm`:

```sh
LIBMAN_ROOT=../unet_libs_asm/extern/libman tools/check_dlls.py
```

Без `LIBMAN_ROOT` этот шаг пропускается с уведомлением (exit всё равно 0,
пока совпадают size/sha256); `--require-mkdll` превращает отсутствие
`LIBMAN_ROOT` в жёсткий отказ. `update_dlls.sh` по умолчанию берёт
`LIBMAN_ROOT` из соседнего чекаута `unet_libs_asm/extern/libman`, если он
есть, и всегда требует его.

Имя DLL в её L1-заголовке при загрузке сверяется только по префиксу
(`UNET` + тег `NET`) - версия в суффиксе намеренно не фиксируется. Настоящая
build-time идентичность - это `sha256` в `dll/manifest.json`.

## Переменные среды

`NET` выбирает бекенд: её значение (3-4 символа, `[A-Z0-9]`, регистр не
важен) напрямую становится именем DLL - `NET=RTL` загружает
`UNETRTL.DLL`, `NET=WIZ` загрузил бы `UNETWIZ.DLL` и так далее. `WIFI` -
единственное встроенное исключение, алиас на `UNETESP.DLL` для
совместимости с существующими инструментами. Как в эту схему добавить
новый бекенд - см.
[docs/UNETLD-SPECRU.md](docs/UNETLD-SPECRU.md#добавление-бекенда).

`NET` *публикуется инструментом настройки бекенда* вместе с остальной его
конфигурацией - пользователи (и программы-потребители) не задают её
вручную. Если переменной нет, правильное действие всегда «запустить
инструмент настройки», а не `SET NET=...`:

| Бекенд | Инструмент настройки | Публикует |
| --- | --- | --- |
| WiFi (`UNETESP.DLL`) | `NETUP` | `NET=WIFI`, `NET_ESP_*`, `NET_IP`/`NET_MASK`/`NET_GW`/`NET_MAC`/... |
| RTL8019A (`UNETRTL.DLL`) | `NETCFG -i`, затем `IFUP` | `NET=RTL`, `NET_RTL_*`, `NET_IP`/`NET_MASK`/`NET_GW`/`NET_MAC`/... |

Инструменты настройки берите из дистрибутива своего бекенда: `NETUP`
входит в комплект WiFi-кита
([sprinter_net](https://github.com/witchcraft2001/sprinter_net)),
`NETCFG`/`IFUP` - в комплект RTL-кита
([sprinter-rtl8019a](https://github.com/witchcraft2001/sprinter-rtl8019a)).
`UNET_FN_STATUS` с `A=0xFF` проверяет, что эта конфигурация опубликована, не
трогая железо - удобно для дружелюбного сообщения «сначала запустите
NETUP/IFUP». Полный список переменных и справочник функций UNET - в
[docs/UNETAPIRU.md](docs/UNETAPIRU.md).

## Правила работы с памятью

Взяты из самого UNET ABI (см. `abi/unet_abi.toml`) и из DSS:

- Загружать DLL только в окно 1 (`0x4000`) или окно 2 (`0x8000`) -
  **никогда в окно 3** (`0xC000`): бекенд ESP отображает туда железо на
  время каждого вызова.
- Любой буфер, переданный в функцию UNET (строки host/port, данные
  send/recv, назначение `GETINFO`), должен целиком лежать ниже `0xC000` и
  вне окна, куда загружена DLL.
- Строка host - не длиннее 128 байт, строка port - не длиннее 15 байт.
- На время вызова UNET должно оставаться не меньше ~256 байт свободного
  стека.
- UNET не реентерабелен - один вызов за раз.

## Лицензия

BSD 3-Clause, см. [LICENSE](LICENSE). Вендоренные DLL остаются под
лицензиями своих родительских проектов - происхождение указано в
`dll/manifest.json`.
