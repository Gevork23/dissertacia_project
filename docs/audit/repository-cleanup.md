# Repository Cleanup Audit

## 1. Цель фазы

Фаза 2 была выполнена как инженерная чистка репозитория после контрольной ревизии: убрать технический мусор, локальные runtime-артефакты, небезопасные environment-файлы, локальную базу, дублирующиеся документы и обновить правила игнорирования без изменения архитектуры, API, моделей или бизнес-логики.

## 2. Исходное состояние после Фазы 1

`docs/audit/current-state-audit.md` в переданном архиве не найден. Поэтому состояние после Фазы 1 было восстановлено по файловой системе, `.gitignore`, README, Docker/Scripts-конфигурации и Git metadata из архива.

Ключевые наблюдения исходного состояния:

- Git metadata присутствует: каталог `.git/` есть, `git status` доступен.
- После нормализации рабочей копии из Git-индекса содержательные tracked-изменения отсутствовали.
- В архиве присутствовали локальные runtime-артефакты: `backend/db.sqlite3`, `backend/media/`, `backend/logs/backend.log`, `infra/.env`.
- В дереве присутствовали Python cache-артефакты: 11 директорий `__pycache__/` и 157 файлов `.pyc`.
- В `docs/` были дубли PDF-документов: пары с именами `#U...pdf` и кириллическими именами имели одинаковые Git object hash. Оставлены человекочитаемые кириллические имена.

## 3. Проверенные области

- root directory
- backend
- docs
- scripts
- data
- media/uploads
- environment files
- caches
- logs
- databases
- archives
- generated files
- git status

## 4. Найденный технический мусор

| Категория | Примеры | Количество/пути | Решение |
|---|---|---|---|
| Python cache | `__pycache__/`, `*.pyc` | 11 директорий, 157 файлов `.pyc` | Удалить безопасно |
| Логи | `backend/logs/backend.log` | 1 файл, около 956 KB | Удалить безопасно как локальный runtime artifact |
| Локальная SQLite-база | `backend/db.sqlite3` | 1 файл, около 540 KB | Удалить: база воспроизводится миграциями, не должна храниться в архиве |
| Local uploads/media | `backend/media/documents/...` | 822 файла, около 56 KB | Удалить: это локальные загрузки/результат тестов, не demo/evaluation corpus |
| Environment file | `infra/.env` | 1 файл | Удалить: `.env` не должен попадать в передаваемый архив; оставить `.env.example` |
| Дублирующиеся PDF | `docs/#U041f...pdf`, `docs/#U0421...pdf` | 6 файлов | Удалить дубли с кривыми `#U...` именами; оставить кириллические PDF с теми же Git object hash |
| Архивы | `*.zip`, `*.tar`, `*.tar.gz` | Не найдены внутри проекта | Ничего не удалялось |
| IDE/editor/OS files | `.idea/`, `.vscode/`, `.DS_Store`, `Thumbs.db` | Не найдены | Добавлены/подтверждены правила в `.gitignore` |
| Coverage/cache reports | `.coverage`, `htmlcov/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/` | Не найдены в финальном состоянии | Правила подтверждены/добавлены в `.gitignore` |

## 5. Удалённые файлы и директории

| Путь/маска | Причина удаления | Безопасность удаления |
|---|---|---|
| `**/__pycache__/` | Python bytecode cache | Безопасно: генерируется интерпретатором |
| `**/*.pyc` | Python bytecode files | Безопасно: генерируется интерпретатором |
| `backend/logs/` | Локальные runtime-логи | Безопасно: каталог пересоздаётся приложением |
| `backend/db.sqlite3` | Локальная dev/test база | Осторожное удаление: база не tracked, воспроизводится миграциями |
| `backend/media/` | Локальные uploaded/generated файлы | Осторожное удаление: файлы не tracked, demo corpus находится отдельно в `data/`/`docs/` |
| `infra/.env` | Локальный environment-файл | Безопасно и необходимо для публикации: вместо него оставлен `infra/.env.example` |
| `docs/#U041f#U0424#U0420-02-1.pdf` | Дубль PDF с кривым именем | Безопасно после сверки Git object hash с `docs/ПФР-02-1.pdf` |
| `docs/#U041f#U0424#U0420-02-2.pdf` | Дубль PDF с кривым именем | Безопасно после сверки Git object hash с `docs/ПФР-02-2.pdf` |
| `docs/#U0421#U0423-35-1.pdf` | Дубль PDF с кривым именем | Безопасно после сверки Git object hash с `docs/СУ-35-1.pdf` |
| `docs/#U0421#U0423-35-2.pdf` | Дубль PDF с кривым именем | Безопасно после сверки Git object hash с `docs/СУ-35-2.pdf` |
| `docs/#U0421#U0423-49-1.pdf` | Дубль PDF с кривым именем | Безопасно после сверки Git object hash с `docs/СУ-49-1.pdf` |
| `docs/#U0421#U0423-49-2.pdf` | Дубль PDF с кривым именем | Безопасно после сверки Git object hash с `docs/СУ-49-2.pdf` |

