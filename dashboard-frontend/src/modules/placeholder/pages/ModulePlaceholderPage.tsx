import type { NavigationItem } from "../../../shared/config/navigation";
import { ModuleStateCard } from "../../../shared/ui/states/ModuleStateCard";

type ModulePlaceholderPageProps = {
  item: NavigationItem;
};

export function ModulePlaceholderPage({ item }: ModulePlaceholderPageProps) {
  return (
    <ModuleStateCard
      title={item.title}
      status="inactive"
      message={`${item.description}. Раздел уже заложен в каркас панели, но серверный и интерфейсный слой для него ещё не подключены.`}
    />
  );
}
