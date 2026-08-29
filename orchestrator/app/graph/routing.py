import time

from ..agents.state import SafetyResult, State

_CURRENT_MONTH_PREFIX = time.strftime("%Y-%m")


def _format_monthly_order_summary(state: State) -> str:
        """Summarize the current month's manual orders for grounded recall."""
        orders = [
            order
            for order in (state.recent_orders.entries if state.recent_orders else [])
            if str(order.get("purchased_at", "")).startswith(_CURRENT_MONTH_PREFIX)
        ]
        if not orders:
            return "0 orders, total ¥0.00 this month"
    
        try:
            total = sum(float(order.get("price") or 0) for order in orders)
        except (TypeError, ValueError):
            return (
                f"{len(orders)} orders this month; one or more order prices are invalid. "
                "Use the individual order prices below."
            )
        items = ", ".join(str(order.get("item") or "Unnamed item") for order in orders)
        return f"{len(orders)} orders, total ¥{total:.2f} this month: {items}"


class GraphRouting:
    """Routing logic for the graph."""

    @staticmethod
    def decide_if_input_safe(safety: SafetyResult) -> str:
        return "chatter_node" if safety.is_safe else "unsafe_output"

    @staticmethod
    def decide_if_output_safe(safety: SafetyResult) -> str:
        return "summarize_node" if safety.is_safe else "unsafe_output"
