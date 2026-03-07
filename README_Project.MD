# DSTU Dissertation Project (Dissertacia)

Backend-сервис для загрузки версий нормативных документов, разбиения на структурные части (чанки),
индексации в Qdrant и семантического поиска по выбранной версии документа.

## Требования
- Docker + Docker Compose
- (опционально) Git Bash / Linux terminal

## Быстрый старт

1) Создать файл окружения:
- Скопируй ``` 
infra/.env.example
``` 
в
``` infra/.env ```
- Заполни значения при необходимости

2) Запуск сервисов:
```
docker compose up --build
```
Открыть API:

Backend: ```
http://localhost:8000/
```
Qdrant Dashboard: ```
http://localhost:6333/dashboard
```

Основные эндпоинты

Список документов: ```
GET /api/documents/
```
Создать документ: ```
POST /api/documents/
```
Список версий: ```
GET /api/versions/
```
Создать версию (загрузка файла): ```
POST /api/versions/
```
Поиск: ```
GET /api/search/?q=...&version_id=...
```
Логи

Логи пишутся в:

Консоль контейнера backend

Файл: logs/backend.log (volume logs)

Примечание про кириллицу и curl (Windows/Git Bash)

Для корректной работы с русскими запросами используйте:

./scripts/search_ru.sh "обязан" 9
./scripts/search_ru.sh "ответственность" 9