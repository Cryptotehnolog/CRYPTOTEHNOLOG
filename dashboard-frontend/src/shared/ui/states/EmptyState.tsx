import { stateCaption, stateCard, stateText, stateTitle } from "./StateCard.css";

type EmptyStateProps = {
  title: string;
  message: string;
  caption?: string;
};

export function EmptyState({ title, message, caption }: EmptyStateProps) {
  return (
    <div className={stateCard}>
      <h2 className={stateTitle}>{title}</h2>
      {caption ? <p className={stateCaption}>{caption}</p> : null}
      <p className={stateText}>{message}</p>
    </div>
  );
}
