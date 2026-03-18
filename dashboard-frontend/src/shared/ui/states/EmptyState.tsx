import { stateCard, stateText, stateTitle } from "./StateCard.css";

type EmptyStateProps = {
  title: string;
  message: string;
};

export function EmptyState({ title, message }: EmptyStateProps) {
  return (
    <div className={stateCard}>
      <h2 className={stateTitle}>{title}</h2>
      <p className={stateText}>{message}</p>
    </div>
  );
}
