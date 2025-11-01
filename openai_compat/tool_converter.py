"""
Tool and function call conversion between OpenAI and Anthropic formats.
"""
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def convert_openai_tool_calls_to_anthropic(tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert OpenAI tool_calls to Anthropic tool_use content blocks."""
    logger.debug(f"[TOOL_CONVERSION] Converting {len(tool_calls)} OpenAI tool_calls to Anthropic format")
    logger.debug(f"[TOOL_CONVERSION] Raw OpenAI tool_calls: {json.dumps(tool_calls, indent=2)}")

    anthropic_content = []

    for idx, tool_call in enumerate(tool_calls):
        logger.debug(f"[TOOL_CONVERSION] Processing tool_call #{idx}: {json.dumps(tool_call, indent=2)}")

        function = tool_call.get("function", {})
        tool_id = tool_call.get("id", "")
        function_name = function.get("name", "")
        arguments_str = function.get("arguments", "{}")

        logger.debug(f"[TOOL_CONVERSION]   - Tool ID: {tool_id}")
        logger.debug(f"[TOOL_CONVERSION]   - Function name: {function_name}")
        logger.debug(f"[TOOL_CONVERSION]   - Arguments (raw string): {arguments_str}")

        try:
            parsed_input = json.loads(arguments_str)
            logger.debug(f"[TOOL_CONVERSION]   - Parsed input: {json.dumps(parsed_input, indent=2)}")
        except json.JSONDecodeError as e:
            logger.error(f"[TOOL_CONVERSION]   - ERROR: Failed to parse arguments JSON: {e}")
            parsed_input = {}

        anthropic_block = {
            "type": "tool_use",
            "id": tool_id,
            "name": function_name,
            "input": parsed_input
        }

        logger.debug(f"[TOOL_CONVERSION]   - Converted to Anthropic block: {json.dumps(anthropic_block, indent=2)}")
        anthropic_content.append(anthropic_block)

    logger.debug(f"[TOOL_CONVERSION] Final Anthropic tool_use blocks: {json.dumps(anthropic_content, indent=2)}")
    return anthropic_content


def convert_openai_function_call_to_anthropic(function_call: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert OpenAI function_call (legacy) to Anthropic tool_use."""
    return [{
        "type": "tool_use",
        "id": f"func_{function_call.get('name', '')}",
        "name": function_call.get("name", ""),
        "input": json.loads(function_call.get("arguments", "{}"))
    }]


def convert_openai_tools_to_anthropic(openai_tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    """Convert OpenAI tools/functions to Anthropic tools format."""
    if not openai_tools:
        logger.debug("[TOOLS_SCHEMA] No tools to convert")
        return None

    logger.debug(f"[TOOLS_SCHEMA] Converting {len(openai_tools)} OpenAI tools to Anthropic format")
    logger.debug(f"[TOOLS_SCHEMA] Raw OpenAI tools: {json.dumps(openai_tools, indent=2)}")

    anthropic_tools = []

    for idx, tool in enumerate(openai_tools):
        logger.debug(f"[TOOLS_SCHEMA] Processing tool #{idx}: {json.dumps(tool, indent=2)}")

        # Check if it's already in Anthropic format (Cursor sends this)
        if "name" in tool and "description" in tool and "type" not in tool:
            # Already Anthropic format, pass through
            logger.debug(f"[TOOLS_SCHEMA]   - Tool already in Anthropic format: {tool.get('name')}")
            anthropic_tools.append(tool)
        elif tool.get("type") == "function":
            # Standard OpenAI format
            function = tool.get("function", {})
            tool_name = function.get("name", "")
            tool_description = function.get("description", "")
            tool_parameters = function.get("parameters", {})

            logger.debug("[TOOLS_SCHEMA]   - Converting OpenAI function tool")
            logger.debug(f"[TOOLS_SCHEMA]     - Name: {tool_name}")
            logger.debug(f"[TOOLS_SCHEMA]     - Description: {tool_description}")
            logger.debug(f"[TOOLS_SCHEMA]     - Parameters schema: {json.dumps(tool_parameters, indent=2)}")

            anthropic_tool = {
                "name": tool_name,
                "description": tool_description,
                "input_schema": tool_parameters
            }

            logger.debug(f"[TOOLS_SCHEMA]   - Converted to Anthropic tool: {json.dumps(anthropic_tool, indent=2)}")
            anthropic_tools.append(anthropic_tool)
        else:
            logger.warning(f"[TOOLS_SCHEMA]   - Unknown tool format (skipping): {json.dumps(tool, indent=2)}")

    logger.debug(f"[TOOLS_SCHEMA] Final Anthropic tools: {json.dumps(anthropic_tools, indent=2)}")
    return anthropic_tools if anthropic_tools else None


def convert_openai_functions_to_anthropic(openai_functions: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    """Convert OpenAI functions (legacy) to Anthropic tools format."""
    if not openai_functions:
        return None

    anthropic_tools = []

    for func in openai_functions:
        anthropic_tools.append({
            "name": func.get("name", ""),
            "description": func.get("description", ""),
            "input_schema": func.get("parameters", {})
        })

    return anthropic_tools if anthropic_tools else None