## 6. Файлы, которые НЕ удалялись

| Путь/категория | Почему оставлено | Что проверить позже |
|---|---|---|
| `backend/**/migrations/*.py` | Django migrations являются частью схемы и истории БД | Не удалять; проверять только при отдельной миграционной ревизии |
| `backend/documents/tests/` | Тесты нужны для регрессионной проверки | Сохранить и использовать через `scripts/test.sh` или запуск из `backend/` |
| `scripts/` | Скрипты lint/test/smoke нужны для воспроизводимости | Уточнить README-команды, если нужно |
| `docs/*.md` | Документация нужна для научной упаковки | Позже возможна редакторская ревизия, но не удаление в Фазе 2 |
| `docs/ПФР-02-*.pdf`, `docs/СУ-*.pdf` | Человекочитаемые версии PDF-документов; сохранены как corpus/demo materials | В следующих фазах решить, должны ли они жить в `docs/` или `data/demo_corpus/` |
| `data/manual_samples/*` | Manual sample corpus для extraction/demo/tests | Проверить структуру corpus позже, не удалять в Фазе 2 |
| `data/importance_dataset/*` | Dataset для правил значимости | Проверить актуальность в ML/evaluation-фазе |
| `infra/.env.example` | Безопасный шаблон окружения | Поддерживать синхронно с `backend/config/settings.py` |
| `docker-compose.yml`, `backend/Dockerfile`, `backend/entrypoint.sh` | Инфраструктура запуска | Не изменялась, кроме удаления локального `.env` |

## 7. Обновления `.gitignore`

Текущий `.gitignore` уже покрывал значительную часть Python/Django мусора: `__pycache__/`, `*.py[codz]`, `.pytest_cache/`, `.coverage`, `htmlcov/`, `*.log`, `db.sqlite3`, `.env`, `*.env`, `media/`, `uploads/`, `backend/media/`, `backend/logs/`, `.mypy_cache/`, `.ruff_cache/`, `.DS_Store`, `Thumbs.db`.

Добавлен блок `Phase 2 repository hygiene`:

- `*.pyo`
- `*.pyd`
- `*.sqlite3`
- `*.sqlite3-journal`
- `.env.local`
- `.env.*.local`
- `*.env.local`
- `*.env.*.local`
- `.idea/`
- `.vscode/`
- `.mypy_cache/`
- `.ruff_cache/`
- `.coverage.*`
- `htmlcov/`
- `Thumbs.db`
- `.DS_Store`

Не добавлялись агрессивные правила вроде `data/`, `docs/`, `*.pdf`, `*.docx`, потому что проект содержит demo/manual corpus и документацию.

## 8. Проверка `.env` и секретов

Найден `infra/.env`; он удалён из очищенной рабочей копии. В финальном состоянии из environment-файлов остаётся только `infra/.env.example`.

`infra/.env.example` обновлён безопасными placeholder-значениями:

- `DJANGO_SECRET_KEY=change-me`
- `ENTITY_LLM_API_KEY=change-me`
- `RESULT_LLM_ENABLED=False`
- safe local defaults для `RESULT_LLM_*`

Финальный redacted scan по паттернам `SECRET_KEY`, `API_KEY`, `PASSWORD`, `TOKEN`, `PRIVATE KEY`, `DATABASE_URL` показал только настройки/placeholder-значения в коде и `.env.example`. Реальные private keys, tokens, дампы credentials и tracked `.env` не обнаружены.

Важно: `docker-compose.yml` по-прежнему ожидает `infra/.env`. Для запуска через Docker нужно создать локальный файл вручную: скопировать `infra/.env.example` в `infra/.env` и при необходимости изменить значения. Сам `infra/.env` в репозитории храниться не должен.

## 9. Проверка локальных баз и media/uploads

Удалены:

- `backend/db.sqlite3` — локальная SQLite-база;
- `backend/media/` — локальные upload/generated-файлы;
- `backend/logs/` — runtime-логи.

После smoke-проверки эти артефакты были временно созданы повторно приложением и затем снова удалены. В финальном состоянии `db.sqlite3`, `backend/media/`, `backend/logs/*.log` отсутствуют.

## 10. Проверка архивов и дубликатов

