# Dashboard positions: projection на Главной, master-table в /terminal/positions и read-only facade truth

**Дата:** 2026-03-31  
**Статус:** Принято  

## Контекст
После серии изменений в `dashboard`/`terminal` positions stack проект пришёл к устойчивой модели, которую нужно зафиксировать архитектурно, а не только в README.

Для positions surfaces теперь одновременно существуют два разных operator-facing представления:
- `Главная` (`/terminal`) как компактная пользовательская projection открытых позиций и истории позиций;
- full page `/terminal/positions` как canonical master-table для тех же сущностей.

Без явной фиксации эта граница легко размывается:
- full page начинает вести себя как ещё один widget, а не как canonical table;
- `Главная` начинает не просто проецировать truth, а жить по собственной ad hoc модели колонок и данных;
- UI получает соблазн фейкать поля, которых ещё нет в canonical backend truth path;
- dev/test verification через seeded runtime можно случайно превратить в production-like behavior.

Дополнительно в positions path были канонически surfaced новые truth fields:
- для `Открытых позиций`: `strategy`, `current_price`, `unrealized_pnl_usd`, `unrealized_pnl_percent`;
- для `Истории позиций`: `strategy`, `realized_pnl_r`, `realized_pnl_usd`, `realized_pnl_percent`.

Это решение нужно зафиксировать как boundary-правило для дальнейших changes в positions UI и dashboard facade.

## Рассмотренные альтернативы
1. Оставить текущее поведение только как неформальную договорённость в UI-коде и README.
2. Считать `Главную` и `/terminal/positions` равноправными table surfaces без явного разделения `projection` и `master-table`.
3. Разрешить UI/dashboard добавлять поля и secondary presentation через локальные fallback/computed values, даже если canonical truth path ещё не расширен.
4. Зафиксировать архитектурную границу: `Главная` = пользовательская projection, `/terminal/positions` = canonical master-table, `dashboard` = read-only facade, новые fields допускаются только через canonical source layers end-to-end.

## Решение
Принят вариант 4.

### 1. Главная как пользовательская projection
- `Главная` (`/terminal`) не является authoritative table surface.
- Она показывает компактные projections открытых позиций и истории позиций, ориентированные на пользовательский выбор колонок и порядок колонок.
- Пользовательская projection может:
  - выбирать subset доступных колонок;
  - хранить локальный persistence порядка/состава колонок;
  - отличаться плотностью и layout от full page.
- Пользовательская projection не может создавать собственные truth fields вне canonical backend surface.

### 2. /terminal/positions как canonical master-table
- Full page `/terminal/positions` зафиксирована как canonical master-table для:
  - `Открытых позиций`;
  - `Истории позиций`.
- Именно эта surface определяет:
  - полный актуальный список доступных колонок;
  - canonical column semantics для terminal positions UI;
  - master-level table interaction model.
- Настройки `Главной` считаются projection поверх canonical columns, а не отдельной независимой table model.

### 3. Dashboard как read-only facade
- `dashboard` не является самостоятельным domain source-of-truth для positions.
- `dashboard` обязан оставаться read-only facade над canonical backend truths:
  - risk open-position truth;
  - risk history truth;
  - persistence/history records;
  - facade snapshots и DTO.
- `dashboard` не должен:
  - придумывать поля, которых нет в canonical path;
  - вычислять ad hoc значения только ради UI;
  - маскировать отсутствие truth красивым fallback-поведением.

### 4. Canonical surfaced fields в Открытых позициях
В current canonical open positions path surfaced и доступны для terminal UI:
- `position_id`
- `symbol`
- `exchange`
- `strategy`
- `side`
- `entry_price`
- `quantity`
- `initial_stop`
- `current_stop`
- `current_risk_usd`
- `current_risk_r`
- `current_price`
- `unrealized_pnl_usd`
- `unrealized_pnl_percent`
- `trailing_state`
- `opened_at`
- `updated_at`

Эти поля проходят end-to-end через:
- risk open-position truth;
- dashboard facade snapshots;
- dashboard DTO;
- frontend response/types;
- terminal tables.

### 5. Canonical surfaced fields в Истории позиций
В current canonical position history path surfaced и доступны для terminal UI:
- `position_id`
- `symbol`
- `exchange`
- `strategy`
- `side`
- `entry_price`
- `quantity`
- `initial_stop`
- `current_stop`
- `trailing_state`
- `opened_at`
- `closed_at`
- `realized_pnl_r`
- `realized_pnl_usd`
- `realized_pnl_percent`

Эти поля проходят end-to-end через:
- `POSITION_CLOSED` / risk history foundation;
- persistence;
- dashboard facade snapshots;
- dashboard DTO;
- frontend response/types;
- terminal tables.

### 6. Seeded runtime только для dev/test verification
- Env flag `CRYPTOTEHNOLOG_DASHBOARD_DEV_SEED=positions` фиксируется как controlled dev/test path.
- Этот path нужен для:
  - визуальной проверки widgets и full page tables;
  - regression check по positions UI;
  - проверки search/filter/sort/actions/column projection на реальных seeded rows.
- Seeded runtime не является production feature и не меняет normal path без явного env flag.

### 7. Правило дальнейшего расширения positions fields
Любое новое positions/history field может появиться в UI только если оно:
1. имеет canonical source-of-truth;
2. протянуто через backend source layers;
3. surfaced в dashboard facade snapshot/DTO path;
4. после этого добавлено во frontend types и UI.

Если поля нет в canonical path, UI обязан:
- не фейкать его;
- не подменять отсутствующее truth псевдозначением;
- либо не показывать поле, либо явно работать через neutral/fallback presentation без имитации новых данных.

## Последствия
- **Плюсы:** граница между compact projection и canonical master-table становится однозначной; снижается риск расхождения `Главной` и full page; positions UI расширяется только через честный backend truth path; seeded runtime остаётся контролируемым dev/test механизмом.
- **Плюсы:** README и terminal UI теперь опираются на одно и то же архитектурное правило, а не на неформальную договорённость.
- **Минусы:** любые новые поля для positions/history требуют end-to-end расширения canonical path и не могут быть быстро “добавлены только в UI”.
- **Минусы:** full page и `Главная` нельзя развивать как две независимые table-системы без соблюдения зафиксированной boundary-модели.

## Связанные ADR
- Связан с `0021-risk-ledger-source-of-truth.md`
- Связан с `0024-production-alignment-composition-root-and-runtime-truth.md`
