# REFERENCE PROMPTS
## Historical and Roadmap Prompt Archive

---

## Назначение

Эта директория хранит reference-only prompt-документы.

Они нужны как:

- исторический архив;
- источник сильных идей;
- long-range vision;
- материал для будущей нормализации фаз.

Они **не** являются authoritative truth для текущей реализации.

---

## Правило использования

Текущая implementation truth определяется только через:

- `README.md`
- `prompts/plan/P_X.md`
- `prompts/plan/P_X_RESULT.md`
- `docs/adr/*.md`
- фактический код

Reference prompts можно использовать:

- для phase-alignment перед открытием новой фазы;
- для извлечения deferred scope;
- для roadmap planning.

Но их нельзя использовать как прямую команду на реализацию текущего шага без отдельной нормализации.

---

## Структура

- `russian_archive/` — архив исходных русскоязычных prompt-документов из внешней папки `D:\План с промтами_Русский`

Архив дополнительно связан с roadmap-слоем через:

- `docs/roadmap/PROMPT_ARCHIVE_CROSSWALK.md`
- `docs/roadmap/DEFERRED_SCOPE.md`

---

## Текущий статус

Архив сохранён в репозитории именно для того, чтобы:

- не потерять идеи;
- не дублировать их в памяти или чатах;
- но при этом не разрушать phase discipline текущей реализации.
