/**
 * Navbar component — Guikelai (贵客来) brand status bar.
 *
 * - Brand word + small round logo mark.
 * - The hamburger MenuIcon opens a "more choices" dropdown: new chat,
 *   product discovery, cart, profile, language toggle and an about entry
 *   (with the version footer). Closes on outside click and Escape.
 */

import React, { useEffect, useRef, useState } from "react";
import MenuIcon from "@mui/icons-material/Menu";
import AddCommentOutlinedIcon from "@mui/icons-material/AddCommentOutlined";
import TravelExploreOutlinedIcon from "@mui/icons-material/TravelExploreOutlined";
import ShoppingCartOutlinedIcon from "@mui/icons-material/ShoppingCartOutlined";
import PersonOutlineOutlinedIcon from "@mui/icons-material/PersonOutlineOutlined";
import TranslateIcon from "@mui/icons-material/Translate";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import { toast } from "react-toastify";
import { useTranslation } from "react-i18next";
import { setAppLanguage, type AppLang } from "../i18n";
import type { TabId } from "./BottomTabBar";

interface NavbarProps {
  /** Navigates the shell to the given tab. */
  onNavigate?: (tab: TabId) => void;
  /** Starts a fresh chat conversation; the menu entry hides when absent. */
  onNewChat?: () => void;
  /** Toggles the UI language; falls back to the built-in i18n switch. */
  onToggleLanguage?: () => void;
}

const Navbar: React.FC<NavbarProps> = ({
  onNavigate,
  onNewChat,
  onToggleLanguage,
}) => {
  const { t, i18n } = useTranslation();
  const [menuOpen, setMenuOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  // Close on outside click / Escape while the dropdown is open.
  useEffect(() => {
    if (!menuOpen) return;
    const handleClickOutside = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [menuOpen]);

  const handleLanguageClick = () => {
    setMenuOpen(false);
    if (onToggleLanguage) {
      onToggleLanguage();
    } else {
      const next: AppLang = i18n.language?.startsWith("zh") ? "en" : "zh";
      setAppLanguage(next);
    }
  };

  const handleAboutClick = () => {
    setMenuOpen(false);
    toast.info(t("menu.version"));
  };

  const menuItems: {
    key: string;
    label: string;
    icon: React.ReactNode;
    onClick: () => void;
  }[] = [
    ...(onNewChat
      ? [
          {
            key: "newChat",
            label: t("menu.newChat"),
            icon: <AddCommentOutlinedIcon sx={{ fontSize: 18 }} />,
            onClick: () => {
              setMenuOpen(false);
              onNewChat();
            },
          },
        ]
      : []),
    {
      key: "discover",
      label: t("menu.discover"),
      icon: <TravelExploreOutlinedIcon sx={{ fontSize: 18 }} />,
      onClick: () => {
        setMenuOpen(false);
        onNavigate?.("discover");
      },
    },
    {
      key: "cart",
      label: t("menu.cart"),
      icon: <ShoppingCartOutlinedIcon sx={{ fontSize: 18 }} />,
      onClick: () => {
        setMenuOpen(false);
        onNavigate?.("cart");
      },
    },
    {
      key: "me",
      label: t("menu.me"),
      icon: <PersonOutlineOutlinedIcon sx={{ fontSize: 18 }} />,
      onClick: () => {
        setMenuOpen(false);
        onNavigate?.("me");
      },
    },
    {
      key: "language",
      label: t("menu.language"),
      icon: <TranslateIcon sx={{ fontSize: 18 }} />,
      onClick: handleLanguageClick,
    },
    {
      key: "about",
      label: t("menu.about"),
      icon: <InfoOutlinedIcon sx={{ fontSize: 18 }} />,
      onClick: handleAboutClick,
    },
  ];

  return (
    <div ref={rootRef}>
      {/* Top status bar: brand + "more choices" menu trigger */}
      <div className="status-bar">
        <div className="status-bar__brand">
          <button
            type="button"
            className="status-bar__menu-trigger"
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            aria-label={t("brand.name")}
            onClick={() => setMenuOpen((open) => !open)}
          >
            <MenuIcon sx={{ color: "var(--brand-deep)" }} fontSize="small" />
          </button>
          <img
            className="status-bar__logo"
            src="/images/logo-guikelai.png"
            alt={t("brand.name")}
          />
          <span className="status-bar__brand-word">{t("brand.name")}</span>
        </div>

        {menuOpen && (
          <div className="brand-menu" role="menu" aria-label={t("brand.name")}>
            {menuItems.map((item) => (
              <button
                key={item.key}
                type="button"
                role="menuitem"
                className="brand-menu__item"
                onClick={item.onClick}
              >
                <span className="brand-menu__item-icon" aria-hidden="true">
                  {item.icon}
                </span>
                {item.label}
              </button>
            ))}
            <div className="brand-menu__version">{t("menu.version")}</div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Navbar;
