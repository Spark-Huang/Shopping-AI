
"""
Data models for Guikelai.

This module defines the core data structures used throughout the shopping assistant,
including the main State object that flows through the LangGraph and supporting models.
"""
from operator import ior
from pydantic import BaseModel, Field
from typing import Annotated, TypedDict, Dict, List, Any, Optional


def last_non_empty(current: str, update: str) -> str:
    """Merge concurrent language updates without losing a detected value."""
    return update or current


class Cart(BaseModel):
    """
    Shopping cart model for storing user's selected items.
    
    Attributes:
        contents: List of cart items with their quantities and metadata
    """
    contents: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of items in the cart with their quantities and metadata"
    )
    
    def is_empty(self) -> bool:
        """Check if the cart is empty."""
        return len(self.contents) == 0
    
    def get_item_count(self) -> int:
        """Get the total number of items in the cart."""
        return sum(item.get('amount', 0) for item in self.contents)
    
    def get_items(self) -> List[str]:
        """Get a list of unique item names in the cart."""
        return list(set(item.get('item', '') for item in self.contents))


class RecentOrders(BaseModel):
    """Recent manual orders used for grounded spending recall."""

    entries: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Most recent manually recorded purchases, newest first"
    )


class State(BaseModel):
    """
    Main state object that flows through the LangGraph.
    
    This object contains all the information needed by the various agents
    to process user queries and generate responses.
    
    Attributes:
        user_id: Unique identifier for the user
        query: The user's input query
        context: Previous conversation context
        cart: User's shopping cart
        recent_orders: Recent manual orders for grounded spending recall
        response: Generated response from agents
        image: Base64 encoded image data (if provided)
        retrieved: Dictionary of retrieved product information
        next_agent: Next agent to route to (set by planner)
        safety_enabled: Whether to enable content safety checks
        timings: Performance timing information
    """
    user_id: int = Field(..., description="Unique user identifier")
    authorization: Optional[str] = Field(
        default=None,
        exclude=True,
        representation=False,
        description="Authorization header forwarded to protected services",
    )
    session_id: Optional[int] = Field(default=None, description="Chat session identifier")
    query: str = Field(..., description="User's input query")
    context: str = Field(default="", description="Previous conversation context")
    cart: Cart = Field(default_factory=Cart, description="User's shopping cart")
    recent_orders: RecentOrders = Field(
        default_factory=RecentOrders,
        description="Recent manual orders for grounded spending recall"
    )
    response: str = Field(default="", description="Generated response from agents")
    image: str = Field(default="", description="Base64 encoded image data")
    retrieved: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Dictionary of retrieved product information keyed by product name. "
            "Legacy shape: name -> image path. Commercial shape (D4): "
            "name -> {'image': str, 'url'?: str, 'price'?: float}."
        )
    )
    next_agent: str = Field(default="", description="Next agent to route to")
    language: Annotated[str, last_non_empty] = Field(
        default="",
        description="Reply language requested by the UI (en/zh, D5)"
    )
    stream_buffer: Any = Field(
        default=None,
        exclude=True,
        representation=False,
        description="Internal per-request safety stream buffer"
    )
    safety_enabled: bool = Field(default=True, description="Enable safety checks")
    dialect: bool = Field(
        default=False,
        description="Guizhou-dialect reply mode requested by the UI (stylistic only)"
    )
    timings: Annotated[Dict[str, float], ior] = Field(
        default_factory=dict,
        description="Performance timing information for each step"
    )
    
    def add_timing(self, step: str, duration: float) -> None:
        """Add timing information for a processing step."""
        self.timings[step] = duration
    
    def get_total_time(self) -> float:
        """Get the total processing time."""
        return sum(self.timings.values())
    
    def has_image(self) -> bool:
        """Check if the state contains an image."""
        return bool(self.image.strip())
    
    def is_empty_query(self) -> bool:
        """Check if the query is empty."""
        return not bool(self.query.strip())


class SafetyResult(BaseModel):
    """
    Safety check result model.
    
    This model represents the result of content safety checks
    performed by the safety service.
    
    Attributes:
        is_safe: Whether the content passed safety checks
        safety_timings: Timing information for the safety check
    """
    is_safe: bool = Field(default=True, description="Whether content passed safety checks")
    language: str = Field(default="", description="Reply language requested by the UI (en/zh)")
    safety_timings: Dict[str, float] = Field(
        default_factory=dict,
        description="Timing information for safety checks"
    )
    
    def add_timing(self, check_type: str, duration: float) -> None:
        """Add timing information for a specific safety check."""
        self.safety_timings[check_type] = duration
    
    def get_total_safety_time(self) -> float:
        """Get the total time spent on safety checks."""
        return sum(self.safety_timings.values())


# Type aliases for better code readability
AgentResponse = Dict[str, Any]
ProductInfo = Dict[str, Any]
TimingInfo = Dict[str, float]
