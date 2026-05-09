# Final Thesis Risk Register

| Риск | Вероятность | Влияние | Как снизить |
|---|---|---|---|
| Недостаточно внешних источников | medium | high | Подобрать реальные источники по `bibliography-gap-analysis.md`; не выдумывать библиографию. |
| Нумерация рисунков и таблиц не финальная | high | medium | Выполнить финальную нумерацию после сборки DOCX/PDF; проверить все ссылки в тексте. |
| Synthetic corpus может вызвать вопросы | medium | medium | Честно описать ограничения, key-change annotation и planned future work; подчеркнуть MVP nature. |
| Quiz generation не идеален | medium | medium | Подчеркнуть baseline nature, correct/relevant question rate и обязательный human-in-the-loop approval. |
| Слишком сильные утверждения о применимости метода | medium | high | Использовать cautious claims: «на подготовленном corpus», «в рамках MVP», «поддерживает, но не заменяет эксперта». |
| Недостаточное обоснование local-first scope | low | medium | Сослаться на PROJECT_SCOPE, mvp-freeze и требования воспроизводимости; не заявлять enterprise deployment. |
| Смешение LLM с ядром метода | medium | medium | В тексте и презентации указывать: optional/fallback AI layer, deterministic/rule-based/hybrid pipeline как ядро. |
| Неполная проверка runtime-мусора в архиве | medium | medium | Проверить `git status --short`, `.gitignore`, `db.sqlite3`, `media/`, `uploads/`, `*.log`, `__pycache__/`, `.pytest_cache/`. |
| Ошибки при переносе метрик в финальную верстку | medium | high | Сверять таблицы с experiment artifacts; не пересчитывать и не «улучшать» значения вручную. |
| Несогласованность объекта/предмета/цели после правок | low | high | Перед сдачей сверить введение, главу 1 и заключение; согласовать с научным руководителем. |
| Отсутствие финального списка приложений | medium | medium | Заранее решить, какие схемы, таблицы и фрагменты corpus включать в приложения. |
| Антиплагиат выявит длинные совпадения из шаблонных описаний | medium | medium | Проверить оригинальность, корректно оформить источники и переформулировать шаблонные места собственным языком. |
