import { navigationItems } from "../../shared/config/navigation";
import { Badge } from "../../shared/ui/primitives/Badge";
import {
  barMeta,
  barTitle,
  statusBar,
  statusCluster,
  titleCluster,
} from "./TopStatusBar.css";

type TopStatusBarProps = {
  currentPath: string;
};

export function TopStatusBar({ currentPath }: TopStatusBarProps) {
  const currentItem =
    navigationItems.find(
      (item) =>
        currentPath === item.route ||
        (currentPath === "/" && item.route === "/overview"),
    ) ?? navigationItems[0];

  return (
    <header className={statusBar}>
      <div className={titleCluster}>
        <div className={barMeta}>Центр управления платформой</div>
        <h1 className={barTitle}>{currentItem.title}</h1>
      </div>
      <div className={statusCluster}>
        <Badge tone="neutral">Фундамент только для чтения</Badge>
        <Badge tone="accent">{currentItem.phase.toUpperCase()}</Badge>
      </div>
    </header>
  );
}
