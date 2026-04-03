# WORKING WITH PHASE TRUTH
## Памятка по работе с phase plans, roadmap и historical prompts

---

## Зачем нужна эта памятка

В проекте теперь есть несколько уровней документов:

- authoritative phase truth;
- архитектурные решения;
- roadmap и deferred scope;
- historical/reference prompts.

Без явных правил работы с ними легко получить:

- scope inflation;
- drift между кодом и документацией;
- реализацию “по старому prompt”, а не по текущей truth;
- потерю сильных идей или, наоборот, преждевременное протаскивание их в код.

Для `CRYPTOTEHNOLOG` это особенно критично, потому что проект ориентирован на
real-money runtime, а значит архитектурная честность важнее “широкого размаха”.

---

## Главный принцип

> Код всегда пишется по текущей authoritative truth, а не по historical prompt-архиву.

Authoritative truth определяется только через:

- `README.md`
- `prompts/plan/P_X.md`
- `prompts/plan/P_X_RESULT.md`
- `docs/adr/*.md`
- фактический код

Все остальные документы полезны, но не командуют текущей реализацией напрямую.

---

## Иерархия документов

### 1. `README.md`

Роль:

- release truth проекта;
- текущее состояние фаз;
- краткая честная фиксация implemented scope и deferred scope.

Когда читать:

- перед открытием новой фазы;
- перед финализацией;
- при проверке, не врёт ли документация о текущем состоянии проекта.

Когда менять:

- при phase closure;
- при явной нормализации release truth;
- при появлении новых package/runtime contours, которые уже вошли в release scope.

---

### 2. `prompts/plan/P_X.md`

Роль:

- authoritative phase truth;
- главный рабочий документ текущей фазы.

Что в нём должно быть:

- смысл фазы;
- стартовая truth;
- in scope;
- out of scope;
- порядок реализации;
- acceptance criteria;
- definition of done.

Когда создавать:

- обязательно перед реализацией каждой новой основной фазы.

Когда менять:

- при нормализации scope;
- при устранении document drift;
- при переходе к closure-ready truth.

Правило ссылок в рабочих отчётах и сообщениях:

- при упоминании phase-documents нужно использовать точные пути вида `prompts/plan/P_X.md` и `prompts/plan/P_X_RESULT.md`;
- нельзя сокращать их до просто `P_X.md` / `P_X_RESULT.md`, если рядом существуют historical/reference prompt-файлы с похожими именами.

---

### 3. `prompts/plan/P_X_RESULT.md`

Роль:

- closure truth завершённой фазы.

Что в нём должно быть:

- что реально реализовано;
- архитектурный summary;
- verification truth;
- follow-up lines;
- честная формулировка closure scope.

Когда создавать:

- обязательно при финализации каждой основной фазы.

---

### 4. `docs/adr/*.md`

Роль:

- архитектурные решения и ownership/source-of-truth discipline.

ADR отвечает не на вопрос “что делаем в фазе”, а на вопрос:

- почему выбран именно такой архитектурный путь;
- где живёт source of truth;
- как разделяются runtime boundaries и ownership.

Когда нужен новый ADR:

- появляется новый runtime contour;
- меняется source of truth;
- меняется ownership между слоями;
- открывается corrective path уровня архитектуры.

Когда ADR не нужен:

- обычный implementation-step внутри уже зафиксированной phase truth;
- локальный hardening без изменения архитектурной модели.

---

### 5. `docs/roadmap/*.md`

Роль:

- long-range coordination;
- сохранение идей;
- deferred scope;
- связь historical prompts с текущими и будущими фазами.

Ключевые документы:

- `MASTER_ROADMAP.md`
- `DEFERRED_SCOPE.md`
- `IDEA_REGISTRY.md`
- `PROMPT_ARCHIVE_CROSSWALK.md`
- `FUTURE_PHASE_ALLOCATION.md`
- `CODEX_MESSAGE_TEMPLATES.md`

Эти документы не являются прямой implementation truth.

---

### 6. `prompts/reference/`

Роль:

- historical/reference archive;
- source of ideas;
- long-range vision;
- материал для future phase-alignment.

Правило:

> Historical prompts нельзя использовать как прямой приказ на реализацию текущего шага без отдельной нормализации.

---

## Как теперь работать с Codex в VS Code

### Стандарт первого сообщения для новой фазы

В стартовом сообщении всегда нужно явно указывать:

