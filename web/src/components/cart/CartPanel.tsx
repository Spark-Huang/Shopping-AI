/**
 * CartPanel: full-page shopping-cart view for the bottom-tab navigation.
 *
 * - Shows item name, amount and unit price (when available) for the
 *   current session user.
 * - Renders as a regular in-flow page inside the Cart tab (the former
 *   fixed/collapsible side panel is gone — no Collapse button anymore).
 * - Friendly empty state when the cart has no items.
 * - Refreshes when a cart mutation is detected (via refreshSignal) and
 *   on mount. Data is persisted server-side, so it survives reloads.
 * - Reports the total item count upward (onCountChange) so the Cart tab
 *   badge in BottomTabBar stays in sync.
 */

import React, { useCallback, useEffect, useState } from "react";
import { toast } from "react-toastify";
import { useTranslation } from "react-i18next";
import ShoppingCartOutlinedIcon from "@mui/icons-material/ShoppingCartOutlined";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import ShareIcon from "@mui/icons-material/Share";
import "./cart.css";
import { fetchCart, removeCartProduct } from "../../api/cartApi";
import { markPurchased } from "../../api/ordersApi";
import { getOrCreateUserId } from "../../lib/identity";
import { CartItemData } from "../../types/cart";
import { shareText } from "../../lib/share";

const isHttpsUrl = (value: string): boolean => {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && url.hostname.length > 0;
  } catch {
    return false;
  }
};

interface CartPanelProps {
  /**
   * Bump this counter to trigger a cart refresh. The chatbox increments
   * it whenever an add/remove cart operation is detected in an assistant
   * response.
   */
  refreshSignal: number;
  /**
   * Called whenever the fetched cart contents change, with the total
   * number of items; App forwards it to the tab-bar badge.
   */
  onCountChange?: (totalItems: number) => void;
  onOrderChange?: () => void;
}

type LoadState = "loading" | "ready" | "error";

const CartPanel: React.FC<CartPanelProps> = ({ refreshSignal, onCountChange, onOrderChange }) => {
  const [items, setItems] = useState<CartItemData[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [markingPurchased, setMarkingPurchased] = useState<Set<string>>(new Set());
  const { t } = useTranslation();

  const refresh = useCallback(async () => {
    const userId = getOrCreateUserId();
    try {
      const data = await fetchCart(userId);
      setItems(Array.isArray(data.cart) ? data.cart : []);
      setLoadState("ready");
    } catch (error) {
      console.error("CartPanel: failed to load cart", error);
      setLoadState("error");
    }
  }, []);

  // Load on mount and whenever a cart mutation signal arrives.
  useEffect(() => {
    refresh();
  }, [refresh, refreshSignal]);

  const totalItems = items.reduce((sum, it) => sum + (it.amount || 0), 0);
  const totalPrice = items.reduce((sum, it) => sum + ((it.price || 0) * (it.amount || 0)), 0);
  const itemsWithoutPrice = items.filter(it => it.price == null).reduce((sum, it) => sum + (it.amount || 0), 0);

  const handleMarkPurchased = async (item: typeof items[number]) => {
    if (markingPurchased.has(item.item)) return;
    setMarkingPurchased(current => new Set(current).add(item.item));
    let orderRecorded = false;
    try {
      await markPurchased(getOrCreateUserId(), {
        item: item.item,
        price: item.price ?? null,
        note: "Marked from Cart",
      });
      orderRecorded = true;
      await removeCartProduct(getOrCreateUserId(), item.item, item.amount);
      toast.success(t("cart.movedToOrders"));
      onOrderChange?.();
    } catch (error) {
      console.error("CartPanel: failed to complete mark-purchased cart sync", error);
      setMarkingPurchased(current => {
        const next = new Set(current);
        next.delete(item.item);
        return next;
      });
      toast.error(t(orderRecorded ? "cart.syncFailed" : "me.orderFailed"));
    }
  };

  const handleShareCart = async () => {
    const lines = items.map((item) => {
      const price = item.price != null ? ` · $${(item.price * item.amount).toFixed(2)}` : "";
      return `- ${item.item} × ${item.amount}${price}`;
    });
    const text = `${t("cart.shareText")}\n${lines.join("\n")}\n${t("cart.total")}: $${totalPrice.toFixed(2)}\n${t("cart.shareSlogan")}\n${window.location.origin}`;
    try {
      if (navigator.share) {
        await navigator.share({ text });
        return;
      }
      await shareText(
        text,
        t("chatbox.shareCopied"),
        t("chatbox.shareFailed")
      );
    } catch (error) {
      if ((error as DOMException)?.name !== "AbortError") {
        toast.error(t("chatbox.shareFailed"));
      }
    }
  };

  // Keep the tab-bar badge in sync with the fetched cart contents.
  useEffect(() => {
    onCountChange?.(totalItems);
  }, [totalItems, onCountChange]);

  return (
    <section className="cart-page" aria-label={t("cart.title")}>
      <div className="cart-page__header">
        <h4 className="cart-page__title">
          <ShoppingCartOutlinedIcon
            fontSize="small"
            sx={{ color: "var(--brand-deep)" }}
          />
          {t("cart.title")}
          {loadState === "ready" && totalItems > 0 && (
            <span className="cart-page__badge">{totalItems}</span>
          )}
        </h4>
      </div>

      <div className="cart-page__body">
        {loadState === "ready" && totalItems > 0 && (
          <p className="cart-page__purchase-hint">{t("cart.purchaseHint")}</p>
        )}
        {loadState === "loading" && (
          <div className="cart-page__loading">{t("cart.loading")}</div>
        )}
        {loadState === "error" && (
          <div className="cart-page__error">{t("cart.error")}</div>
        )}
        {loadState === "ready" && items.length === 0 && (
          <div className="cart-page__empty">{t("cart.empty")}</div>
        )}
        {loadState === "ready" &&
          items.map((it) => (
            <div className="cart-page__item" key={it.item}>
              <span className="cart-page__item-name">{it.item}</span>
              <span className="cart-page__item-amount">×{it.amount}</span>
              <span className="cart-page__item-price">
                {it.price != null ? `$${(it.price * it.amount).toFixed(2)}` : ""}
              </span>
              {it.url && isHttpsUrl(it.url) && (
                <a href={it.url} target="_blank" rel="noopener noreferrer" className="cart-page__item-link">
                  <span className="sr-only">Opens on the product site</span>
                  <OpenInNewIcon fontSize="small" />
                </a>
              )}
              <button
                type="button"
                className="cart-page__item-action"
                disabled={markingPurchased.has(it.item)}
                onClick={() => handleMarkPurchased(it)}
              >
                {markingPurchased.has(it.item)
                  ? t("me.markedPurchased")
                  : t("me.markPurchased")}
              </button>
            </div>
          ))}
        {loadState === "ready" && totalItems > 0 && (
          <div className="cart-page__total">
            <div className="cart-page__total-row">
              <span>{t("cart.total")}: ${totalPrice.toFixed(2)}</span>
              {itemsWithoutPrice > 0 && (
                <span className="cart-page__no-price">
                  (+ {itemsWithoutPrice} {t("cart.noPrice")})
                </span>
              )}
              <button type="button" className="cart-page__share" onClick={handleShareCart}>
                <ShareIcon fontSize="small" />
                {t("cart.shareList")}
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
};

export default CartPanel;
