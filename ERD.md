# ERD

## Назначение

Этот файл фиксирует **целевую ER-модель MVP**.

Важно: это не только снимок текущего кода из архива, а **модель данных, к которой должен прийти MVP**. Поэтому некоторые поля здесь описаны как целевые, даже если в текущем backend они ещё не полностью реализованы.

## Ключевая логика данных

- один документ имеет много версий;
- каждая версия разбивается на структурные фрагменты;
- сравнение выполняется между двумя версиями одного документа;
- по результатам сравнения генерируется тест;
- тест проходит сотрудник;
- результат попытки хранится и участвует в отчётности.

## Mermaid ER Diagram

```mermaid
erDiagram
    DOCUMENT ||--o{ DOCUMENT_VERSION : has
    DOCUMENT_VERSION ||--o{ CHUNK : split_into
    DOCUMENT_VERSION ||--o{ GENERATED_QUIZ : from_version
    DOCUMENT_VERSION ||--o{ GENERATED_QUIZ : to_version
    GENERATED_QUIZ ||--o{ QUIZ_ATTEMPT : has

    DOCUMENT {
        bigint id PK
        string title
        text description
        datetime created_at
        datetime updated_at
    }

    DOCUMENT_VERSION {
        bigint id PK
        bigint document_id FK
        int version_number
        string source_filename
        string file_path
        text extracted_text
        text normalized_text
        string content_hash
        datetime created_at
    }

    CHUNK {
        bigint id PK
        bigint version_id FK
        int chunk_index
        string heading
        string section_path
        text text
        string text_hash
        int token_count
        datetime created_at
    }

    GENERATED_QUIZ {
        bigint id PK
        bigint from_version_id FK
        bigint to_version_id FK
        string title
        json payload
        int questions_count
        string status
        string approved_by_name
        datetime approved_at
        text approval_comment
        datetime created_at
    }

    QUIZ_ATTEMPT {
        bigint id PK
        bigint quiz_id FK
        string participant_name
        json answers
        int score
        int total_questions
        datetime created_at
    }