import json
import logging
import os
import sys
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from langgraph.config import get_stream_writer

from ..budget import extract_monthly_budget
from ..state import State
from ...tools.functions import (
    add_to_cart_function,
    bulk_add_to_cart_function,
    bulk_remove_from_cart_function,
    remove_from_cart_function,
    view_cart_function,
    view_cart_total_function,
    parse_tool_call_fallback,
)
from .catalog_match import CatalogMatchMixin, _extract_price, _normalize_name
from .memory_client import MemoryClientMixin
from .name_heuristics import _extract_ordinal_position, _strip_ordinals
from .reference_resolution import ReferenceResolutionMixin


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )


logger = logging.getLogger(__name__)


class CartAgent(ReferenceResolutionMixin, CatalogMatchMixin, MemoryClientMixin):
    _CATALOG_LOOKUP_K = 5
    _IMPULSE_ITEM_VALUE = 150.0
    _IMPULSE_LINE_COUNT = 3
    def __init__(self,
            config,
        ) -> None:
            logging.info(f"CartAgent.__init__() | Initializing with llm_name={config.llm_name}, llm_port={config.llm_port}")
            self.llm_name = config.llm_name
            self.llm_port = config.llm_port
        
            # Store configuration
            self.memory_base_url = config.memory_base_url
            self.model = OpenAI(base_url=config.llm_port, api_key=os.environ["LLM_API_KEY"])
            self.search_url = config.retriever_port
            self.categories = config.categories
            self.retry_strategy = Retry(
                    total=3,                    
                    status_forcelist=[422, 429, 500, 502, 503, 504],  
                    allowed_methods=["POST"],   
                    backoff_factor=1            
                )
            logging.info(f"CartAgent.__init__() | Initialization complete")

    def invoke(
            self,
            state: State,
            verbose : bool = True
        ) -> State:
            """
            Determines which function to perform and executes it through the configured OpenAI-compatible LLM endpoint.
            """
            start = time.monotonic()
            logging.info(f"CartAgent.invoke() | Starting with query: {state.query}")
            self.state = state
            tools = [
                add_to_cart_function,
                remove_from_cart_function,
                bulk_add_to_cart_function,
                bulk_remove_from_cart_function,
                view_cart_function,
                view_cart_total_function,
            ]

            system_prompt = (
                "You are a retail cart manager. Your ONLY job is to execute exactly one cart "
                "tool call that fulfils the user's CURRENT QUERY. Do not return plain text.\n\n"
                "TOOL SELECTION (choose exactly one):\n"
                "- add_to_cart: user wants to put ONE item IN the cart. Triggers: 'add', "
                "'put in cart', \"I'll take\", 'buy', 'get me', 'include'.\n"
                "- bulk_add_to_cart: user wants to put TWO OR MORE distinct items IN the cart "
                "in the same request. Prefer this over multiple add_to_cart calls whenever the "
                "user enumerates several products (separated by commas, 'and', 'also', 'plus', "
                "'as well as', etc.). Populate 'items' with one entry per named product.\n"
                "- remove_from_cart: user wants to take ONE item OUT. Triggers: 'remove', "
                "'take out', 'delete', 'drop'.\n"
                "- bulk_remove_from_cart: user wants to take TWO OR MORE distinct items OUT in "
                "the same request. Prefer this over multiple remove_from_cart calls whenever "
                "the user enumerates several products to remove.\n"
                "- view_cart: user wants to SEE cart contents. Triggers: \"what's in my cart\", "
                "'show my cart', 'view cart', 'check my cart'. Do NOT use view_cart when the "
                "user is asking to add or remove an item.\n"
                "- view_cart_total: user wants the MONETARY TOTAL of the cart. Triggers: "
                "\"what's my total\", 'how much is my cart', 'cart subtotal', \"how much do I owe\", "
                "'total cost', 'sum of my cart'. Prefer this over view_cart whenever the user "
                "asks about a price, sum, or total. Never attempt arithmetic yourself.\n\n"
                "REFERENCE RESOLUTION:\n"
                "When the user says 'it', 'this', 'that', 'the one', 'another', etc., resolve "
                "the pronoun to the MOST RECENT specific product in RECENT DISCUSSION. Give the "
                "MOST RECENT ASSISTANT MESSAGE the highest weight, then the user's last query, "
                "then older context. Do NOT default to items already in the cart.\n\n"
                "ITEM NAME RULES (apply to item_name for single tools AND to every items[].item_name "
                "for bulk tools):\n"
                "- Copy the full product name VERBATIM from RECENT DISCUSSION. Do not "
                "shorten it, do not substitute a category word, do not paraphrase.\n"
                "- Examples of the same rule applied across product types (these names "
                "are illustrative only; use the actual name from RECENT DISCUSSION):\n"
                "    * Discussed: 'Alpine Waterproof Hiking Boot'. User says 'add it to "
                "my cart' -> item_name = 'Alpine Waterproof Hiking Boot'. NOT 'boot' "
                "or 'hiking boot'.\n"
                "    * Discussed: 'Pearl Drop Stud Earrings'. User says 'buy the "
                "pearls' -> item_name = 'Pearl Drop Stud Earrings'. NOT 'pearls' or "
                "'earrings'.\n"
                "    * Discussed: 'Midnight Velvet Blazer'. User says 'add the blue "
                "one' -> item_name = 'Midnight Velvet Blazer'. NOT 'blue one' or "
                "'blazer'.\n"
                "    * Discussed: 'Bamboo Slim-Fit Chinos'. User says 'add those' -> "
                "item_name = 'Bamboo Slim-Fit Chinos'. NOT 'those' or 'chinos'.\n"
                "    * Discussed: 'Honey Floral Print Midi Skirt', 'Lace and Silk Blouse', "
                "'Pearl Bracelet'. User says 'please add the Honey Floral Print Midi Skirt, "
                "the Lace and Silk Blouse, and the Pearl Bracelet to my cart' -> call "
                "bulk_add_to_cart with items=[{item_name: 'Honey Floral Print Midi Skirt', "
                "quantity: 1}, {item_name: 'Lace and Silk Blouse', quantity: 1}, "
                "{item_name: 'Pearl Bracelet', quantity: 1}].\n"
                "- If the user specifies a quantity use it; otherwise default to 1.\n"
                "- Ignore minor typos in the user's query.\n"
            )

            recent_discussion = self._extract_recent_discussion(state.context)
            cart_contents = (
                [f"{c.get('amount', 1)} x {c.get('item', '')}" for c in state.cart.contents]
                if state.cart and state.cart.contents else []
            )

            user_content = (
                f"CURRENT QUERY: {state.query}\n\n"
                f"CURRENT CART: {', '.join(cart_contents) if cart_contents else 'empty'}\n\n"
                f"RECENT DISCUSSION (most recent first, use this to resolve pronouns):\n"
                f"{recent_discussion}"
            )

            messages: list[ChatCompletionMessageParam] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ]

            # Create the request parameters
            response = self.model.chat.completions.create(
                model=self.llm_name,
                messages=messages,
                temperature=0.0,
                max_tokens=8192,
                tools=tools,
                tool_choice="auto",
                stream=False,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}}
            )

            message = response.choices[0].message
            tool_name = None
            tool_args = {}

            if message.tool_calls:
                called_tool = message.tool_calls[0]
                tool_name = called_tool.function.name
                tool_args = json.loads(called_tool.function.arguments)
            else:
                logging.warning(f"CartAgent.invoke() | No structured tool_calls returned. Content: {message.content}")
                tool_name, tool_args = parse_tool_call_fallback(message.content)

            if not tool_name:
                logging.error("CartAgent.invoke() | Could not determine tool call from model response.")
                output_state = state
                output_state.response = "I couldn't process that cart action. Could you please rephrase your request?"
                end = time.monotonic()
                output_state.context = output_state.context + f"\nAgent Response: {output_state.response}"
                output_state.timings["cart"] = end - start
                return output_state

            logging.info(f"CartAgent.invoke() | Tool name: {tool_name}")

            # Override ``item_name`` for add/remove with a deterministic
            # resolver. Coreference over a multi-KB context is where the
            # model silently picks the wrong product; anchored signals from
            # cart + context fix that.
            #
            # Override policy is anchor-strength aware:
            #   * "named"/"ordinal" queries carry an explicit user instruction
            #     (a product name or a display position) -- they override the
            #     LLM's item_name when the two disagree. The LLM is still
            #     trusted when it already produced the exact same product.
            #   * "pronoun" queries are weak signals: the LLM sees the same
            #     RECENT DISCUSSION we do, so its explicit ``product``/
            #     ``item_name`` choice is kept unless it failed to provide one
            #     (then the last-mentioned product fills the gap). This avoids
            #     the historical bug where "add the first one to my cart" had
            #     the LLM's correct pick silently replaced by the
            #     rightmost-mentioned product.
            if tool_name in ("add_to_cart", "remove_from_cart"):
                # Some models emit the alias ``product`` instead of
                # ``item_name``; normalize so both the resolver override
                # below and the dispatch branch can rely on one field.
                if not tool_args.get("item_name") and tool_args.get("product"):
                    logging.info(
                        "CartAgent.invoke() | normalizing tool arg 'product' -> 'item_name'"
                    )
                    tool_args["item_name"] = tool_args["product"]

                resolved, anchor_kind = self._resolve_target_item_with_kind(state)
                if resolved:
                    llm_pick = tool_args.get("item_name") or tool_args.get("product")
                    if not llm_pick:
                        logging.warning(
                            f"CartAgent.invoke() | filling missing item_name "
                            f"from deterministic={resolved!r} (anchor={anchor_kind})"
                        )
                        tool_args["item_name"] = resolved
                    elif anchor_kind in ("named", "ordinal") and (
                        _normalize_name(llm_pick) != _normalize_name(resolved)
                    ):
                        logging.warning(
                            f"CartAgent.invoke() | overriding item_name "
                            f"llm={llm_pick!r} -> deterministic={resolved!r} "
                            f"(anchor={anchor_kind})"
                        )
                        tool_args["item_name"] = resolved
            elif tool_name in ("bulk_add_to_cart", "bulk_remove_from_cart"):
                # Normalize ``items`` shape and fix up any per-entry names the
                # model paraphrased. Quantity defaults live here too so the
                # dispatch branches don't need to repeat the coercion.
                items = self._coerce_bulk_items(tool_args.get("items"))
                items = self._override_bulk_item_names(items, state)
                tool_args["items"] = items

            output_state = state 
            if verbose:
                logging.info(f"CartAgent.invoke() | tool_name: {tool_name}\n\t| tool_args: {tool_args}")

            # Perform our associated action.
            if tool_name == "add_to_cart":
                logging.info(f"CartAgent.invoke() | Adding to cart")
                item_name = tool_args["item_name"]
                quantity = tool_args["quantity"]
                output_state.response = self._add_to_cart(state.user_id, item_name, quantity)
                output_state.cart = self._get_cart(state.user_id)
                gentle_impulse_note = self._maybe_impulse_budget_note(
                    output_state.response,
                    output_state.cart,
                    state.user_id,
                )
                if gentle_impulse_note:
                    output_state.response += f"\n{gentle_impulse_note}"
            
            elif tool_name == "remove_from_cart":
                logging.info(f"CartAgent.invoke() | Removing from cart")
                item_name = tool_args["item_name"]
                quantity = tool_args["quantity"]    
                output_state.response = self._remove_from_cart(state.user_id, item_name, quantity)
                output_state.cart = self._get_cart(state.user_id)

            elif tool_name == "bulk_add_to_cart":
                items = tool_args.get("items") or []
                logging.info(
                    f"CartAgent.invoke() | Bulk adding {len(items)} item(s) to cart"
                )
                lines = []
                for entry in items:
                    if not isinstance(entry, dict):
                        continue
                    name = (entry.get("item_name") or "").strip()
                    if not name:
                        continue
                    try:
                        quantity = int(entry.get("quantity", 1) or 1)
                    except (TypeError, ValueError):
                        quantity = 1
                    lines.append(self._add_to_cart(state.user_id, name, quantity))
                if lines:
                    output_state.response = "\n".join(lines)
                else:
                    output_state.response = (
                        "No items were specified to add to the cart."
                    )
                output_state.cart = self._get_cart(state.user_id)

            elif tool_name == "bulk_remove_from_cart":
                items = tool_args.get("items") or []
                logging.info(
                    f"CartAgent.invoke() | Bulk removing {len(items)} item(s) from cart"
                )
                lines = []
                for entry in items:
                    if not isinstance(entry, dict):
                        continue
                    name = (entry.get("item_name") or "").strip()
                    if not name:
                        continue
                    try:
                        quantity = int(entry.get("quantity", 1) or 1)
                    except (TypeError, ValueError):
                        quantity = 1
                    lines.append(self._remove_from_cart(state.user_id, name, quantity))
                if lines:
                    output_state.response = "\n".join(lines)
                else:
                    output_state.response = (
                        "No items were specified to remove from the cart."
                    )
                output_state.cart = self._get_cart(state.user_id)

            elif tool_name == "view_cart":
                cart = self._get_cart(state.user_id)
                logging.info(f"CartAgent.invoke() | Viewing cart.\n\t| Cart: {cart}")
                if len(cart.contents) == 0:
                    output_state.response = "Your cart is empty."
                else:
                    contents = cart.contents
                    items = [f"The user has ({contents[ind]['amount']} {contents[ind]['item']}) in their cart" for ind in range(len(contents))]
                    items_str = ". ".join(items)
                    logging.info(f"CartAgent.invoke() | item list retrieved: {items_str}")
                    output_state.response = f"{items_str}"
                output_state.cart = cart

            elif tool_name == "view_cart_total":
                logging.info("CartAgent.invoke() | Computing cart total.")
                output_state.response = self._view_cart_total(state.user_id)
                output_state.cart = self._get_cart(state.user_id)

            # Update our context and return our state.
            if verbose:
                logging.info(f"CartAgent.invoke() | output_state: {output_state}")
        
            #self._update_context(state.user_id, f"USER QUERY:{output_state.query}\nRESPONSE:{output_state.response}")
            end = time.monotonic()
            output_state.context = output_state.context + f"\nAgent Response: {output_state.response}"
            output_state.timings["cart"] = end - start
            logging.info(f"CartAgent.invoke() | Returning final state with response: {output_state.response}")

            return output_state

    def _maybe_impulse_budget_note(
        self, add_response: str, cart, user_id: int
    ) -> str | None:
        if add_response.startswith("Failed") or "No such item" in add_response:
            return None
        if sum(item.get("amount", 0) or 0 for item in cart.contents) < 3:
            return None
        priced_items = [
            (float(item["price"]), item.get("amount", 1) or 1)
            for item in cart.contents
            if item.get("price") is not None
        ]
        if len(priced_items) < 3 or not any(
            price >= self._IMPULSE_ITEM_VALUE for price, _amount in priced_items
        ):
            return None

        cart_total = sum(price * amount for price, amount in priced_items)
        if cart_total < self._IMPULSE_ITEM_VALUE * self._IMPULSE_LINE_COUNT:
            return None

        budget = extract_monthly_budget(
            self._get_context_for_impulse_note(user_id)
        )
        if budget is not None:
            return (
                f"Budget alert: your cart total of ${cart_total:.2f} is above your "
                f"${budget:.2f} monthly budget. If now is the right time to buy, no problem; "
                "otherwise I can help you compare or remove items."
            )
        return (
            f"Gentle note: your cart now totals ${cart_total:.2f} and includes a "
            "higher-priced item. If you'd like a spending reference, set a budget in Me; "
            "otherwise feel free to keep browsing."
        )

    def _get_context_for_impulse_note(self, user_id: int) -> str:
        try:
            state = getattr(self, "state", None)
            headers = {"Authorization": state.authorization} if state else {}
            response = requests.get(
                f"{self.memory_base_url}/user/{user_id}/context",
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            return response.json().get("context", "")
        except (requests.RequestException, ValueError, KeyError):
            return ""


_extract_ordinal_position = _extract_ordinal_position
_strip_ordinals = _strip_ordinals
