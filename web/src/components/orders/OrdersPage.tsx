import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import ReceiptLongOutlinedIcon from "@mui/icons-material/ReceiptLongOutlined";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import { fetchOrders } from "../../api/ordersApi";
import { fetchHistory } from "../../api/historyApi";
import { getOrCreateUserId } from "../../lib/identity";
import { parseMonthlyBudget } from "../../lib/budget";
import type { OrderData } from "../../types/orders";

type LoadState = "loading" | "ready" | "error";

interface OrdersPageProps {
  refreshSignal: number;
  onBack: () => void;
  onOrderChange?: () => void;
}

const OrdersPage: React.FC<OrdersPageProps> = ({
  refreshSignal,
  onBack,
  onOrderChange,
}) => {
  const { t } = useTranslation();
  const [orders, setOrders] = useState<OrderData[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [budget, setBudget] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      const userId = getOrCreateUserId();
      const [data, history] = await Promise.all([
        fetchOrders(userId),
        fetchHistory(userId),
      ]);
      setOrders(data.orders);
      setBudget(parseMonthlyBudget(history.context || ""));
      setLoadState("ready");
    } catch (error) {
      console.error("OrdersPage: failed to load orders", error);
      setLoadState("error");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh, refreshSignal]);

  useEffect(() => {
    if (refreshSignal > 0) onOrderChange?.();
  }, [refreshSignal, onOrderChange]);

  const monthSummary = useMemo(() => {
    const prefix = new Date().toISOString().slice(0, 7);
    const monthly = orders.filter((order) =>
      (order.purchased_at ?? "").startsWith(prefix)
    );
    const total = monthly.reduce((sum, order) => sum + (order.price ?? 0), 0);
    return { count: monthly.length, total };
  }, [orders]);

  const budgetPercent =
    budget == null ? null : Math.min(100, (monthSummary.total / budget) * 100);
  const overBudget = budget != null && monthSummary.total > budget;

  return (
    <div className="me-page">
      <button
        type="button"
        className="me-page__back"
        onClick={onBack}
        data-testid="orders-back"
      >
        <ArrowBackIcon fontSize="small" />
        {t("me.back")}
      </button>
      {loadState === "loading" && (
        <p className="orders-summary">{t("me.ordersLoading")}</p>
      )}
      {loadState === "error" && (
        <p className="orders-error">{t("me.ordersError")}</p>
      )}
      {loadState === "ready" && orders.length === 0 && (
        <div className="me-empty" role="status">
          <span className="me-empty__icon">
            <ReceiptLongOutlinedIcon />
          </span>
          <p className="me-empty__title">{t("me.ordersEmpty")}</p>
          <p className="me-empty__hint">{t("me.ordersEmptyHint")}</p>
        </div>
      )}
      {loadState === "ready" && orders.length > 0 && (
        <>
          <p className="orders-summary" data-testid="orders-monthly-summary">
            {t("me.ordersMonthlySummary", {
              count: monthSummary.count,
              total: monthSummary.total.toFixed(2),
            })}
          </p>
          {budget != null && (
            <div
              className={`orders-budget ${
                overBudget ? "orders-budget--over" : "orders-budget--ok"
              }`}
              data-testid="orders-budget"
            >
              <div className="orders-budget__header">
                <span>
                  {t("me.ordersBudget", {
                    budget: budget.toFixed(2),
                    total: monthSummary.total.toFixed(2),
                  })}
                </span>
                <span>
                  {overBudget
                    ? t("me.ordersOverBudget", {
                        amount: (monthSummary.total - budget).toFixed(2),
                      })
                    : t("me.ordersRemaining", {
                        amount: (budget - monthSummary.total).toFixed(2),
                      })}
                </span>
              </div>
              <div
                className="orders-budget__track"
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={budget}
                aria-valuenow={Math.min(monthSummary.total, budget)}
                aria-label={t("me.ordersBudgetProgressBar")}
              >
                <div
                  className="orders-budget__bar"
                  style={{ width: `${budgetPercent ?? 0}%` }}
                />
              </div>
            </div>
          )}
          <div className="orders-list">
            {orders.map((order) => (
              <article className="orders-item" key={order.id}>
                <span className="orders-item__name">{order.item}</span>
                {order.price != null && <span>${order.price.toFixed(2)}</span>}
                {order.purchased_at && (
                  <time dateTime={order.purchased_at}>
                    {order.purchased_at.slice(0, 10)}
                  </time>
                )}
              </article>
            ))}
          </div>
        </>
      )}
    </div>
  );
};

export default OrdersPage;
