# MASTER ROADMAP
## Canonical Roadmap and Truth Hierarchy

---

## Назначение

Этот документ фиксирует лучшую схему хранения проектных идей, фазовых планов и
исторических prompt-документов для `CRYPTOTEHNOLOG`.

Цель схемы:

- не потерять ни одну сильную идею;
- не смешивать текущую phase truth с дальним roadmap;
- не допускать scope inflation в money-critical runtime;
- сохранять жёсткую release truth для каждой реализуемой фазы.

---

## Иерархия истины

### 1. Authoritative Truth

Это единственный уровень, по которому можно:

- писать код;
- открывать и закрывать фазы;
- выпускать релизы;
- принимать архитектурные решения.

Сюда входят:

- `README.md`
- `prompts/plan/P_X.md`
- `prompts/plan/P_X_RESULT.md`
- `docs/adr/*.md`
- фактический код в `src/cryptotechnolog`

Правило:

> Если historical prompt, roadmap-идея или старое описание конфликтуют с этим уровнем, выигрывает authoritative truth.

---

### 2. Strategic Roadmap

Это уровень долгосрочного продуктово-архитектурного развития.

Он нужен для:

- сохранения дальнего vision;
- планирования будущих линий;
- накопления сильных идей без давления на текущую фазу.

Сюда входят:

- `docs/roadmap/MASTER_ROADMAP.md`
- `docs/roadmap/DEFERRED_SCOPE.md`
- `docs/roadmap/IDEA_REGISTRY.md`

Правило:

> Roadmap-документы не являются прямой инструкцией на реализацию текущего шага.

---

### 3. Historical / Reference Prompts

Это исторические prompt-документы, включая широкие phase-prompts и дальние
архитектурные наброски.

Для репозитория они сохраняются как:

- `prompts/reference/russian_archive/*`

А также как существующие исторические prompt-файлы в `prompts/`, если они уже
участвуют в истории проекта.

Правило:

> Historical prompts используются как reference и source of ideas, но не как текущая truth для реализации.

---

## Текущая структура ролей

### `prompts/plan/`

Содержит только:

- authoritative phase plans;
- authoritative phase result / closure documents.

Примеры:

- `P_7.md`
- `P_7_RESULT.md`
- `P_8.md`
- `P_8_RESULT.md`

---

### `prompts/reference/russian_archive/`

Содержит:

- архив исходных русскоязычных prompt-документов;
- long-range prompts;
- historical drafts;
- reference-only phase materials.

Это архивная зона, а не источник текущей phase truth.

---

### `docs/roadmap/`

Содержит:

- текущую схему управления roadmap;
- реестр вынесенного scope;
- реестр идей и будущих линий.

---

## Правила работы с новыми идеями

Если идея:

### 1. Вошла в текущую фазу

Она должна быть отражена в:

- `prompts/plan/P_X.md`
- коде
- при closure — в `P_X_RESULT.md`
- при необходимости — в `README.md`

### 2. Не вошла в текущую фазу, но признана полезной

Она должна быть отражена в:

- `docs/roadmap/DEFERRED_SCOPE.md`

### 3. Ещё не разложена по фазам, но ценна как будущее направление

Она должна быть отражена в:

- `docs/roadmap/IDEA_REGISTRY.md`

Правило:

> Ни одна сильная идея не должна оставаться только “в старом prompt” или “в голове”.

---

## Правила открытия новых фаз

Перед открытием новой фазы:

1. сверяется текущий код;
2. сверяется `README.md`;
3. сверяются relevant ADR;
4. historical prompts используются только как reference;
5. создаётся новый authoritative `prompts/plan/P_X.md`.

Это обязательная процедура для money-critical проекта.

---

## Почему эта схема выбрана

Для проекта, который должен работать с реальными деньгами, опасны не только
ошибки в коде, но и ошибки в управлении scope:

- premature orchestration;
- смешение ownership между слоями;
- реализация будущих идей как будто они уже подтверждены;
- release truth, расходящаяся с кодом.

Эта схема нужна, чтобы:

- vision не терялось;
- текущая реализация не расплывалась;
- каждая фаза закрывалась честно;
- архитектура росла последовательно, а не скачками.

---

## Текущий статус

- `P_7` закрыта как `v1.7.0`
- `P_8` закрыта как `v1.8.0`
- `P_9` закрыта как `v1.9.0`
- sequencing ближайших будущих фаз нормализован так:
  - `P_10` — `Execution Foundation`
  - `P_11` — `Opportunity / Selection Foundation`
  - `P_12` — `Strategy Orchestration / Meta Layer`
- дальнейшие идеи и широкие prompt-линии должны использоваться через roadmap / deferred registry / reference archive, а не как текущая implementation truth
