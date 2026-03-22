import type { NavigationItem } from "../../../shared/config/navigation";
import { ModuleStateCard } from "../../../shared/ui/states/ModuleStateCard";

type ModulePlaceholderPageProps = {
  item: NavigationItem;
};

function getModuleGroup(item: NavigationItem): "core" | "runtime" {
  return item.key === "signals" ||
    item.key === "strategy" ||
    item.key === "execution" ||
    item.key === "opportunity" ||
    item.key === "orchestration" ||
    item.key === "position-expansion" ||
    item.key === "portfolio-governor"
    ? "runtime"
    : "core";
}

export function ModulePlaceholderPage({ item }: ModulePlaceholderPageProps) {
  const group = getModuleGroup(item);
  const status = group === "core" ? "read-only" : "restricted";

  return (
    <ModuleStateCard
      title={item.title}
      status={status}
      caption={
        group === "core"
          ? "Модуль уже отражён в системной карте dashboard, но для него пока нет отдельной operator-facing страницы."
          : "Контур уже существует в текущей platform truth, но в dashboard пока доступен только как часть overview и navigation map."
      }
      message={
        group === "core"
          ? `${item.description}. Этот раздел виден в navigation как системная поверхность и будет развиваться отдельно от overview.`
          : `${item.description}. Этот runtime-контур уже существует в mainline, но отдельная UI-поверхность для него ещё не подключена в dashboard line.`
      }
      metaBadges={[
        {
          label: group === "core" ? "системная поверхность" : "runtime-контур",
          tone: group === "core" ? "neutral" : "accent",
        },
        {
          label: item.phase,
          tone: "neutral",
        },
      ]}
      hints={[
        `Навигационный маршрут уже закреплён: ${item.route}`,
        group === "core"
          ? "Сейчас это честная placeholder-поверхность без отдельного backend/API расширения."
          : "Сейчас контур читается через overview, а не через самостоятельную страницу.",
      ]}
    />
  );
}
