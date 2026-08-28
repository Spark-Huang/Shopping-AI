import ast
import json
import re
from typing import Any, Dict, Optional, Tuple
from typing import Any, Dict, Optional, Tuple

def parse_tool_call_fallback(content: str) -> Tuple[Optional[str], Dict[str, Any]]:
    """Parse a tool call from raw model content when structured tool_calls are absent.

    Handles two output formats observed from OpenAI-compatible model servers when the vLLM
    tool parser does not match the model's emit style:

    1. XML-style:
         <tool_call>
           <function=NAME>
             <parameter=KEY>VALUE</parameter>
           </function>
         </tool_call>

    2. JSON-style:
         {"name": "NAME", "arguments": {...}}

    Returns (tool_name, args_dict). Both are empty-ish if parsing fails.
    """
    if not content:
        return None, {}

    name, args = _parse_xml_tool_call(content)
    if name:
        return name, args

    return _parse_json_tool_call(content)


def _parse_xml_tool_call(content: str) -> Tuple[Optional[str], Dict[str, Any]]:
    function_match = re.search(r"<function=([^>]+)>", content)
    if not function_match:
        return None, {}

    tool_name = function_match.group(1).strip()
    params: Dict[str, Any] = {}
    param_pattern = re.compile(
        r"<parameter=([^>]+)>\s*(.*?)\s*</parameter>", re.DOTALL
    )
    for match in param_pattern.finditer(content):
        key = match.group(1).strip()
        value = match.group(2).strip()
        params[key] = _coerce_value(value)
    return tool_name, params


def _parse_json_tool_call(content: str) -> Tuple[Optional[str], Dict[str, Any]]:
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start == -1 or end <= start:
            return None, {}
        parsed = json.loads(content[start:end])
    except (json.JSONDecodeError, TypeError):
        return None, {}

    if not isinstance(parsed, dict):
        return None, {}
    name = parsed.get("name")
    if not name:
        return None, {}
    args = parsed.get("arguments") or parsed.get("parameters") or {}
    if not isinstance(args, dict):
        args = {}
    return name, args


def _coerce_value(value: str) -> Any:
    if not value:
        return value
    stripped = value.strip()
    # The XML tool-call format returns list/dict arguments as their string
    # repr (e.g. "[]", "['red', 'blue']", "{'min_price': 50}"). Parse those
    # into real Python containers so downstream code doesn't have to special
    # case string-shaped lists. Fall back to the raw string on parse failure.
    if stripped and stripped[0] in "[{":
        try:
            return ast.literal_eval(stripped)
        except (ValueError, SyntaxError):
            try:
                return json.loads(stripped)
            except ValueError:
                return value
    if stripped.lstrip("-").isdigit():
        try:
            return int(stripped)
        except ValueError:
            pass
    try:
        if "." in stripped:
            return float(stripped)
    except ValueError:
        pass
    return value
