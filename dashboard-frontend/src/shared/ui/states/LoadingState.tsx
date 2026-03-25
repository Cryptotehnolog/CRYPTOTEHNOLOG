import { stateCaption, stateCard, stateText, stateTitle } from "./StateCard.css";

type LoadingStateProps = {
  title?: string;
  caption?: string;
  message?: string;
};

export function LoadingState({
  title = "Загрузка обзора",
  caption = "Панель подключается к локальному runtime и собирает снимок платформы в режиме только чтения.",
  message = "Панель запрашивает снимок состояния платформы из серверного контура управления.",
}: LoadingStateProps) {
  return (
    <div className={stateCard}>
      <h2 className={stateTitle}>{title}</h2>
      <p className={stateCaption}>{caption}</p>
      <p className={stateText}>{message}</p>
    </div>
  );
}
