import { stateCaption, stateCard, stateText, stateTitle } from "./StateCard.css";

type ErrorStateProps = {
  message: string;
};

export function ErrorState({ message }: ErrorStateProps) {
  return (
    <div className={stateCard}>
      <h2 className={stateTitle}>Ошибка загрузки панели</h2>
      <p className={stateCaption}>
        Обзор остаётся read-only supporting surface и ожидает корректный ответ от backend path.
      </p>
      <p className={stateText}>{message}</p>
    </div>
  );
}