1. в какой ветке работаем;
2. какая фаза открыта;
3. какие документы являются authoritative truth;
4. какие документы являются reference-only;
5. что входит в scope;
6. что не входит в scope;
7. что именно нужно сделать на текущем шаге;
8. что делать запрещено.

Если этого не сделать, Codex почти неизбежно начнёт тянуть scope из historical prompts.

---

### Стандарт шага внутри фазы

Каждый шаг должен быть узким.

Сначала формулируется:

- текущий подэтап;
- его цель;
- что считается хорошим результатом;
- что запрещено делать на этом шаге.

Только потом идёт реализация.

---

### Стандарт review / audit шага

Если делаем review:

- Codex не пишет новый код автоматически;
- сначала выдаёт findings;
- только потом принимается решение, нужен ли corrective step.

Это особенно важно перед финализацией фаз.

---

## Как работать с новыми идеями

Если в ходе работы появляется идея, нужно сразу решить, к какой категории она относится.

### Вариант A. Это часть текущей фазы

Тогда идея должна попасть в:

- `P_X.md`
- код
- при необходимости в ADR

### Вариант B. Это полезно, но не входит в текущую фазу

Тогда идея должна попасть в:

- `docs/roadmap/DEFERRED_SCOPE.md`

### Вариант C. Это сильная идея, но ещё рано раскладывать по фазам

Тогда идея должна попасть в:

- `docs/roadmap/IDEA_REGISTRY.md`

Главное правило:

> Идея не должна оставаться только “в чате”, “в голове” или “в старом prompt”.

---

## Как открывать новую фазу

Для каждой новой основной фазы нужен обязательный порядок:

### Шаг 1. Alignment

Сверяем:

- `README.md`
- relevant `P_(X-1).md` и `P_(X-1)_RESULT.md`
- relevant ADR
- relevant roadmap/deferred docs
- historical prompts только как reference
- фактический код

### Шаг 2. Новый `P_X.md`

Формулируем:

- цель фазы;
- scope;
- anti-scope guards;
- acceptance criteria;
- definition of done.

### Шаг 3. Реализация

Идём только после зафиксированного phase plan.

---

## Как закрывать фазу

Closure фазы всегда идёт в таком порядке:

1. hardening / phase review;
2. verification;
3. нормализация docs/release truth;
4. `P_X_RESULT.md`;
5. финализация release.

Нельзя честно закрывать фазу, если:

- код и docs расходятся;
- verification не зелёная;
- closure scope не зафиксирован;
- из parallel tracks могут подмешаться посторонние изменения.

### Что обязательно должно существовать до финализации

Для основной фазы до closure должны существовать:

- `prompts/plan/P_X.md`
- фактическая кодовая реализация фазы
- при необходимости relevant ADR
- зелёный или честно интерпретируемый verification subset

Для formal closure обязательно должны появиться:

- `prompts/plan/P_X_RESULT.md`
- release/doc truth в `README.md`

### Как отличать blocker от residual risk

**Blocker** — это то, что мешает честно закрыть фазу.

Примеры:

- незелёный critical verification subset;
- отсутствующий production source of truth;
- release/doc drift;
- скрытый runtime contract mismatch.

**Residual risk** — это то, что желательно улучшить, но что не делает closure dishonest.

Примеры:

- отсутствие дополнительного e2e сценария, если текущий closure scope уже честно покрыт;
- неблокирующий warning тестовой среды;
- будущая hardening line, явно вынесенная из фазы.

### Проверка рабочего дерева перед release

Перед релизными git-действиями обязательно проверяется:

- `git status`
- staged / unstaged changes
- untracked files
- наличие parallel-track изменений

Если есть посторонние изменения:

- их нужно явно показать;
- не включать в фазовый релиз без отдельного решения.

### Formal finalization

Только после review, verification и doc normalization можно:

1. сделать релизный commit;
2. создать tag;
3. выполнить merge;
4. сделать push.

Если на любом git-шаге возникает проблема, её нельзя исправлять молча.

### Правило версионирования фаз

Для основных фаз используется простое правило:

- закрытие основной фазы `P_X` соответствует версии `v1.X.0`

Примеры:

- `P_7` → `v1.7.0`
- `P_8` → `v1.8.0`
- `P_9` → `v1.9.0`
- `P_10` → `v1.10.0`
- `P_11` → `v1.11.0`

Patch-версии используются только для уже закрытой основной фазы:

