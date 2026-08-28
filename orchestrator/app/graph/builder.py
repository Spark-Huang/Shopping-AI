import logging
from typing import Any

from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, START, StateGraph

from ..agents.state import State
from .nodes import GraphNodes
from .routing import GraphRouting

logger = logging.getLogger(__name__)


def create_graph(
    cart_agent: Any,
    retriever_agent: Any,
    planner_agent: Any,
    chatter_agent: Any,
    summary_agent: Any,
    config
) -> StateGraph:
    """
    Create the LangGraph for Shopping AI.
    
    The graph orchestrates the flow between different specialized agents:
    - Memory retrieval
    - Input safety checks
    - Query routing via planner
    - Specialized agent processing (cart, retriever)
    - Output generation via chatter
    - Output safety checks
    - Response summarization
    
    Args:
        cart_agent: Agent for shopping cart operations
        retriever_agent: Agent for product search and retrieval
        planner_agent: Agent for query routing
        chatter_agent: Agent for natural language responses
        summary_agent: Agent for response summarization
    
    Returns:
        Compiled LangGraph instance
    """
    logger.info("Creating Shopping AI graph")
    
    # Set the global config for use throughout the graph
    GraphNodes.configure(config)
    
    # Create the graph
    graph = StateGraph(State)
    
    # Add nodes with descriptive names
    graph.add_node("memory_node", GraphNodes.get_memory)
    graph.add_node("input_safety_node", GraphNodes.check_input_safety)
    graph.add_node("planner_node", planner_agent.invoke)
    graph.add_node("cart_node", cart_agent.invoke)
    graph.add_node("retriever_node", retriever_agent.invoke)
    graph.add_node("check_safety_node", GraphNodes.check_safety_node)
    graph.add_node("begin_buffered_stream", GraphNodes.begin_buffered_stream)
    graph.add_node("passthrough_node", RunnableLambda(GraphNodes.passthrough))
    graph.add_node("chatter_node", chatter_agent.invoke)
    graph.add_node("output_safety_node", GraphNodes.check_output_safety)
    graph.add_node("summarize_node", summary_agent.invoke)
    graph.add_node("unsafe_output", GraphNodes.unsafe_output)

    # Set the entry point
    graph.add_edge(START, "memory_node")
    graph.add_edge("begin_buffered_stream", "chatter_node")
    
    graph.add_edge("memory_node", "planner_node")
    graph.add_edge("memory_node", "input_safety_node")

    # Add conditional routing based on planner decision
    graph.add_conditional_edges(
        "planner_node",
        planner_agent.decide_function,
        {
            "cart": "cart_node",
            "retriever": "retriever_node",
            "chatter": "passthrough_node",
        }
    )

    # Add edges from specialized agents to safety checks
    graph.add_edge(["cart_node", "input_safety_node"], "check_safety_node")
    graph.add_edge(["retriever_node", "input_safety_node"], "check_safety_node")
    graph.add_edge(["passthrough_node", "input_safety_node"], "check_safety_node")

    # Add conditional routing for input safety
    graph.add_conditional_edges(
        "check_safety_node",
        GraphRouting.decide_if_input_safe,
        {
            "chatter_node": "begin_buffered_stream",
            "unsafe_output": "unsafe_output",
        },
    )

    # Add edges for output processing
    graph.add_edge("chatter_node", "output_safety_node")

    # Add conditional routing for output safety
    graph.add_conditional_edges(
        "output_safety_node",
        GraphRouting.decide_if_output_safe,
        {
            "summarize_node": "summarize_node",
            "unsafe_output": "unsafe_output",
        },
    )

    # End graph
    graph.add_edge("summarize_node", END)
    graph.add_edge("unsafe_output", END)
    
    # Compile and return the graph
    compiled_graph = graph.compile()
    logger.info("create_graph() | Graph created successfully.")
    
    return compiled_graph
