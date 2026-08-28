/**
 * BottomTabBar: Symy-style fixed bottom tab navigation.
 *
 * - Three tabs: Messages / Cart / Me, each with an MUI icon + i18n label.
 * - Cart tab carries an item-count badge (MUI Badge).
 * - Active tab in brand blue, inactive in gray; respects the notch via
 *   env(safe-area-inset-bottom).
 * - Controlled component: App owns activeTab and keeps every panel
 *   mounted (visibility switching only), so switching never unmounts
 *   the chatbox SSE stream or the cart state.
 */

import React from "react";
import { useTranslation } from "react-i18next";
import Badge from "@mui/material/Badge";
import ChatBubbleOutlineIcon from "@mui/icons-material/ChatBubbleOutline";
import ShoppingCartOutlinedIcon from "@mui/icons-material/ShoppingCartOutlined";
import PersonOutlineIcon from "@mui/icons-material/PersonOutline";

/** The three tabs of the app shell. */
export type TabId = "messages" | "cart" | "me";

interface BottomTabBarProps {
  /** Currently visible tab. */
  activeTab: TabId;
  /** Called with the newly selected tab id. */
  onChange: (tab: TabId) => void;
  /** Total item count shown as the Cart tab badge. */
  cartCount: number;
}

const BottomTabBar: React.FC<BottomTabBarProps> = ({
  activeTab,
  onChange,
  cartCount,
}) => {
  const { t } = useTranslation();

  const tabs: {
    id: TabId;
    label: string;
    icon: React.ReactNode;
    testid: string;
  }[] = [
    {
      id: "messages",
      label: t("tabs.messages"),
      icon: <ChatBubbleOutlineIcon />,
      testid: "tab-messages",
    },
    {
      id: "cart",
      label: t("tabs.cart"),
      icon: (
        <Badge
          color="primary"
          badgeContent={cartCount}
          max={99}
          showZero={false}
        >
          <ShoppingCartOutlinedIcon />
        </Badge>
      ),
      testid: "tab-cart",
    },
    {
      id: "me",
      label: t("tabs.me"),
      icon: <PersonOutlineIcon />,
      testid: "tab-me",
    },
  ];

  return (
    <nav className="bottom-tab-bar" aria-label="Main navigation">
      {tabs.map((tab) => {
        const active = tab.id === activeTab;
        return (
          <button
            key={tab.id}
            type="button"
            className={`bottom-tab-bar__tab${active ? " bottom-tab-bar__tab--active" : ""}`}
            aria-current={active ? "page" : undefined}
            aria-selected={active}
            onClick={() => onChange(tab.id)}
            data-testid={tab.testid}
          >
            <span className="bottom-tab-bar__icon">{tab.icon}</span>
            <span className="bottom-tab-bar__label">{tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
};

export default BottomTabBar;
