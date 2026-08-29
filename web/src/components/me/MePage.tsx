/**
 * MePage: "Me" tab — brand word, language switcher, Orders/Favorites
 * entries (D6) and version line.
 *
 * D6: Orders and Favorites are entry rows leading to empty-state sub-views
 * navigation is modelled as a tiny local view state so it maps 1:1 onto
 * future routes (/me, /me/orders, /me/favorites) when a router is added.
 */

import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "react-toastify";
import Switch from "@mui/material/Switch";
import PersonOutlineIcon from "@mui/icons-material/PersonOutline";
import ReceiptLongOutlinedIcon from "@mui/icons-material/ReceiptLongOutlined";
import FavoriteBorderOutlinedIcon from "@mui/icons-material/FavoriteBorderOutlined";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import ShoppingCartOutlinedIcon from "@mui/icons-material/ShoppingCartOutlined";
import { setAppLanguage, type AppLang } from "../../i18n";
import OrdersPage from "../orders/OrdersPage";
import { addContext, fetchHistory } from "../../api/historyApi";
import { fetchFreshness, saveFreshness } from "../../api/freshnessApi";
import {
  fetchRegion,
  saveRegion,
  SHOPPING_REGIONS,
} from "../../api/regionApi";
import { markPurchased } from "../../api/ordersApi";
import { getOrCreateUserId } from "../../lib/identity";
import { getAuthUser } from "../../lib/auth";
import { parseMonthlyBudget, replaceMonthlyBudget } from "../../lib/budget";
import { readFavorites } from "../../lib/favorites";
import type { ImageContent } from "../../types/chat";

/**
 * Sub-views of the Me tab. Values intentionally mirror the future route
 * slugs so swapping the local state for a router is mechanical.
 */
type MeView = "root" | "orders" | "favorites";

/** Displayed version; keep in sync with package.json "version". */
const APP_VERSION = "1.0.0";

type MePageProps = {
  onAddToCart?: (productName: string) => void;
  onOrderChange?: () => void;
  safetyEnabled: boolean;
  onSafetyChange: (enabled: boolean) => void;
  onLogout?: () => void;
};

