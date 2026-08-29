retrieval_extraction_function = {
    "type": "function",
    "function": {
        "name": "extract_retrieval_inputs",
        "description": """Extract structured retrieval inputs from the user request.

                          Return:
                          - search_entities: WHAT THE USER WANTS THE CATALOG TO RETURN,
                            never an item they only reference for styling or comparison.
                          - up to three relevant categories from the provided category list.
                          - explicit numeric price filters ONLY when the user states a budget.

                          Do not infer missing constraints.

                          IMPORTANT:
                          - For NEW product type queries (including "shoes that go with it",
                            "earrings to match", "a bag for this outfit"), extract the NEW
                            product type from the query, not the referenced item.
                          - For ATTRIBUTE questions about a previously named product
                            (colors, sizes, care, price), extract that product's name.
                          - NEVER combine or merge context products with new search terms.""",
        "parameters": {
            "type": "object",
            "properties": {
                "search_entities": {
                    "type": "array",
                    "description": "Individual terms that the user is searching for.",
                    "items": {"type": "string"}
                },
                "category_one": {
                    "type": "string",
                    "description": "Most relevant category from available categories. Must be an exact value from the provided list."
                },
                "category_two": {
                    "type": "string",
                    "description": "Second most relevant category from available categories. Must be an exact value from the provided list."
                },
                "category_three": {
                    "type": "string",
                    "description": "Third most relevant category from available categories. Must be an exact value from the provided list."
                },
                "min_price": {
                    "type": "number",
                    "description": "Minimum reference price in Chinese yuan. OMIT THIS FIELD unless the user explicitly states a lower bound (e.g., 'over ¥50'). Never default to 0."
                },
                "max_price": {
                    "type": "number",
                    "description": "Maximum reference price in Chinese yuan. OMIT THIS FIELD unless the user explicitly states an upper bound (e.g., 'under ¥100'). Never default to 0."
                }
            },
            "required": ["search_entities", "category_one", "category_two", "category_three"]
        }
    }
}

"""
A function that responds to the user and summarizes the context.
"""
summary_function = {
    "type" : "function",
    "function" : {
        "name" : "summarizer",
        "description" : "Tool that summarizes the context of the user's conversation.",
        "parameters" : {
            "type" : "object",
            "properties" : {
                "summary" : {
                    "type" : "string",
                    "description" : "A concise summary that MUST preserve: all product names, product specifications (materials, colors, care instructions, prices), products the user asked about, and cart contents. Summarize only the general conversation flow and user preferences."
                },
            },
            "required" : ["summary"]
        },
    },
}

"""
Gets items to add to the users cart.
"""
add_to_cart_function = {
    "type": "function",
    "function": {
        "name": "add_to_cart",
        "description": "Tool to add items to the user's cart. These items must be proper nouns from the provided context.",
        "parameters": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "The name of the item. Must be from the chat history, or most recent user query.",
                },
                "quantity": {
                    "type": "integer",
                    "description": "The number of items to add to the cart.",
                },
            },
            "required": ["item_name", "quantity"],
        },
    },
}

"""
Removes items from the user's cart.
"""
remove_from_cart_function = {
    "type": "function",
    "function": {
        "name": "remove_from_cart",
        "description": "Tool to remove items to the user's cart.",
        "parameters": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "The name of item to add to the cart.",
                },
                "quantity": {
                    "type": "integer",
                    "description": "The number of items to add to the cart.",
                },
            },
            "required": ["item_name", "quantity"],
        },
    },
}

"""
Adds multiple items to the cart in a single tool call.

Preferred over repeated ``add_to_cart`` calls whenever the user names two or
more distinct products in the same request (e.g. "add the skirt, the blouse,
and the bracelet"). The cart agent iterates ``items`` and runs the existing
per-item catalog match + memory write for each entry, so atomicity is best-
effort: a catalog miss on one line does not prevent the others from being
added and is surfaced explicitly in the response.
"""
bulk_add_to_cart_function = {
    "type": "function",
    "function": {
        "name": "bulk_add_to_cart",
        "description": (
            "Tool to add MULTIPLE items to the user's cart in a single call. "
            "Use whenever the user names two or more distinct products to add "
            "in the same request. Do not emit parallel add_to_cart calls."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": (
                        "List of items to add. Each entry carries the full product "
                        "name (copied verbatim from recent discussion) and the quantity."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "item_name": {
                                "type": "string",
                                "description": "The full product name from the chat history or most recent user query.",
                            },
                            "quantity": {
                                "type": "integer",
                                "description": "The number of units of this item to add. Defaults to 1 if unspecified.",
                            },
                        },
                        "required": ["item_name", "quantity"],
                    },
                },
            },
            "required": ["items"],
        },
    },
}

"""
Removes multiple items from the cart in a single tool call. Mirrors
``bulk_add_to_cart`` for removals.
"""
bulk_remove_from_cart_function = {
    "type": "function",
    "function": {
        "name": "bulk_remove_from_cart",
        "description": (
            "Tool to remove MULTIPLE items from the user's cart in a single call. "
            "Use whenever the user names two or more distinct products to remove "
            "in the same request. Do not emit parallel remove_from_cart calls."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": (
                        "List of items to remove. Each entry carries the full product "
                        "name (copied verbatim from recent discussion) and the quantity."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "item_name": {
                                "type": "string",
                                "description": "The full product name from the chat history or most recent user query.",
                            },
                            "quantity": {
                                "type": "integer",
                                "description": "The number of units of this item to remove. Defaults to 1 if unspecified.",
                            },
                        },
                        "required": ["item_name", "quantity"],
                    },
                },
            },
            "required": ["items"],
        },
    },
}

"""
Views items in the user's cart.
"""
view_cart_function = {
    "type": "function",
    "function": {
        "name": "view_cart",
        "description": "Tool to view the user's cart.",
    },
}

"""
Computes the monetary total of the items in the user's cart.

Use this whenever the user asks about price sums, totals, subtotals, or
how much the cart will cost. A deterministic server-side calculation
avoids LLM arithmetic errors.
"""
view_cart_total_function = {
    "type": "function",
    "function": {
        "name": "view_cart_total",
        "description": (
            "Tool to compute the total cost of the items currently in the user's cart. "
            "Use for queries like 'what's my total?', 'how much is my cart?', "
            "'cart subtotal', 'how much do I owe', or any sum-of-prices question."
        ),
    },
}