- `v1.X.1`
- `v1.X.2`
- `v1.X.3`

Они допустимы только для:

- hotfix;
- corrective release;
- post-release CI / formatting / infra fix;
- иных узких patch-изменений без открытия новой основной фазы.

Нельзя использовать patch-версии вместо новой основной фазы.

Например:

- `P_11` не может быть оформлена как `v1.10.1`
- `P_12` не может быть оформлена как `v1.10.2`

Major version jump (`v2.0.0`) не делается автоматически при переходе к следующей фазе.
Он допустим только если для этого отдельно зафиксирована новая versioning policy.

### Post-release fix

Если после релиза падает:

- formatter;
- CI-only lint check;
- иной узкий non-scope post-release technical check;

и при этом логика release scope не меняется,
допускается отдельный post-release hotfix.

Правило:

- hotfix должен быть узким;
- не должен расширять release scope;
- должен явно формулироваться как post-release fix.

---

## Что считать parallel tracks

Parallel track — это линия, которая:

- живёт рядом с основными фазами;
- может быть полезной;
- но не должна автоматически попадать в текущий release.

Для текущего проекта таким track уже является:

- dashboard line

Правило:

> Parallel track всегда должен быть явно исключён из phase release, если отдельно не принято другое решение.

---

## Branch / Workstream Truth

Branch/workstream truth нужна только для coordination clarity.

Она не заменяет:

- authoritative phase truth;
- release truth;
- roadmap truth;
- architectural truth.

Текущая рабочая branch/workstream схема проекта:

- `master` — mainline truth branch;
- `terminal-ui` — активная UI/workstream ветка;
- `connector/bybit-market-data` — отдельная рабочая ветка узкого connector slice;
- `dashboard-foundation` — историческая/архивная ветка, уже поглощённая `terminal-ui`.

Что это означает practically:

- наличие открытой ветки само по себе не открывает новую фазу;
- наличие отдельного workstream не делает его автоматически authoritative phase truth;
- historical/supporting/connector ветки не должны автоматически трактоваться как committed roadmap line;
- merge/release decisions по этим веткам принимаются отдельно и не выводятся только из факта их существования.

Phase truth по-прежнему определяется только через:

- `README.md`;
- `prompts/plan/P_X.md`;
- `prompts/plan/P_X_RESULT.md`;
- `docs/adr/*.md`;
- фактический код.

Правило чтения веток:

- `master` читается как mainline integration/release branch;
- `terminal-ui` читается как текущая активная UI/control-surface линия;
- `connector/bybit-market-data` читается как отдельный рабочий connector track;
- `dashboard-foundation` читается как архивная историческая ветка, а не как текущий supporting track;
- ни одна из этих веток не должна сама по себе подменять authoritative docs.

Если branch reality и phase docs расходятся, выигрывает phase truth, а branch/workstream
состояние должно описываться как operational/coordination context, а не как новая
implementation truth.

---

## Как не потерять идеи и не сломать проект

Неправильный путь:

- держать все prompts как одинаково обязательные;
- реализовывать “всё важное сразу”;
- смешивать foundation и future consumers.

Правильный путь:

- хранить все prompts;
- хранить все идеи;
- но давать право командовать кодом только текущей phase truth.

Это и есть рабочая модель для money-critical системы.

---

## Краткий operating model

### Когда пишем код

Ориентируемся только на:

- phase plan;
- ADR;
- README;
- фактический код.

### Когда ищем future ideas

Смотрим в:

- `prompts/reference/`
- `DEFERRED_SCOPE.md`
- `IDEA_REGISTRY.md`
- `PROMPT_ARCHIVE_CROSSWALK.md`
- `FUTURE_PHASE_ALLOCATION.md`

### Когда формулируем рабочие сообщения для Codex

Базовые шаблоны берём из:

- `CODEX_MESSAGE_TEMPLATES.md`

### Когда переносим scope

Фиксируем перенос в:

- `README.md` кратко;
- `DEFERRED_SCOPE.md` подробно.

### Когда открываем новую фазу

Сначала alignment, потом новый `P_X.md`, потом реализация.

### Когда закрываем фазу

Сначала review и verification, потом docs/result, потом release.

---

## Итог

Эта схема нужна не ради документации как таковой.
Она нужна, чтобы проект:

- не терял сильные идеи;
- не тащил в код несозревшие подсистемы;
- не врал в release truth;
- оставался управляемым как real-money engineering system.
