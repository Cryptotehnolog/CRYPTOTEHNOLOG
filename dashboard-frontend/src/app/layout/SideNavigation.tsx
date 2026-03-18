import { NavLink } from "react-router-dom";

import { navigationItems } from "../../shared/config/navigation";
import { Badge } from "../../shared/ui/primitives/Badge";
import {
  brandBlock,
  brandCaption,
  brandTitle,
  itemBadge,
  navDescription,
  navItem,
  navLink,
  navList,
  navSection,
  sideFrame,
} from "./SideNavigation.css";

type SideNavigationProps = {
  currentPath: string;
};

export function SideNavigation({ currentPath }: SideNavigationProps) {
  return (
    <div className={sideFrame}>
      <div className={brandBlock}>
        <div className={brandCaption}>CRYPTOTEHNOLOG</div>
        <div className={brandTitle}>Операторская панель</div>
      </div>

      <nav className={navSection} aria-label="Разделы панели">
        <ul className={navList}>
          {navigationItems.map((item) => {
            const isCurrent =
              currentPath === item.route ||
              (currentPath === "/" && item.route === "/overview");

            return (
              <li key={item.key} className={navItem}>
                <NavLink
                  className={navLink[isCurrent ? "active" : "inactive"]}
                  to={item.route}
                >
                  <div>
                    <div>{item.title}</div>
                    <small className={navDescription}>{item.description}</small>
                  </div>
                  <span className={itemBadge}>
                    <Badge tone={item.key === "overview" ? "accent" : "neutral"}>
                      {item.phase}
                    </Badge>
                  </span>
                </NavLink>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
