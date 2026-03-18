import { stateCard, stateText, stateTitle } from "./StateCard.css";

export function LoadingState() {
  return (
    <div className={stateCard}>
      <h2 className={stateTitle}>Загрузка обзора</h2>
      <p className={stateText}>
        Панель запрашивает снимок состояния платформы из backend панели управления.
      </p>
    </div>
  );
}
