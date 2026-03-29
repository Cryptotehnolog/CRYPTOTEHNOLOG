# PROMPTS
## Как использовать prompt-документы в проекте

---

## Главный принцип

В этой директории есть документы с разной ролью.

Они **не равны по статусу**.

Текущая implementation truth определяется не любым prompt-файлом, а только
через authoritative phase documents.

---

## Какие prompt-документы являются authoritative

Authoritative truth для текущей или закрытой фазы живёт только в:

- `prompts/plan/P_X.md`
- `prompts/plan/P_X_RESULT.md`

Именно эти документы используются:

- для открытия новой фазы;
- для реализации;
- для review;
- для финализации и release truth.

---

## Что находится в корне `prompts/`

Файлы вида:

- `02_ФАЗА_1_...`
- `03_ФАЗА_2_...`
- `08_ФАЗА_7_...`
- `09_ФАЗА_8_...`

нужно считать в первую очередь **historical/reference prompt-документами**,
если только их содержимое не было отдельно нормализовано в актуальный
`prompts/plan/P_X.md`.

Иными словами:

> Наличие старого большого prompt-файла в корне `prompts/` не означает, что он является текущей implementation truth.

---

## Как работать с historical prompts

Historical prompts полезны как:

- источник идей;
- материал для phase-alignment;
- long-range vision;
- источник deferred scope.

Но они не должны:

- напрямую диктовать реализацию текущего шага;
- конфликтовать с `README.md`;
- подменять `prompts/plan/P_X.md`;
- навязывать scope текущей фазы.

---

## Рекомендуемый порядок работы

### Если открывается новая фаза

Сначала читать:

- `README.md`
- relevant ADR
- `prompts/plan/P_X.md` (или подготовить новый)
- relevant `P_(X-1)_RESULT.md`

Только потом:

- historical prompts из корня `prompts/`
- `prompts/reference/`

### Если идёт реализация внутри фазы

Ориентироваться только на:

- `README.md`
- текущий `prompts/plan/P_X.md`
- relevant ADR
- фактический код

### Если нужна идея на будущее

Смотреть в:

- `docs/roadmap/DEFERRED_SCOPE.md`
- `docs/roadmap/IDEA_REGISTRY.md`
- `docs/roadmap/PROMPT_ARCHIVE_CROSSWALK.md`
- `prompts/reference/`

---

## Связанные документы

- Главная рабочая памятка: [WORKING_WITH_PHASE_TRUTH.md](/D:/CRYPTOTEHNOLOG/docs/roadmap/WORKING_WITH_PHASE_TRUTH.md)
- Общая схема truth-слоёв: [MASTER_ROADMAP.md](/D:/CRYPTOTEHNOLOG/docs/roadmap/MASTER_ROADMAP.md)
- Реестр вынесенного scope: [DEFERRED_SCOPE.md](/D:/CRYPTOTEHNOLOG/docs/roadmap/DEFERRED_SCOPE.md)
- Связка historical prompts с roadmap: [PROMPT_ARCHIVE_CROSSWALK.md](/D:/CRYPTOTEHNOLOG/docs/roadmap/PROMPT_ARCHIVE_CROSSWALK.md)

