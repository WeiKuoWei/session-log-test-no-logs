"""Model providers. AnthropicProvider is the real call path (Messages API over HTTPS, stdlib only);
MockProvider returns canned, API-shaped responses from mock/extractions.json and never touches the network."""
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from .config import API_KEY_ENV
from .extraction import TOOL_NAME


class ProviderError(Exception):
    """kind: rate_limited | unavailable | timeout | network | auth | bad_request | no_credentials"""

    def __init__(self, kind, message, retryable=False, retry_after=None):
        super().__init__(message)
        self.kind, self.retryable, self.retry_after = kind, retryable, retry_after


def redact(text):
    text = re.sub(r"sk-ant-[A-Za-z0-9_\-]+", "[REDACTED]", str(text))
    key = os.environ.get(API_KEY_ENV)
    return text.replace(key, "[REDACTED]") if key else text


def request_headers(config, api_key):
    return {"x-api-key": api_key, "anthropic-version": config["anthropic_version"],
            "content-type": "application/json"}


class AnthropicProvider:
    mocked = False

    def __init__(self, config, opener=urllib.request.urlopen):
        self.config, self.opener = config, opener

    def send(self, payload):
        key = os.environ.get(API_KEY_ENV)
        if not key:
            raise ProviderError("no_credentials", f"environment variable {API_KEY_ENV} is not set")
        req = urllib.request.Request(
            self.config["api_base"].rstrip("/") + "/v1/messages",
            data=json.dumps(payload).encode(), headers=request_headers(self.config, key), method="POST")
        try:
            with self.opener(req, timeout=self.config["timeout_seconds"]) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise self._http_error(e) from None
        except TimeoutError:
            raise ProviderError("timeout", "request timed out", retryable=True) from None
        except urllib.error.URLError as e:
            raise ProviderError("network", redact(f"network error: {e.reason}"), retryable=True) from None
        except json.JSONDecodeError:
            raise ProviderError("unavailable", "provider returned a non-JSON body", retryable=True) from None

    @staticmethod
    def _http_error(e):
        try:
            detail = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:
            detail = ""
        text = redact(f"HTTP {e.code}: {detail}".strip())
        retry_after = None
        try:
            retry_after = float(e.headers.get("retry-after")) if e.headers else None
        except (TypeError, ValueError):
            pass
        if e.code == 429:
            return ProviderError("rate_limited", text, True, retry_after)
        if e.code in (500, 502, 503, 504, 529):
            return ProviderError("unavailable", text, True, retry_after)
        if e.code in (401, 403):
            return ProviderError("auth", text)
        return ProviderError("bad_request", text)


class MockProvider:
    mocked = True

    def __init__(self, config, fixtures_path="mock/extractions.json"):
        self.config = config
        self.fixtures = json.loads(Path(fixtures_path).read_text(encoding="utf-8"))

    def send(self, payload):
        match = re.search(r"Document id: (\S+)", payload["messages"][0]["content"])
        doc = match.group(1) if match else None
        if doc not in self.fixtures:
            raise ProviderError("bad_request", f"no mock response recorded for {doc}")
        return mock_response(self.config["model"], self.fixtures[doc])


def mock_response(model, extraction, stop_reason="tool_use"):
    return {"id": "msg_mock", "type": "message", "role": "assistant", "model": model,
            "content": [{"type": "tool_use", "id": "toolu_mock", "name": TOOL_NAME, "input": extraction}],
            "stop_reason": stop_reason, "usage": {"input_tokens": 0, "output_tokens": 0}, "mocked": True}


def make_provider(config):
    if config["provider"] == "anthropic":
        return AnthropicProvider(config)
    if config["provider"] == "mock":
        return MockProvider(config)
    raise ValueError(f"unknown provider {config['provider']!r} (use anthropic or mock)")
