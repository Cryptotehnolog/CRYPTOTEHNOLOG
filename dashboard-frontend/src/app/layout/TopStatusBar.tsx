import { useLocation } from "react-router-dom";

import { navigationItems } from "../../shared/config/navigation";
import { Badge } from "../../shared/ui/primitives/Badge";
import {
  barMeta,
  barSubtitle,
  barTitle,
  statusBar,
  statusCluster,
  titleCluster,
} from "./TopStatusBar.css";

export function TopStatusBar() {
  const location = useLocation();
  const currentItem =
    navigationItems.find(
      (item) =>
        location.pathname === item.route ||
        (location.pathname === "/" && item.route === "/overview"),
    ) ?? navigationItems[0];

  const currentPhaseLabel = currentItem.phase === "core" ? "системная поверхность" : currentItem.phase;

  return (
    <header className={statusBar}>
      <div className={titleCluster}>
        <div className={barMeta}>Поддерживающая линия панели • операторский вид только для чтения</div>
        <h1 className={barTitle}>{currentItem.title}</h1>
        <p className={barSubtitle}>
          {currentItem.description}. Панель остаётся поддерживающим контуром только для чтения и
          отражает текущее состояние платформы после v1.14.0 без расширения серверных границ.
        </p>
      </div>
      <div className={statusCluster}>
        <Badge tone="neutral">линия панели</Badge>
        <Badge tone="accent">состояние платформы v1.14.0</Badge>
        <Badge tone="warning">только чтение</Badge>
        <Badge tone="neutral">{currentPhaseLabel}</Badge>
      </div>
    </header>
  );
}
