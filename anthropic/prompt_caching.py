"""Prompt caching functionality for Anthropic API"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def count_existing_cache_controls(request_data: Dict[str, Any]) -> int:
    """Count existing cache_control blocks in the request

    Args:
        request_data: Request data dictionary

    Returns:
        Number of existing cache_control blocks
    """
    count = 0

    # Count in tools (first in cache hierarchy)
    if 'tools' in request_data:
        tools = request_data['tools']
        if isinstance(tools, list):
            for tool in tools:
                if isinstance(tool, dict) and 'cache_control' in tool:
                    count += 1

    # Count in system message
    if 'system' in request_data:
        system = request_data['system']
        if isinstance(system, list):
            for block in system:
                if isinstance(block, dict) and 'cache_control' in block:
                    count += 1

    # Count in messages
    if 'messages' in request_data:
        for message in request_data['messages']:
            content = message.get('content')
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and 'cache_control' in block:
                        count += 1

    return count


def add_prompt_caching(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add prompt caching breakpoints following Anthropic's best practices

    Strategy:
    - Add cache_control to tools (if present) - mark the last tool
    - Add cache_control to system message (if present)
    - Add cache_control to the last 2 user messages to cache recent conversation
    - Only mark the last content block in each cached message
    - Respect Anthropic's limit of 4 cache_control blocks maximum
    - Follow cache hierarchy: tools → system → messages

    Anthropic prompt caching docs: https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching

    Args:
        request_data: Request data dictionary

    Returns:
        Modified request data with prompt caching added
    """
    modified_request = request_data.copy()
    MAX_CACHE_BLOCKS = 4

    # Count existing cache_control blocks
    existing_count = count_existing_cache_controls(modified_request)
    cache_added_count = 0

    if existing_count >= MAX_CACHE_BLOCKS:
        logger.debug(f"Request already has {existing_count} cache_control blocks (max: {MAX_CACHE_BLOCKS}), skipping auto-caching")
        return modified_request

    remaining_slots = MAX_CACHE_BLOCKS - existing_count
    logger.debug(f"Found {existing_count} existing cache_control blocks, {remaining_slots} slots available")

    # Add cache_control to tools (first in cache hierarchy)
    # Only mark the last tool - Anthropic automatically caches all tools before it
    if 'tools' in modified_request and remaining_slots > 0:
        tools = modified_request['tools']
        if isinstance(tools, list) and len(tools) > 0:
            # Mark the last tool for caching
            last_tool = tools[-1]
            if isinstance(last_tool, dict) and 'cache_control' not in last_tool:
                last_tool['cache_control'] = {'type': 'ephemeral'}
                cache_added_count += 1
                remaining_slots -= 1
                logger.debug(f"Added cache_control to tools (last tool: {last_tool.get('name', 'unknown')})")

    # Add cache_control to system message if present and we have room
    if 'system' in modified_request and remaining_slots > 0:
        system = modified_request['system']

        # System can be a string or array of content blocks
        if isinstance(system, list) and len(system) > 0:
            # Mark the last system block for caching
            last_block = system[-1]
            if isinstance(last_block, dict) and 'cache_control' not in last_block:
                last_block['cache_control'] = {'type': 'ephemeral'}
                cache_added_count += 1
                remaining_slots -= 1
                logger.debug("Added cache_control to system message (last block)")
        elif isinstance(system, str):
            # Convert string system to array format with cache_control
            modified_request['system'] = [
                {
                    'type': 'text',
                    'text': system,
                    'cache_control': {'type': 'ephemeral'}
                }
            ]
            cache_added_count += 1
            remaining_slots -= 1
            logger.debug("Added cache_control to system message (converted from string)")

    # Add cache_control to the last 2 user messages for conversation caching
    if 'messages' in modified_request and remaining_slots > 0:
        messages = modified_request['messages']

        # Find the last 2 user messages
        user_message_indices = [i for i, msg in enumerate(messages) if msg.get('role') == 'user']

        # Cache the last 2 user messages (or fewer if there aren't 2 or we don't have room)
        num_to_cache = min(2, len(user_message_indices), remaining_slots)
        cache_indices = user_message_indices[-num_to_cache:] if num_to_cache > 0 else []

        for idx in cache_indices:
            if remaining_slots <= 0:
                break

            message = messages[idx]
            content = message.get('content')

            if isinstance(content, list) and len(content) > 0:
                # Mark the last content block for caching
                last_block = content[-1]
                if isinstance(last_block, dict) and 'cache_control' not in last_block:
                    last_block['cache_control'] = {'type': 'ephemeral'}
                    cache_added_count += 1
                    remaining_slots -= 1
            elif isinstance(content, str):
                # Convert string content to array format with cache_control
                messages[idx]['content'] = [
                    {
                        'type': 'text',
                        'text': content,
                        'cache_control': {'type': 'ephemeral'}
                    }
                ]
                cache_added_count += 1
                remaining_slots -= 1

    if cache_added_count > 0:
        total_count = existing_count + cache_added_count
        logger.debug(f"Added prompt caching to {cache_added_count} locations (total: {total_count}/{MAX_CACHE_BLOCKS})")

    return modified_request
