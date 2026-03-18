import type { PropsWithChildren, ReactNode } from "react";

import { panel, panelCaption, panelHeader, panelTitle } from "./Panel.css";

type PanelProps = PropsWithChildren<{
  title: string;
  caption?: string;
  aside?: ReactNode;
}>;

export function Panel({ title, caption, aside, children }: PanelProps) {
  return (
    <section className={panel}>
      <header className={panelHeader}>
        <div>
          <h2 className={panelTitle}>{title}</h2>
          {caption ? <p className={panelCaption}>{caption}</p> : null}
        </div>
        {aside}
      </header>
      {children}
    </section>
  );
}