Внутри проекта не найдено старых `*.zip`, `*.tar`, `*.tar.gz`, `*.tgz`, `*.rar`, `*.7z`.

Найдены и удалены 6 дублирующихся PDF с техническими `#U...` именами. Сохранены человекочитаемые версии:

- `docs/ПФР-02-1.pdf`
- `docs/ПФР-02-2.pdf`
- `docs/СУ-35-1.pdf`
- `docs/СУ-35-2.pdf`
- `docs/СУ-49-1.pdf`
- `docs/СУ-49-2.pdf`

`data/manual_samples/sample.pdf`, `data/manual_samples/samplepdf.pdf`, `data/manual_samples/sampleword.docx` оставлены как manual/demo samples.

## 11. Git status после чистки

Git metadata доступен. После чистки ожидаемый `git status --short`:

```text
 M .gitignore
 D docs/#U041f#U0424#U0420-02-1.pdf
 D docs/#U041f#U0424#U0420-02-2.pdf
 D docs/#U0421#U0423-35-1.pdf
 D docs/#U0421#U0423-35-2.pdf
 D docs/#U0421#U0423-49-1.pdf
 D docs/#U0421#U0423-49-2.pdf
 M infra/.env.example
?? docs/audit/
```

Удаления `docs/#U...pdf` осознанные: это дубликаты кириллических PDF.

## 12. Повторные проверки после чистки

| Команда | Статус | Комментарий |
|---|---|---|
| `python backend/manage.py check` | pass | Exit code 0: `System check identified no issues` |
| `python backend/manage.py makemigrations --check --dry-run` | pass | Exit code 0: `No changes detected` |
| `python backend/manage.py test` | pass | Exit code 0, но из root-команды обнаружено 0 tests; дополнительно `bash scripts/test.sh` прошёл 120 тестов |
| `bash scripts/lint.sh` | pass | Exit code 0: isort/black/flake8 passed |
| `bash scripts/demo_smoke.sh` | pass | Exit code 0: health, demo dashboard, upload, text payload passed |
| `python backend/manage.py runserver` | pass | Сервер стартовал, `/api/health/` ответил; после smoke сервер остановлен |

Дополнительная проверка:

| Команда | Статус | Комментарий |
|---|---|---|
| `bash scripts/test.sh` | pass | Exit code 0: `Ran 120 tests ... OK` |

## 13. Оставшиеся проблемы

- `docs/audit/current-state-audit.md` отсутствовал в архиве после Фазы 1.
- `python backend/manage.py test` из корня возвращает exit code 0, но находит 0 тестов; фактические тесты проходят через `bash scripts/test.sh` / запуск из `backend/`.
- `docker-compose.yml` требует локальный `infra/.env`, но в чистом репозитории он намеренно отсутствует. Это нужно явно указывать в инструкции запуска.
- В проекте есть сохранённые PDF/DOCX sample/corpus-файлы; они оставлены осознанно, но позже стоит решить, где должен жить demo corpus: `docs/` или `data/demo_corpus/`.

## 14. Риски

- Если пользователь запустит demo/smoke, снова появятся локальные `backend/db.sqlite3`, `backend/media/` и `backend/logs/`; `.gitignore` покрывает эти артефакты, но перед архивированием их нужно удалять.
- Наличие PDF/DOCX corpus в `docs/` может выглядеть неоднозначно для научной упаковки. Лучше в последующих фазах описать corpus явно или перенести его в `data/demo_corpus/`.
- Docker-запуск без локального `infra/.env` потребует явного шага `cp infra/.env.example infra/.env`.
- Архитектурные дубли service layer и LLM fallback-логика в этой фазе не исправлялись по ограничению scope.

## 15. Что переходит в Фазу 3

В Фазу 3 переходит только то, что связано с архитектурной чистотой и service layer:

- ревизия дублирующейся логики между workflow/service modules;
- проверка границ `workflows.py`, `quiz_attempts.py`, `result_reporting.py`;
- уточнение, где должен жить demo/document corpus;
- приведение README/SETUP к фактическому запуску, если это будет связано с архитектурным/операционным контуром.

LLM fallback-логика должна остаться для Фазы 4. MVP scope и научная упаковка — для следующих фаз.

## 16. Итоговый вывод

Фаза 2 выполнена: безопасный технический мусор удалён, локальные `.env`, SQLite DB, uploads/media и logs убраны, дубли PDF с техническими именами удалены после проверки, `.gitignore` усилен, `.env.example` обновлён безопасными placeholder-значениями, проверки после чистки выполнены. Репозиторий приведён в более чистое, воспроизводимое и пригодное для передачи состояние без архитектурного рефакторинга и без изменения бизнес-логики.
