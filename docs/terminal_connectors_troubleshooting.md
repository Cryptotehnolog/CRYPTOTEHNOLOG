# Local Terminal Connectors Troubleshooting

Короткий runbook для локальной диагностики страницы `http://127.0.0.1:5173/terminal/connectors`.

## Primary Fetch Paths

Frontend terminal/connectors ходит в backend на `http://127.0.0.1:8000`.

Текущие primary endpoints:

- spot block:
  - `GET /dashboard/settings/bybit-spot-product-snapshot`
  - `GET /dashboard/settings/bybit-spot-connector-diagnostics`
- futures block:
  - `GET /dashboard/settings/bybit-connector-diagnostics`

`GET /dashboard/settings/bybit-spot-runtime-status` полезен для ручной диагностики spot runtime, но не является primary fetch path текущего spot block. Текущий spot UI живёт от `bybit-spot-product-snapshot`.

## Minimal Local Check Order

Порядок проверки должен быть именно таким:

1. Проверить listener на `127.0.0.1:8000`.
2. Проверить `200` от:
   - `/dashboard/settings/bybit-spot-product-snapshot`
   - `/dashboard/settings/bybit-spot-connector-diagnostics`
   - `/dashboard/settings/bybit-connector-diagnostics`
3. Сделать hard reload страницы `terminal/connectors`.
4. Только после этого решать, есть ли реальная regression в connector semantics.

Рекомендуемая минимальная ручная проверка:

```powershell
netstat -ano | findstr ":8000"
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/dashboard/settings/bybit-spot-product-snapshot | Select-Object -ExpandProperty StatusCode
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/dashboard/settings/bybit-spot-connector-diagnostics | Select-Object -ExpandProperty StatusCode
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/dashboard/settings/bybit-connector-diagnostics | Select-Object -ExpandProperty StatusCode
```

То же самое можно выполнить одной командой:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev\check_terminal_connectors_backend.ps1
```

## Typical False Alarms

Типовые ложные тревоги, которые нельзя путать с regression в connector logic:

- `connection refused` на spot/futures endpoints:
  - это dead backend path;
  - это не bug в spot/futures semantics.
- Красный UI после того, как backend уже поднят:
  - это может быть stale browser state;
  - сначала сделать hard reload и заново снять network.
- Futures payload с `transport_status = disconnected` или `lifecycle_state = built` при `HTTP 200`:
  - это не request failure;
  - это нормальный diagnostics payload с нерабочим runtime state.
- Различие counts между runtime и product snapshot:
  - само по себе не равно bug;
  - сначала нужно проверить `screen_scope_reason`, `contract_flags` и actual `instrument_rows`.

## E2E Harness Caveats

Для `dashboard-frontend/tests/e2e/terminal-connectors.spec.ts`:

- Playwright harness требует свободный `127.0.0.1:8000`, потому что `playwright.config.ts` поднимает свой backend webServer.
- Если `8000` уже занят, сначала освободить порт или не запускать параллельный backend вручную.
- Child process spawn для Playwright/webServer может упираться в sandbox restrictions.
- Если e2e не стартует с `spawn EPERM` или похожей ошибкой:
  - сначала проверять harness/process permissions;
  - не делать вывод, что сломана UI semantics.

## Interpretation Rules

Не переходить к разбору:

- `false-empty snapshot`
- `runtime vs product mismatch`
- `trade_count_24h semantics`
- `pending_archive / fallback / published scope`

пока не подтверждено одновременно:

- backend слушает `8000`;
- spot endpoints отвечают `200`;
- futures diagnostics endpoint отвечает `200`;
- terminal page после hard reload действительно всё ещё показывает проблему.
