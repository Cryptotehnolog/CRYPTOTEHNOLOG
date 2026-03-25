import { NavLink } from "react-router-dom";

import { navigationItems } from "../../shared/config/navigation";
import { Badge } from "../../shared/ui/primitives/Badge";
import {
  brandBlock,
  brandCaption,
  brandTitle,
  groupCaption,
  groupList,
  groupTitle,
  itemBadge,
  navDescription,
  navItem,
  navLink,
  navSection,
  navSectionHeader,
  sideFrame,
} from "./SideNavigation.css";

const navGroups = [
  {
    key: "overview",
    title: "Обзор",
    caption: "Главная витрина текущего состояния платформы в режиме только чтения.",
    items: navigationItems.filter((item) => item.key === "overview"),
  },
  {
    key: "core",
    title: "Системные поверхности",
    caption: "Контур управления, наблюдаемость и операторские поверхности без отдельного торгового сценария.",
    items: navigationItems.filter(
      (item) =>
        item.key !== "overview" &&
        ![
          "signals",
          "strategy",
          "execution",
          "opportunity",
          "orchestration",
          "position-expansion",
          "portfolio-governor",
        ].includes(item.key),
    ),
  },
  {
    key: "runtime",
    title: "Торговые контуры",
    caption: "Контуры основной линии, которые уже видны в навигации и постепенно раскрываются через обзор и отдельные страницы.",
    items: navigationItems.filter((item) =>
      [
        "signals",
        "strategy",
        "execution",
        "opportunity",
        "orchestration",
        "position-expansion",
        "portfolio-governor",
      ].includes(item.key),
    ),
  },
] as const;

export function SideNavigation() {
  return (
    <div className={sideFrame}>
      <div className={brandBlock}>
        <div className={brandCaption}>CRYPTOTEHNOLOG</div>
        <div className={brandTitle}>Операторская панель</div>
      </div>

      <nav className={navSection} aria-label="Разделы панели">
        {navGroups.map((group) => (
          <section key={group.key}>
            <header className={navSectionHeader}>
              <div className={groupTitle}>{group.title}</div>
              <div className={groupCaption}>{group.caption}</div>
            </header>
            <ul className={groupList}>
              {group.items.map((item) => (
                <li key={item.key} className={navItem}>
                  <NavLink
                    className={({ isActive }) => navLink[isActive ? "active" : "inactive"]}
                    end={item.key === "overview"}
                    to={item.route}
                  >
                    <div>
                      <div>{item.title}</div>
                      <small className={navDescription}>{item.description}</small>
                    </div>
                    <span className={itemBadge}>
                      <Badge
                        tone={
                          item.key === "overview"
                            ? "accent"
                            : group.key === "runtime"
                              ? "warning"
                              : "neutral"
                        }
                      >
                        {item.phase}
                      </Badge>
                    </span>
                  </NavLink>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </nav>
    </div>
  );
}
