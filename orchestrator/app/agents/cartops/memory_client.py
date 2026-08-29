import json
import logging
from urllib.parse import urlparse

from typing import Any, Dict, Optional



import requests



from ..state import Cart
from .catalog_match import _extract_price





class MemoryClientMixin:
    def _memory_headers(self) -> Dict[str, str]:
        state = getattr(self, "state", None)
        if state is None or state.authorization is None:
            return {}
        return {"Authorization": state.authorization}

    def _get_cart(self, user_id: int) -> Cart:

        response = requests.get(
            f"{self.memory_base_url}/user/{user_id}/cart",
            headers=self._memory_headers(),
        )
        logging.info(f"CartAgent._get_cart() | Response text: {response.text}.")
        if response.status_code == 200:
            cart_data = json.loads(response.text)["cart"]
            return Cart(contents=cart_data)
        return Cart(contents=[])

    def _add_to_cart(self, user_id: int, item_name: str, quantity: int) -> str:
        match = self._lookup_in_catalog(item_name)
        if match is None:
            return f"No such item ({item_name}) could be found in the catalog."

        catalog_item_name = match["name"]
        price = _extract_price(match.get("text"))
        product_url = match.get("url")
        if product_url is not None:
            parsed_url = urlparse(str(product_url))
            if parsed_url.scheme != "https" or not parsed_url.netloc:
                logging.warning(
                    "CartAgent._add_to_cart() | rejected non-https catalog url "
                    f"for '{catalog_item_name}'"
                )
                product_url = None
        payload = {
            "item": catalog_item_name,
            "amount": quantity,
            "url": product_url if isinstance(product_url, str) and product_url else "",
        }
        if price is not None:
            payload["price"] = price
        response = requests.post(
            f"{self.memory_base_url}/user/{user_id}/cart/add",
            json=payload,
            headers=self._memory_headers(),
        )
        if response.status_code == 200:
            return response.json()["message"]
        return f"Failed to add {quantity} {catalog_item_name} to cart."

    def _view_cart_total(self, user_id: int) -> str:
        """Compute the cart total deterministically from cached prices.

        LLMs are unreliable for arithmetic, so we sum line totals server-side
        using the per-line price stored when the item was added. Missing prices
        are reported explicitly rather than silently dropped.
        """
        cart = self._get_cart(user_id)
        if not cart.contents:
            return "Your cart is empty, so the total is ¥0.00."

        lines = []
        subtotal = 0.0
        missing_price: list[str] = []
        for entry in cart.contents:
            item_name = entry.get("item", "")
            amount = int(entry.get("amount", 0) or 0)
            price = entry.get("price")
            if price is None:
                missing_price.append(item_name)
                lines.append(f"- {amount} x {item_name}: price unavailable")
                continue
            line_total = float(price) * amount
            subtotal += line_total
            lines.append(
                f"- {amount} x {item_name} @ ${float(price):.2f} = ${line_total:.2f}"
            )

        summary = "\n".join(lines)
        total_line = f"Cart total: ${subtotal:.2f}"
        if missing_price:
            names = ", ".join(missing_price)
            total_line += (
                f" (excluding items without a cached price: {names}. "
                "Re-add them to include their price in the total.)"
            )
        return f"{summary}\n{total_line}"

    def _remove_from_cart(self, user_id: int, item_name: str, quantity: int) -> str:
        match = self._lookup_in_catalog(item_name)
        if match is None:
            return f"No such item ({item_name}) could be found in the catalog."

        catalog_item_name = match["name"]
        response = requests.post(
            f"{self.memory_base_url}/user/{user_id}/cart/remove",
            json={"item": catalog_item_name, "amount": quantity},
            headers=self._memory_headers(),
        )
        if response.status_code == 200:
            return response.json()["message"]
        return f"Failed to remove {quantity} {catalog_item_name} from cart."
