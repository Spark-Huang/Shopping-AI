
"""
Query routing agent for Shopping AI.

This module contains the PlannerAgent that determines which specialized agent
should handle a user's query based on the query content and context.
"""
import os
import logging
import re
import sys
import time
from typing import Tuple, Dict, List
from openai import OpenAI

from .state import State, Cart


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

_SPENDING_RECALL_INTENT_RE = re.compile(
    r"\bhow\s+much\b|\bwhat\s+did\s+i\b|总共|这个月",
    re.IGNORECASE,
)
_SPENDING_RECALL_SUBJECT_RE = re.compile(
    r"\b(?:spent|orders?|spending)\b|花了|花费",
    re.IGNORECASE,
)


# Configuration will be loaded by the main application


class PlannerAgent:
    """
    Agent responsible for routing user queries to appropriate specialized agents.
    
    The planner analyzes the user's query and determines whether it should be
    handled by the cart agent, retriever agent, visualizer agent, or chatter agent.
    """
    
    def __init__(
        self,
        config,
    ) -> None:
        """
        Initialize the PlannerAgent.
        
        Args:
            config: Configuration instance
        """
        logger.info(f"PlannerAgent.__init__() | llm_name={config.llm_name}, llm_port={config.llm_port}")
        
        # Front-of-pipeline routing is latency-sensitive: prefer the configured
        # small/fast model, falling back to the main model (getattr keeps
        # duck-typed test configs that omit the field working).
        self.llm_name = getattr(config, "small_llm_name", None) or config.llm_name
        self.llm_port = config.llm_port
        self.agent_choices = config.agent_choices
        self.system_prompt = config.routing_prompt
        
        # Initialize the LLM client
        try:
            self.model = OpenAI(
                base_url=self.llm_port,
                api_key=os.environ.get("LLM_API_KEY")
            )
            logger.info("PlannerAgent.__init__() | initialization complete")
        except Exception as e:
            logger.error(f"Failed to initialize PlannerAgent: {e}")
            raise

    def _create_routing_messages(self, query: str, has_image: bool = False) -> List[Dict[str, str]]:
        """
        Create the messages for the routing decision.

        Args:
            query: The user's query to route
            has_image: Whether the current turn includes an attached image.
                The router needs this signal so that deictic queries like
                "do you have this under $100" can be resolved against the
                image instead of being treated as a question about a named
                product that doesn't exist in context.

        Returns:
            List of messages for the LLM
        """
        user_content = f"IMAGE ATTACHED: {'yes' if has_image else 'no'}\nCustomer Query: {query}"
        return [
            {
                "role": "system",
                "content": self.system_prompt
            },
            {
                "role": "user",
                "content": user_content
            }
        ]

    def _call_llm_for_routing(self, query: str, has_image: bool = False) -> str:
        """
        Call the LLM to determine the appropriate agent for the query.
        
        Args:
            query: The user's query
            has_image: Whether the current turn includes an attached image.

        Returns:
            The name of the agent to route to
        """
        try:
            messages = self._create_routing_messages(query, has_image=has_image)
            
            response = self.model.chat.completions.create(
                model=self.llm_name,
                messages=messages,
                temperature=0.0,
                max_tokens=100,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}}
            )
            
            response_content = response.choices[0].message.content.strip().lower()
            logger.debug(f"LLM routing response: {response_content}")
            
            return response_content
            
        except Exception as e:
            logger.error(f"Error calling LLM for routing: {e}")
            return "chatter"  # Default to chatter on error

    def _normalize_agent_name(self, agent_name: str) -> str:
        """
        Normalize agent names to match graph node names.
        
        Args:
            agent_name: Raw agent name from LLM
            
        Returns:
            Normalized agent name
        """
        # Map common variations to standard names
        mappings = {
            "search": "retriever",
            "cart_node": "cart",
            "product_finder": "retriever",
            "general": "chatter",
            "assistant": "chatter"
        }
        
        normalized = mappings.get(agent_name, agent_name)
        
        # Ensure the normalized name is in our valid choices
        if normalized not in self.agent_choices:
            # Smaller/verbose models sometimes answer the routing prompt with a
            # full justification sentence instead of the bare agent name.
            # Salvage the decision from keyword cues before falling back so a
            # verbose-but-correct route is not silently downgraded to chatter.
            normalized = self._salvage_agent_from_text(agent_name)
        
        if normalized not in self.agent_choices:
            logger.warning(f"Invalid agent choice '{agent_name}', defaulting to 'chatter'")
            return "chatter"
        
        return normalized

    def _salvage_agent_from_text(self, text: str) -> str:
        """Extract an agent choice from a verbose routing response.

        Scans the raw lowercased response for the most specific agent keyword:
        cart cues win over retrieval cues (cart operations are rarer and more
        costly to miss), retrieval cues win over generic conversation cues.

        Args:
            text: Raw (non-empty) LLM routing response.

        Returns:
            A best-effort agent name, or the original text if no cue matched.
        """
        lowered = text.lower()
        if any(cue in lowered for cue in (
            "cart_node", "cart manager", "cart operation", "add to cart",
            "adding", "removing items", "clear my cart", "cart total",
        )):
            return "cart"
        if any(cue in lowered for cue in (
            "search", "product finder", "retriever", "new product",
            "product discovery", "browse", "catalog",
        )):
            return "retriever"
        if "chatter" in lowered or "general assistant" in lowered:
            return "chatter"
        return text

    @staticmethod
    def _is_spending_recall_query(query: str) -> bool:
        """Identify order/spending-recall questions without an LLM round trip."""
        return bool(
            _SPENDING_RECALL_INTENT_RE.search(query)
            and _SPENDING_RECALL_SUBJECT_RE.search(query)
        )

    def invoke(
        self,
        state: State,
        verbose: bool = True
    ) -> State:
        """
        Process the user query to determine which agent should handle it.
        
        Args:
            state: Current state containing the user query
            verbose: Whether to log detailed information
            
        Returns:
            Updated state with the next_agent field set
        """
        start_time = time.monotonic()
        logger.info(f"PlannerAgent.invoke() | Processing routing for query: {state.query}")
        
        output_state = state
        
        if self._is_spending_recall_query(state.query):
            logger.info("PlannerAgent.invoke() | Spending-recall query detected, routing to chatter")
            response_content = "chatter"
        # Handle image-only queries
        elif state.has_image() and state.is_empty_query():
            logger.info("PlannerAgent.invoke() | Image-only query detected, routing to retriever")
            response_content = "retriever"
        else:
            # Use LLM to determine routing.
            # Note: We only pass the query, not the context, to avoid routing bias.
            # When an image is attached we also pass that signal so the router can
            # treat deictic references ("this product", "this item") as referring
            # to the image instead of mis-routing to chatter as a named-product
            # question.
            query_string = f"USER QUERY: {state.query}"
            response_content = self._call_llm_for_routing(
                query_string, has_image=state.has_image()
            )
        
        # Normalize the agent name
        normalized_agent = self._normalize_agent_name(response_content)
        
        # Update the state
        output_state.next_agent = normalized_agent
        end_time = time.monotonic()
        output_state.add_timing("planner", end_time - start_time)

        logger.info(f"PlannerAgent.invoke() | Routed query to agent: {normalized_agent}")
        return output_state

    def decide_function(self, state: State) -> str:
        """
        Return the next agent to route to based on the state.
        
        This method is used by the LangGraph for conditional routing.
        
        Args:
            state: Current state with next_agent field
            
        Returns:
            Name of the next agent to route to
        """
        next_agent = getattr(state, "next_agent", "")
        if not next_agent:
            logger.warning("No next_agent in state, defaulting to chatter")
            return "chatter"
        
        logger.debug(f"Routing to agent: {next_agent}")
        return next_agent
