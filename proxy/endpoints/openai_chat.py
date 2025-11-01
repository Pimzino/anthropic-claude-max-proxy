"""
OpenAI-compatible chat completions endpoint.
"""
import json
import logging
import time
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from oauth import OAuthManager
from models import is_custom_model, is_chatgpt_model, get_custom_model_config
from chatgpt_oauth import ChatGPTOAuthManager
from providers.chatgpt_provider import ChatGPTProvider
import settings
from stream_debug import maybe_create_stream_tracer
from anthropic import make_anthropic_request
from openai_compat import convert_anthropic_response_to_openai
from ..models import OpenAIChatCompletionRequest
from ..handlers import (
    prepare_anthropic_request,
    create_openai_stream,
    handle_custom_provider_request,
    handle_custom_provider_stream,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Global instances
oauth_manager = OAuthManager()
chatgpt_oauth_manager = ChatGPTOAuthManager()


@router.post("/v1/chat/completions")
async def openai_chat_completions(request: OpenAIChatCompletionRequest, raw_request: Request):
    """OpenAI-compatible chat completions endpoint"""
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    logger.info(f"[{request_id}] ===== NEW OPENAI CHAT COMPLETION REQUEST =====")

    # Log the raw request data with full detail
    request_dict = request.model_dump()
    logger.debug(f"[{request_id}] ===== RAW CLIENT REQUEST (FULL DETAIL) =====")
    logger.debug(f"[{request_id}] Model: {request_dict.get('model')}")
    logger.debug(f"[{request_id}] Stream: {request_dict.get('stream')}")
    logger.debug(f"[{request_id}] Max tokens: {request_dict.get('max_tokens')}")
    logger.debug(f"[{request_id}] Temperature: {request_dict.get('temperature')}")

    # Log messages in detail
    messages = request_dict.get('messages', [])
    logger.debug(f"[{request_id}] Messages ({len(messages)} total):")
    for idx, msg in enumerate(messages):
        logger.debug(f"[{request_id}]   Message #{idx}: role={msg.get('role')}, content_type={type(msg.get('content'))}")
        if isinstance(msg.get('content'), str):
            content_preview = msg.get('content', '')[:200]
            logger.debug(f"[{request_id}]     Content (preview): {content_preview}...")
        elif isinstance(msg.get('content'), list):
            logger.debug(f"[{request_id}]     Content (array with {len(msg.get('content', []))} items): {json.dumps(msg.get('content'), indent=2)}")

        # Log tool_calls if present
        if 'tool_calls' in msg:
            logger.debug(f"[{request_id}]     Tool calls: {json.dumps(msg['tool_calls'], indent=2)}")

        # Log tool_call_id if present (for tool result messages)
        if 'tool_call_id' in msg:
            logger.debug(f"[{request_id}]     Tool call ID: {msg['tool_call_id']}")

    # Log tools in detail
    if 'tools' in request_dict and request_dict['tools']:
        logger.debug(f"[{request_id}] Tools ({len(request_dict['tools'])} total):")
        for idx, tool in enumerate(request_dict['tools']):
            logger.debug(f"[{request_id}]   Tool #{idx}: {json.dumps(tool, indent=2)}")
    else:
        logger.debug(f"[{request_id}] No tools in request")

    # Log tool_choice if present
    if 'tool_choice' in request_dict:
        logger.debug(f"[{request_id}] Tool choice: {json.dumps(request_dict['tool_choice'], indent=2)}")

    # Log full request as JSON for complete reference
    logger.debug(f"[{request_id}] Full request JSON: {json.dumps(request_dict, indent=2)}")
    logger.debug(f"[{request_id}] ===== END RAW CLIENT REQUEST =====")

    logger.debug(f"[{request_id}] OpenAI Request: {request.model_dump()}")

    # Log HTTP headers to see if client is sending anthropic-beta
    headers_dict = dict(raw_request.headers)
    if "anthropic-beta" in headers_dict:
        logger.warning(f"[{request_id}] Client sent anthropic-beta header: {headers_dict['anthropic-beta']}")
    logger.debug(f"[{request_id}] All HTTP headers from client: {dict(raw_request.headers)}")

    # Log model routing decision
    is_custom = is_custom_model(request.model)
    is_chatgpt = is_chatgpt_model(request.model)

    if is_chatgpt:
        logger.info(f"[{request_id}] Model: {request.model} | ChatGPT: True | Routing to: ChatGPT Responses API")
    elif is_custom:
        logger.info(f"[{request_id}] Model: {request.model} | Custom: True | Routing to: custom provider")
    else:
        logger.info(f"[{request_id}] Model: {request.model} | Routing to: Anthropic")

    # Check if this is a ChatGPT model
    if is_chatgpt_model(request.model):
        logger.info(f"[{request_id}] Routing to ChatGPT for model: {request.model}")

        try:
            # Create ChatGPT provider
            chatgpt_provider = ChatGPTProvider(oauth_manager=chatgpt_oauth_manager)

            # Pass request directly to ChatGPT provider (handles OpenAI → Responses API conversion)
            openai_request_dict = request.model_dump()

            if request.stream:
                # Handle streaming response
                logger.debug(f"[{request_id}] Initiating streaming request to ChatGPT")

                tracer = maybe_create_stream_tracer(
                    enabled=settings.STREAM_TRACE_ENABLED,
                    request_id=request_id,
                    route="chatgpt",
                    base_dir=settings.STREAM_TRACE_DIR,
                    max_bytes=settings.STREAM_TRACE_MAX_BYTES,
                )

                async def chatgpt_stream_generator():
                    try:
                        async for chunk in chatgpt_provider.stream_response(
                            openai_request_dict,
                            request_id,
                            tracer=tracer
                        ):
                            yield chunk
                    except Exception as e:
                        logger.error(f"[{request_id}] ChatGPT stream error: {e}", exc_info=True)
                        error_chunk = f'data: {{"error": {{"message": "ChatGPT stream error: {str(e)}"}}}}\n\n'
                        yield error_chunk
                    finally:
                        if tracer:
                            tracer.close()

                return StreamingResponse(
                    chatgpt_stream_generator(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                    }
                )

            else:
                # Handle non-streaming response
                logger.debug(f"[{request_id}] Initiating non-streaming request to ChatGPT")

                response = await chatgpt_provider.make_request(
                    openai_request_dict,
                    request_id
                )

                if response.status_code != 200:
                    error_body = response.json() if response.content else {"error": {"message": "ChatGPT API error"}}
                    logger.error(f"[{request_id}] ChatGPT error {response.status_code}: {error_body}")
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=error_body
                    )

                # Return ChatGPT response directly (already in OpenAI format)
                return response.json()

        except ValueError as e:
            # OAuth credential error
            logger.error(f"[{request_id}] ChatGPT OAuth error: {e}")
            raise HTTPException(
                status_code=401,
                detail={"error": {"message": str(e)}}
            )
        except Exception as e:
            logger.error(f"[{request_id}] ChatGPT request failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail={"error": {"message": f"ChatGPT request failed: {str(e)}"}}
            )

    # Check if this is a custom model (non-Anthropic)
    if is_custom_model(request.model):
        logger.info(f"[{request_id}] Routing to custom provider for model: {request.model}")

        # Get custom model configuration
        model_config = get_custom_model_config(request.model)
        if not model_config:
            logger.error(f"[{request_id}] Custom model config not found: {request.model}")
            raise HTTPException(
                status_code=400,
                detail={"error": {"message": f"Custom model '{request.model}' not properly configured"}}
            )

        base_url = model_config["base_url"]
        api_key = model_config["api_key"]

        try:
            # Pass request directly to custom provider (no Anthropic conversion)
            openai_request_dict = request.model_dump()

            if request.stream:
                # Handle streaming response
                logger.debug(f"[{request_id}] Initiating streaming request to custom provider")

                tracer = maybe_create_stream_tracer(
                    enabled=settings.STREAM_TRACE_ENABLED,
                    request_id=request_id,
                    route="custom-provider",
                    base_dir=settings.STREAM_TRACE_DIR,
                    max_bytes=settings.STREAM_TRACE_MAX_BYTES,
                )

                async def custom_stream():
                    try:
                        async for chunk in handle_custom_provider_stream(
                            openai_request_dict,
                            base_url,
                            api_key,
                            request_id,
                            tracer=tracer,
                        ):
                            yield chunk
                    finally:
                        if tracer:
                            tracer.close()

                return StreamingResponse(
                    custom_stream(),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
                )
            else:
                # Handle non-streaming response
                logger.debug(f"[{request_id}] Making non-streaming request to custom provider")
                response = await handle_custom_provider_request(
                    openai_request_dict,
                    base_url,
                    api_key,
                    request_id
                )

                elapsed_ms = int((time.time() - start_time) * 1000)
                logger.info(f"[{request_id}] Custom provider request completed in {elapsed_ms}ms status={response.status_code}")

                if response.status_code != 200:
                    # Return error in OpenAI format
                    try:
                        error_json = response.json()
                    except Exception:
                        error_json = {
                            "error": {
                                "message": response.text,
                                "type": "api_error",
                                "code": response.status_code
                            }
                        }

                    logger.error(f"[{request_id}] Custom provider error {response.status_code}: {error_json}")
                    raise HTTPException(status_code=response.status_code, detail=error_json)

                # Return response as-is (already in OpenAI format)
                openai_response = response.json()

                final_elapsed_ms = int((time.time() - start_time) * 1000)
                logger.info(f"[{request_id}] ===== CUSTOM PROVIDER COMPLETION FINISHED ===== Total time: {final_elapsed_ms}ms")
                return openai_response

        except HTTPException:
            final_elapsed_ms = int((time.time() - start_time) * 1000)
            logger.error(f"[{request_id}] ===== CUSTOM PROVIDER COMPLETION FAILED ===== Total time: {final_elapsed_ms}ms")
            raise
        except Exception as e:
            final_elapsed_ms = int((time.time() - start_time) * 1000)
            logger.error(f"[{request_id}] Custom provider request failed after {final_elapsed_ms}ms: {e}")
            logger.exception(f"[{request_id}] Full traceback:")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": {
                        "message": str(e),
                        "type": "internal_error",
                        "code": 500
                    }
                }
            )

    # Get valid access token with automatic refresh (for Anthropic models)
    access_token = await oauth_manager.get_valid_token_async()
    if not access_token:
        logger.error(f"[{request_id}] No valid token available")
        raise HTTPException(
            status_code=401,
            detail={"error": {"message": "OAuth expired; please authenticate using the CLI"}}
        )

    try:
        # Convert OpenAI request to Anthropic format
        openai_request_dict = request.model_dump()
        anthropic_request = prepare_anthropic_request(
            openai_request_dict,
            request_id,
            is_native_anthropic=False
        )

        logger.debug(f"[{request_id}] Final Anthropic request (after adding prompt caching): {json.dumps(anthropic_request, indent=2)}")

        # Extract client beta headers
        client_beta_headers = headers_dict.get("anthropic-beta")

        if request.stream:
            # Handle streaming response
            logger.debug(f"[{request_id}] Initiating streaming request (OpenAI format)")

            tracer = maybe_create_stream_tracer(
                enabled=settings.STREAM_TRACE_ENABLED,
                request_id=request_id,
                route="openai-chat",
                base_dir=settings.STREAM_TRACE_DIR,
                max_bytes=settings.STREAM_TRACE_MAX_BYTES,
            )

            async def stream_with_conversion():
                """Wrapper to convert Anthropic stream to OpenAI format"""
                try:
                    async for chunk in create_openai_stream(
                        request_id,
                        anthropic_request,
                        access_token,
                        client_beta_headers,
                        request.model,
                        tracer=tracer,
                    ):
                        yield chunk
                finally:
                    if tracer:
                        tracer.close()

            return StreamingResponse(
                stream_with_conversion(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
            )
        else:
            # Handle non-streaming response
            logger.debug(f"[{request_id}] Making non-streaming request (OpenAI format)")
            response = await make_anthropic_request(anthropic_request, access_token, client_beta_headers)

            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(f"[{request_id}] Anthropic request completed in {elapsed_ms}ms status={response.status_code}")

            if response.status_code != 200:
                # Return error in OpenAI format
                try:
                    error_json = response.json()
                    # Convert to OpenAI error format
                    openai_error = {
                        "error": {
                            "message": error_json.get("error", {}).get("message", "Unknown error"),
                            "type": error_json.get("error", {}).get("type", "api_error"),
                            "code": response.status_code
                        }
                    }
                except Exception:
                    openai_error = {
                        "error": {
                            "message": response.text,
                            "type": "api_error",
                            "code": response.status_code
                        }
                    }

                logger.error(f"[{request_id}] Anthropic API error {response.status_code}: {json.dumps(openai_error)}")
                raise HTTPException(status_code=response.status_code, detail=openai_error)

            # Convert Anthropic response to OpenAI format
            anthropic_response = response.json()
            openai_response = convert_anthropic_response_to_openai(anthropic_response, request.model)

            final_elapsed_ms = int((time.time() - start_time) * 1000)

            # Log usage information for debugging
            usage_info = openai_response.get("usage", {})
            prompt_tokens = usage_info.get("prompt_tokens", 0)
            completion_tokens = usage_info.get("completion_tokens", 0)
            total_tokens = usage_info.get("total_tokens", 0)
            logger.debug(f"[{request_id}] [DEBUG] Response usage: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}")

            logger.info(f"[{request_id}] ===== OPENAI CHAT COMPLETION FINISHED ===== Total time: {final_elapsed_ms}ms")
            return openai_response

    except HTTPException:
        final_elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error(f"[{request_id}] ===== OPENAI CHAT COMPLETION FAILED ===== Total time: {final_elapsed_ms}ms")
        raise
    except Exception as e:
        final_elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error(f"[{request_id}] Request failed after {final_elapsed_ms}ms: {e}")
        logger.exception(f"[{request_id}] Full traceback:")
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "message": str(e),
                    "type": "internal_error",
                    "code": 500
                }
            }
        )
