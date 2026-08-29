/**
 * CartPanel: full-page shopping-cart view for the bottom-tab navigation.
 *
 * - Shows item name, amount and unit price (when available) for the
 *   current session user.
 * - Each line has a checkbox, a quantity stepper (+/-) and a delete button.
 * - Select multiple lines and check them out in one go (records orders and
 *   clears the settled lines from the cart).
 * - Renders as a regular in-flow page inside the Cart tab.
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
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import CheckBoxOutlineBlankIcon from "@mui/icons-material/CheckBoxOutlineBlank";
import CheckBoxIcon from "@mui/icons-material/CheckBox";
import "./cart.css";
import {
  checkoutCart,
  fetchCart,
  removeCartProduct,
  setCartQuantity,
} from "../../api/cartApi";
import { getOrCreateUserId } from "../../lib/identity";
import { CartItemData } from "../../types/cart";
import { shareText } from "../../lib/share";
import { formatCny } from "../../lib/currency";

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
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState<Set<string>>(new Set());
  const [checkingOut, setCheckingOut] = useState(false);
  const { t } = useTranslation();

  const refresh = useCallback(async () => {
    const userId = getOrCreateUserId();
    try {
      const data = await fetchCart(userId);
      const cart = Array.isArray(data.cart) ? data.cart : [];
      setItems(cart);
      // Drop selections for lines that no longer exist.
      setSelected((current) => {
        const names = new Set(cart.map((it) => it.item));
        const next = new Set([...current].filter((name) => names.has(name)));
        return next;
      });
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

  const selectedItems = items.filter((it) => selected.has(it.item));
  const selectedCount = selectedItems.reduce((sum, it) => sum + (it.amount || 0), 0);
  const selectedTotal = selectedItems.reduce(
    (sum, it) => sum + ((it.price || 0) * (it.amount || 0)),
    0
  );
  const allSelected = items.length > 0 && selected.size === items.length;

  const toggleSelected = (name: string) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    setSelected(allSelected ? new Set() : new Set(items.map((it) => it.item)));
  };

  const markBusy = (name: string, on: boolean) => {
    setBusy((current) => {
      const next = new Set(current);
      if (on) {
        next.add(name);
      } else {
        next.delete(name);
      }
      return next;
    });
  };

  const handleQuantityChange = async (item: CartItemData, delta: number) => {
    const nextAmount = (item.amount || 0) + delta;
    if (nextAmount < 1) return; // deletion goes through the delete button
    if (nextAmount > 99) return;
    markBusy(item.item, true);
    try {
      await setCartQuantity(
        getOrCreateUserId(),
        item.item,
        nextAmount,
        item.price,
        item.url ?? null
      );
      await refresh();
    } catch (error) {
      console.error("CartPanel: failed to update quantity", error);
      toast.error(t("cart.updateFailed", { item: item.item }));
    } finally {
      markBusy(item.item, false);
    }
  };

  const handleDelete = async (item: CartItemData) => {
    markBusy(item.item, true);
    try {
      await removeCartProduct(getOrCreateUserId(), item.item, item.amount);
      toast.success(t("cart.removed", { item: item.item }));
      await refresh();
    } catch (error) {
      console.error("CartPanel: failed to remove item", error);
      toast.error(t("cart.removeFailed", { item: item.item }));
    } finally {
      markBusy(item.item, false);
    }
  };

  const handleCheckout = async () => {
    if (selectedItems.length === 0 || checkingOut) return;
    setCheckingOut(true);
    try {
      await checkoutCart(
        getOrCreateUserId(),
        selectedItems.map((it) => ({ item: it.item, price: it.price }))
      );
      toast.success(
        t("cart.checkoutSuccess", { count: selectedCount, total: selectedTotal.toFixed(2) })
      );
      setSelected(new Set());
      await refresh();
      onOrderChange?.();
    } catch (error) {
      console.error("CartPanel: checkout failed", error);
      toast.error(t("cart.checkoutFailed"));
    } finally {
      setCheckingOut(false);
    }
  };

  const handleShareCart = async () => {
    const lines = items.map((item) => {
      const price = item.price != null ? ` · ${formatCny(item.price * item.amount)}` : "";
      return `- ${item.item} × ${item.amount}${price}`;
    });
    const text = `${t("cart.shareText")}\n${lines.join("\n")}\n${t("cart.total")}: ${formatCny(totalPrice)}\n${t("cart.shareSlogan")}\n${window.location.origin}`;
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
          items.map((it) => {
            const isSelected = selected.has(it.item);
            return (
              <div className="cart-page__item" key={it.item}>
                <button
                  type="button"
                  className="cart-page__item-check"
                  aria-pressed={isSelected}
                  aria-label={t("cart.toggleSelect", { item: it.item })}
                  disabled={busy.has(it.item)}
                  onClick={() => toggleSelected(it.item)}
                >
                  {isSelected ? (
                    <CheckBoxIcon fontSize="small" color="primary" />
                  ) : (
                    <CheckBoxOutlineBlankIcon fontSize="small" />
                  )}
                </button>
                <span className="cart-page__item-name">{it.item}</span>
                <span className="cart-page__qty">
                  <button
                    type="button"
                    className="cart-page__qty-btn"
                    disabled={busy.has(it.item) || (it.amount || 0) <= 1}
                    aria-label={t("cart.decreaseQty", { item: it.item })}
                    onClick={() => handleQuantityChange(it, -1)}
                  >
                    −
                  </button>
                  <span className="cart-page__qty-value">{it.amount}</span>
                  <button
                    type="button"
                    className="cart-page__qty-btn"
                    disabled={busy.has(it.item) || (it.amount || 0) >= 99}
                    aria-label={t("cart.increaseQty", { item: it.item })}
                    onClick={() => handleQuantityChange(it, 1)}
                  >
                    +
                  </button>
                </span>
                <span className="cart-page__item-price">
                  {it.price != null ? formatCny(it.price * it.amount) : ""}
                </span>
                {it.url && isHttpsUrl(it.url) && (
                  <a href={it.url} target="_blank" rel="noopener noreferrer" className="cart-page__item-link">
                    <span className="sr-only">Opens on the product site</span>
                    <OpenInNewIcon fontSize="small" />
                  </a>
                )}
                <button
                  type="button"
                  className="cart-page__item-delete"
                  disabled={busy.has(it.item)}
                  aria-label={t("cart.delete", { item: it.item })}
                  onClick={() => handleDelete(it)}
                >
                  <DeleteOutlineIcon fontSize="small" />
                </button>
              </div>
            );
          })}
        {loadState === "ready" && items.length > 0 && (
          <div className="cart-page__total">
            <div className="cart-page__select-all">
              <button
                type="button"
                className="cart-page__item-check"
                aria-pressed={allSelected}
                onClick={toggleSelectAll}
              >
                {allSelected ? (
                  <CheckBoxIcon fontSize="small" color="primary" />
                ) : (
                  <CheckBoxOutlineBlankIcon fontSize="small" />
                )}
              </button>
              <span>{t("cart.selectAll")}</span>
            </div>
            <div className="cart-page__total-row">
              <span>
                {selected.size > 0
                  ? t("cart.selectedTotal", { count: selectedCount, total: selectedTotal.toFixed(2) })
                  : `${t("cart.total")}: ${formatCny(totalPrice)}`}
              </span>
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
            <button
              type="button"
              className="cart-page__checkout"
              disabled={selected.size === 0 || checkingOut}
              onClick={handleCheckout}
            >
              {checkingOut
                ? t("cart.checkingOut")
                : selected.size > 0
                  ? t("cart.checkoutSelected", { count: selectedCount, total: selectedTotal.toFixed(2) })
                  : t("cart.checkout")}
            </button>
          </div>
        )}
      </div>
    </section>
  );
};

export default CartPanel;
