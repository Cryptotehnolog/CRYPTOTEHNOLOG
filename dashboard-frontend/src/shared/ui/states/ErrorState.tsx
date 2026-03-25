import { stateCaption, stateCard, stateText, stateTitle } from "./StateCard.css";

type ErrorStateProps = {
  message: string;
  title?: string;
  caption?: string;
};

export function ErrorState({
  message,
  title = "Ошибка загрузки панели",
  caption = "Панель остаётся поддерживающей поверхностью только для чтения и ожидает корректный ответ серверного контура.",
}: ErrorStateProps) {
  return (
    <div className={stateCard}>
      <h2 className={stateTitle}>{title}</h2>
      <p className={stateCaption}>{caption}</p>
      <p className={stateText}>{message}</p>
    </div>
  );
}
