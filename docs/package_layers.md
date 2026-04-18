# Слои пакетов (src/)

Краткие правила зависимостей и смыслы — подробнее в `__init__.py` каждого пакета.

| Пакет | Назначение | Может импортировать |
|-------|------------|---------------------|
| `shared` | Константы, версия, мелкие утилиты | stdlib, внешние библиотеки |
| `core` | Чистая логика и разбор данных (без I/O) | `shared`, stdlib |
| `config` | Модель прогона `ProvisionConfig`, валидация | `shared`, `core` |
| `server` | SSH, предпроверки, URL к скриптам | `shared`, `core`, `config` |
| `commands` | Удалённые шаги vpconnect-configure | `shared`, `config`, `server`, `application.outputs` |
| `application` | Оркестрация полного прогона | `shared`, `config`, `server`, `commands`, `application.outputs` |
| `cli` | Argparse и запуск сценария | `shared`, `config`, `application` |
| `gui` | Tkinter UI | `shared`, `config`, `core`, `application` |
| `vpconnect_install` | Точка входа `python -m …`, публичный API версии | `cli`, `gui`, `shared` |

**Запрещено:** `core` не тянет `server`/`gui`/`cli`; `cli` и `gui` не импортируют друг друга.

## Тесты

Зеркальная структура в [`tests/`](../tests/README.md): подкаталог на каждый пакет из таблицы выше.