const MePage: React.FC<MePageProps> = ({
  onAddToCart,
  onOrderChange,
  safetyEnabled,
  onSafetyChange,
  onLogout,
}) => {
  const { t, i18n } = useTranslation();
  // Local stand-in for routing inside the Me tab (D6); see MeView above.
  const [view, setView] = useState<MeView>("root");
  const [favorites, setFavorites] = useState<ImageContent[]>([]);
  const [favoriteSignal, setFavoriteSignal] = useState(0);
  const [orderSignal, setOrderSignal] = useState(0);
  const [markingPurchased, setMarkingPurchased] = useState<Set<string>>(
    new Set()
  );
  const [budget, setBudget] = useState<number | null>(null);
  const [freshnessHours, setFreshnessHours] = useState<number | null>(null);
  const [region, setRegion] = useState<string>("贵州");

  const loadBudget = useCallback(async () => {
    const history = await fetchHistory(getOrCreateUserId());
    setBudget(parseMonthlyBudget(history.context || ""));
  }, []);

  const loadFreshness = useCallback(async () => {
    const setting = await fetchFreshness();
    setFreshnessHours(setting.data_freshness_hours);
  }, []);

  const loadRegion = useCallback(async () => {
    const setting = await fetchRegion();
    setRegion(setting.region);
  }, []);

  useEffect(() => {
    void loadBudget().catch((error) => {
      console.error("MePage: failed to load monthly budget", error);
    });
  }, [loadBudget]);

  useEffect(() => {
    void loadFreshness().catch((error) => {
      console.error("MePage: failed to load data freshness", error);
    });
  }, [loadFreshness]);

  useEffect(() => {
    void loadRegion().catch((error) => {
      console.error("MePage: failed to load shopping region", error);
    });
  }, [loadRegion]);

  useEffect(() => {
    const syncFavorites = () => setFavorites(readFavorites());
    syncFavorites();
    window.addEventListener("storage", syncFavorites);
    return () => window.removeEventListener("storage", syncFavorites);
  }, [favoriteSignal]);

  const toggleLang = () => {
    const next: AppLang = i18n.language?.startsWith("zh") ? "en" : "zh";
    setAppLanguage(next);
  };

  const saveBudget = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const input = event.currentTarget.elements.namedItem("budget");
    if (!(input instanceof HTMLInputElement)) return;
    const value = Number(input.value.trim());
    if (!Number.isFinite(value) || value <= 0) {
      toast.error(t("me.budgetInvalid"));
      return;
    }

    try {
      const userId = getOrCreateUserId();
      const history = await fetchHistory(userId);
      await addContext(
        userId,
        replaceMonthlyBudget(history.context || "", value)
      );
      setBudget(value);
      input.value = "";
      toast.success(t("me.budgetSaved", { budget: value.toFixed(2) }));
    } catch (error) {
      console.error("MePage: failed to save monthly budget", error);
      toast.error(t("me.budgetSaveFailed"));
    }
  };

  const saveDataFreshness = async (
    event: React.FormEvent<HTMLFormElement>
  ) => {
    event.preventDefault();
    const input = event.currentTarget.elements.namedItem("dataFreshness");
    if (!(input instanceof HTMLInputElement)) return;
    const value = Number(input.value.trim());
    if (!Number.isFinite(value) || value <= 0) {
      toast.error(t("me.freshnessInvalid"));
      return;
    }
    try {
      const setting = await saveFreshness(value);
      setFreshnessHours(setting.data_freshness_hours);
      input.value = "";
      toast.success(
        t("me.freshnessSaved", { hours: setting.data_freshness_hours })
      );
    } catch (error) {
      console.error("MePage: failed to save data freshness", error);
      toast.error(t("me.freshnessSaveFailed"));
    }
  };

  const saveShoppingRegion = async (
    event: React.ChangeEvent<HTMLSelectElement>
  ) => {
    const nextRegion = event.target.value;
    try {
      const setting = await saveRegion(nextRegion);
      setRegion(setting.region);
      toast.success(t("me.regionSaved", { region: setting.region }));
    } catch (error) {
      console.error("MePage: failed to save shopping region", error);
      toast.error(t("me.regionSaveFailed"));
    }
  };

  const markFavoritePurchased = useCallback(
    async (product: ImageContent) => {
      if (markingPurchased.has(product.productName)) return;
      setMarkingPurchased((current) =>
        new Set(current).add(product.productName)
      );
      try {
        await markPurchased(getOrCreateUserId(), {
          item: product.productName,
          price: product.price ?? null,
          note: "Marked from Favorites",
        });
        setOrderSignal((value) => value + 1);
      } catch (error) {
        console.error("MePage: failed to mark favorite purchased", error);
        setMarkingPurchased((current) => {
          const next = new Set(current);
          next.delete(product.productName);
          return next;
        });
      }
    },
    [markingPurchased]
  );

  const currentUser = getAuthUser();

  if (view === "orders") {
    return (
      <OrdersPage
        refreshSignal={orderSignal}
        onBack={() => setView("root")}
        onOrderChange={onOrderChange}
      />
    );
  }
  if (view === "favorites") {
    return (
      <div className="me-page">
        <button
          type="button"
          className="me-page__back"
          onClick={() => setView("root")}
          aria-label={t("me.back")}
        >
          <ArrowBackIcon fontSize="small" />
          {t("me.back")}
        </button>
        {favorites.length === 0 ? (
          <div className="me-empty" role="status">
            <span className="me-empty__icon">
              <FavoriteBorderOutlinedIcon />
            </span>
            <p className="me-empty__title">{t("me.favoritesEmpty")}</p>
            <p className="me-empty__hint">{t("me.emptyBrowseHint")}</p>
          </div>
        ) : (
          <div className="favorites-list">
            {favorites.map((product) => (
              <article className="favorites-item" key={product.productName}>
                <img src={product.productUrl} alt={product.productName} />
                <div>
                  <h5>{product.productName}</h5>
                  {product.price != null && (
                    <span>${product.price.toFixed(2)}</span>
                  )}
                  <div className="favorites-item__actions">
                    <button
                      type="button"
                      className="favorites-item__action"
                      onClick={() => onAddToCart?.(product.productName)}
                    >
                      <ShoppingCartOutlinedIcon fontSize="small" />
                      {t("chatbox.addToCart")}
                    </button>
                    {product.externalUrl && (
                      <a
                        href={product.externalUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="favorites-item__action"
                      >
                        <OpenInNewIcon fontSize="small" />
                        {t("me.buyExternal")}
                      </a>
                    )}
                    <button
                      type="button"
                      className="favorites-item__action"
                      disabled={markingPurchased.has(product.productName)}
                      onClick={() => markFavoritePurchased(product)}
                    >
                      <ReceiptLongOutlinedIcon fontSize="small" />
                      {markingPurchased.has(product.productName)
                        ? t("me.markedPurchased")
                        : t("me.markPurchased")}
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="me-page">
      {/* Brand */}
      <div className="me-page__brand">
        <span className="me-page__brand-dot" aria-hidden="true" />
        <h4 className="me-page__brand-name">Guikela</h4>
      </div>

      {/* Account row: current user + sign out */}
      <div className="me-page__row">
        <span className="me-page__row-icon" aria-hidden="true">
          <PersonOutlineIcon fontSize="small" />
        </span>
        <span className="me-page__row-label">
          {t("me.loggedInAs", { username: currentUser?.username ?? "" })}
        </span>
        <button
          type="button"
          className="lang-toggle"
          onClick={onLogout}
          data-testid="logout-button"
        >
          {t("me.logout")}
        </button>
      </div>

      {/* Orders entry (D6) */}
      <button
        type="button"
        className="me-page__row me-page__row--link"
        onClick={() => setView("orders")}
        data-testid="me-entry-orders"
      >
        <span className="me-page__row-icon" aria-hidden="true">
          <ReceiptLongOutlinedIcon fontSize="small" />
        </span>
        <span className="me-page__row-label">{t("me.orders")}</span>
      </button>

      {/* Favorites entry (D6) */}
      <button
        type="button"
        className="me-page__row me-page__row--link"
        onClick={() => {
          setFavoriteSignal((value) => value + 1);
          setView("favorites");
        }}
        data-testid="me-entry-favorites"
      >
        <span className="me-page__row-icon" aria-hidden="true">
          <FavoriteBorderOutlinedIcon fontSize="small" />
        </span>
        <span className="me-page__row-label">{t("me.favorites")}</span>
      </button>

      <div className="me-page__budget" data-testid="me-budget">
        <div className="me-page__row">
          <span className="me-page__row-label">{t("me.budget")}</span>
          <span className="me-page__row-value">
            {budget == null ? t("me.budgetValue") : `$${budget.toFixed(2)}`}
          </span>
        </div>
        <p className="me-page__row-hint">{t("me.budgetHint")}</p>
        <form className="me-page__budget-form" onSubmit={saveBudget}>
          <input
            name="budget"
            type="number"
            min={1}
            step="0.01"
            inputMode="decimal"
            aria-label={t("me.budgetLabel")}
            placeholder={t("me.budgetPlaceholder")}
          />
          <button type="submit">{t("me.saveBudget")}</button>
        </form>
      </div>

      <div className="me-page__budget" data-testid="me-data-freshness">
        <div className="me-page__row">
          <span className="me-page__row-label">
            {t("me.dataFreshness")}
          </span>
          <span className="me-page__row-value">
            {freshnessHours == null
              ? "—"
              : t("me.freshnessValue", { hours: freshnessHours })}
          </span>
        </div>
        <p className="me-page__row-hint">{t("me.freshnessHint")}</p>
        <form className="me-page__budget-form" onSubmit={saveDataFreshness}>
          <input
            name="dataFreshness"
            type="number"
            min={1}
            step="1"
            inputMode="numeric"
            aria-label={t("me.freshnessLabel")}
            placeholder={t("me.freshnessPlaceholder")}
          />
          <button type="submit">{t("me.saveFreshness")}</button>
        </form>
      </div>

      <div className="me-page__budget" data-testid="me-region">
        <div className="me-page__row">
          <span className="me-page__row-label">{t("me.region")}</span>
          <span className="me-page__row-value">{region}</span>
        </div>
        <p className="me-page__row-hint">{t("me.regionHint")}</p>
        <form className="me-page__budget-form">
          <select
            name="region"
            value={region}
            onChange={saveShoppingRegion}
            aria-label={t("me.regionLabel")}
          >
            {SHOPPING_REGIONS.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </form>
      </div>

      {/* Language row */}
      <div className="me-page__row">
        <span className="me-page__row-icon" aria-hidden="true">
          <PersonOutlineIcon fontSize="small" />
        </span>
        <span className="me-page__row-label">{t("me.language")}</span>
        <button
          type="button"
          className="lang-toggle"
          onClick={toggleLang}
          aria-label="Switch language"
          data-testid="lang-toggle"
        >
          {t("me.languageToggle")}
        </button>
      </div>

      {/* Safety row. The local mandatory blocklist always remains active. */}
      <div className="me-page__row">
        <span className="me-page__row-label">{t("me.safety")}</span>
        <Switch
          checked={safetyEnabled}
          onChange={(event) => onSafetyChange(event.target.checked)}
          inputProps={
            {
              "aria-label": t("me.safety"),
              "data-testid": "safety-switch",
            } as React.InputHTMLAttributes<HTMLInputElement>
          }
        />
      </div>
      <p className="me-page__row-hint">
        {t(safetyEnabled ? "me.safetyOnHint" : "me.safetyOffHint")}
      </p>

      {/* Version row */}
      <div className="me-page__row">
        <span className="me-page__row-label">{t("me.version")}</span>
        <span className="me-page__row-value">{APP_VERSION}</span>
      </div>
    </div>
  );
};

export default MePage;
