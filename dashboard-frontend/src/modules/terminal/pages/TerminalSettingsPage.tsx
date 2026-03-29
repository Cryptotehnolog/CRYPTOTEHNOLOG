import { TerminalBadge } from "../components/TerminalBadge";
import { useTerminalUiStore } from "../state/useTerminalUiStore";
import { useTerminalWidgetStore } from "../state/useTerminalWidgetStore";
import {
  exchangeCard,
  exchangeGrid,
  exchangeMeta,
  exchangeRow,
  exchangeToggle,
  localStateNote,
  modeButton,
  modeButtonActive,
  modeControls,
  pageRoot,
  sectionBody,
  sectionCaption,
  sectionHeader,
  sectionTitle,
  settingsCard,
  stateValue,
  widgetSettingsCard,
  widgetSettingsGrid,
  widgetSettingsMeta,
  widgetSettingsRow,
  widgetVisibilityCheckbox,
  widgetVisibilityControl,
} from "./TerminalSettingsPage.css";

export function TerminalSettingsPage() {
  const mode = useTerminalUiStore((state) => state.mode);
  const exchanges = useTerminalUiStore((state) => state.exchanges);
  const setMode = useTerminalUiStore((state) => state.setMode);
  const setExchangeConnected = useTerminalUiStore((state) => state.setExchangeConnected);
  const widgets = useTerminalWidgetStore((state) => state.widgets);
  const setWidgetVisible = useTerminalWidgetStore((state) => state.setWidgetVisible);

  return (
    <div className={pageRoot}>
      <section className={settingsCard}>
        <div className={sectionHeader}>
          <div>
            <div className={sectionCaption}>Режим работы</div>
            <h1 className={sectionTitle}>Управление режимом терминала</h1>
          </div>
          <TerminalBadge tone="neutral">
            {mode === "manual" ? "Ручной режим" : "Авто режим"}
          </TerminalBadge>
        </div>

        <div className={sectionBody}>
          <div className={stateValue}>
            Сейчас выбран: {mode === "manual" ? "Ручной режим" : "Авто режим"}
          </div>
          <div className={modeControls}>
            <button
              type="button"
              className={`${modeButton} ${mode === "manual" ? modeButtonActive : ""}`}
              onClick={() => setMode("manual")}
            >
              Ручной режим
            </button>
            <button
              type="button"
              className={`${modeButton} ${mode === "auto" ? modeButtonActive : ""}`}
              onClick={() => setMode("auto")}
            >
              Авто режим
            </button>
          </div>
          <div className={localStateNote}>
            Локальное terminal-состояние для UX-отработки. Production backend action на этом шаге
            не подключался.
          </div>
        </div>
      </section>

      <section className={settingsCard}>
        <div className={sectionHeader}>
          <div>
            <div className={sectionCaption}>Биржи</div>
            <h2 className={sectionTitle}>Подключение торговых контуров</h2>
          </div>
          <TerminalBadge tone="accent">{exchanges.length} биржи</TerminalBadge>
        </div>

        <div className={exchangeGrid}>
          {exchanges.map((exchange) => (
            <div key={exchange.name} className={exchangeCard}>
              <div className={exchangeRow}>
                <div>
                  <div className={stateValue}>{exchange.name}</div>
                  <div className={exchangeMeta}>
                    {exchange.connected ? "Подключена" : "Отключена"} · {exchange.ping}
                  </div>
                </div>
                <button
                  type="button"
                  className={exchangeToggle}
                  onClick={() => setExchangeConnected(exchange.name, !exchange.connected)}
                >
                  {exchange.connected ? "Отключить" : "Подключить"}
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className={localStateNote}>
          Переключатели пока управляют только terminal UI state и не маскируются под реальную
          backend-команду подключения бирж.
        </div>
      </section>

      <section className={settingsCard}>
        <div className={sectionHeader}>
          <div>
            <div className={sectionCaption}>Виджеты</div>
            <h2 className={sectionTitle}>Состав рабочей области</h2>
          </div>
          <TerminalBadge tone="neutral">
            {widgets.filter((widget) => widget.visible).length} активны
          </TerminalBadge>
        </div>

        <div className={widgetSettingsGrid}>
          {widgets.map((widget) => (
            <div key={widget.id} className={widgetSettingsCard}>
              <div className={widgetSettingsRow}>
                <div>
                  <div className={stateValue}>{widget.title}</div>
                  <div className={widgetSettingsMeta}>
                    {widget.visible ? "Показывается на главной" : "Скрыт с главной"} · {widget.layout.w}×
                    {widget.layout.h}
                  </div>
                </div>

                <label className={widgetVisibilityControl}>
                  <input
                    type="checkbox"
                    className={widgetVisibilityCheckbox}
                    checked={widget.visible}
                    onChange={(event) => setWidgetVisible(widget.id, event.target.checked)}
                  />
                  <span>{widget.visible ? "Включен" : "Выключен"}</span>
                </label>
              </div>
            </div>
          ))}
        </div>

        <div className={localStateNote}>
          Видимость, позиции и размеры widget-area сохраняются локально и сразу синхронизируются
          между главной страницей терминала и настройками.
        </div>
      </section>
    </div>
  );
}
