"""Credential-redacted example request plus the response handling the code implements."""
import json
from pathlib import Path

from .extraction import SYSTEM_PROMPT, TOOL, build_request, prompt_version, user_message
from .provider import mock_response, request_headers

HANDLING = {
    "success": "stop_reason tool_use (or end_turn) with exactly one record_extraction block; its input must validate "
               "against snapshot.schema.json, dates must be real YYYY-MM-DD, every supporting quote must be an exact "
               "substring of the message. Then policy routing runs.",
    "refusal": "stop_reason refusal -> record status error, next_action retry-extraction, error 'refusal: ...'",
    "interrupted": "stop_reason max_tokens / pause_turn / model_context_window_exceeded -> error 'interrupted: ...'",
    "malformed": "no or several tool calls, schema violation, bad date, quote not in message, unreadable input -> error 'malformed: ...'",
    "provider_errors": "HTTP 429 (rate_limited), 500/502/503/504/529 (unavailable), timeout, network: retried up to "
                       "max_attempts with exponential backoff, honouring the retry-after header; then error "
                       "'provider <kind>: ...'. HTTP 401/403 (auth), other 4xx (bad_request) and a missing "
                       "ANTHROPIC_API_KEY are not retried.",
    "after_error": "The record keeps extraction null and the error; the last valid result stays in history and is "
                   "shown as previous_valid, labelled with its own attempt number and source hash.",
}


def build_evidence(config, message_path="materials/requests/IT-001.json"):
    message = json.loads(Path(message_path).read_text(encoding="utf-8"))["message"]
    doc = Path(message_path).name
    headers = request_headers(config, "[REDACTED: read from environment variable ANTHROPIC_API_KEY]")
    mock = json.loads(Path("mock/extractions.json").read_text(encoding="utf-8"))[doc]
    return {
        "label": "Example request construction for materials/requests/IT-001.json. Nothing was sent; no API key was "
                 "available. The response shown is MOCKED.",
        "endpoint": config["api_base"].rstrip("/") + "/v1/messages",
        "method": "POST",
        "headers": headers,
        "configuration": {k: config.get(k) for k in ("provider", "model", "max_tokens", "temperature", "timeout_seconds",
                                                      "max_attempts", "backoff_seconds", "workers", "anthropic_version")},
        "prompt_version": prompt_version(),
        "body": build_request(config, doc, message),
        "response_handling": HANDLING,
        "mocked_response_example": mock_response(config["model"], mock),
        "live_response_example": None,
    }
