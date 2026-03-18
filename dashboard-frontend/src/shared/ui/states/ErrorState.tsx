import { stateCard, stateText, stateTitle } from "./StateCard.css";

type ErrorStateProps = {
  message: string;
};

export function ErrorState({ message }: ErrorStateProps) {
  return (
    <div className={stateCard}>
      <h2 className={stateTitle}>Ошибка загрузки панели</h2>
      <p className={stateText}>{message}</p>
    </div>
  );
}
