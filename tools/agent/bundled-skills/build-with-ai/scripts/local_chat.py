#!/usr/bin/env python3
"""Call the local llama-server OpenAI-compatible HTTP API. Python standard library only."""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading


DEFAULT_BASE = "http://127.0.0.1:8080"


def resolve_base(value):
    raw = (value or os.environ.get("LLAMA_SERVER_URL") or DEFAULT_BASE).strip()
    return raw.rstrip("/")


def assert_allowed(base, allow_remote):
    host = (urllib.parse.urlparse(base).hostname or "").lower()
    if host in {"127.0.0.1", "localhost", "::1"}:
        return
    if allow_remote:
        return
    raise SystemExit(
        "refusing non-loopback URL %s; pass the URL the user gave and add --allow-remote" % base
    )


def http_request(url, method="GET", payload=None, timeout=30):
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status, res.read()
    except urllib.error.HTTPError as exc:
        body = exc.read()
        raise SystemExit("HTTP %s from %s: %s" % (exc.code, url, body.decode("utf-8", "replace")[:500]))
    except urllib.error.URLError as exc:
        raise SystemExit(
            "cannot reach %s (%s). Start llama-server, or pass --base-url / set LLAMA_SERVER_URL. "
            "If this agent already occupies the only server slot, do not call complete in this turn; "
            "write the application against the local API instead."
            % (url, exc.reason)
        )


def model_id(base, timeout):
    _status, body = http_request(base + "/v1/models", timeout=timeout)
    data = json.loads(body.decode("utf-8"))
    items = data.get("data") or []
    if not items or not isinstance(items[0], dict) or not items[0].get("id"):
        raise SystemExit("/v1/models did not return a model id")
    return items[0]["id"]


def chat_payload(model, prompt, stream):
    return {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": bool(stream),
    }


def read_completion(body):
    data = json.loads(body.decode("utf-8"))
    choices = data.get("choices") or []
    if not choices:
        raise SystemExit("completion response had no choices")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not isinstance(content, str):
        raise SystemExit("completion response had no message content")
    return content


def read_stream(response_bytes):
    parts = []
    for line in response_bytes.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            break
        event = json.loads(payload)
        for choice in event.get("choices") or []:
            delta = choice.get("delta") or {}
            text = delta.get("content")
            if isinstance(text, str):
                parts.append(text)
    if not parts:
        raise SystemExit("stream ended without content")
    return "".join(parts)


def cmd_probe(args):
    base = resolve_base(args.base_url)
    assert_allowed(base, args.allow_remote)
    props_status, props_body = http_request(base + "/props", timeout=args.timeout)
    mid = model_id(base, args.timeout)
    props = json.loads(props_body.decode("utf-8"))
    print(json.dumps({
        "base_url": base,
        "props_status": props_status,
        "model_id": mid,
        "model_path": props.get("model_path") or props.get("default_generation_settings", {}).get("model"),
        "chat_completions": base + "/v1/chat/completions",
    }, indent=2))


def cmd_complete(args):
    base = resolve_base(args.base_url)
    assert_allowed(base, args.allow_remote)
    prompt = args.prompt
    if prompt is None:
        prompt = sys.stdin.read()
    if not prompt.strip():
        raise SystemExit("prompt is empty")
    mid = args.model or model_id(base, args.timeout)
    payload = chat_payload(mid, prompt, args.stream)
    if args.stream:
        _status, body = http_request(base + "/v1/chat/completions", "POST", payload, args.timeout)
        sys.stdout.write(read_stream(body))
        sys.stdout.write("\n")
        return
    _status, body = http_request(base + "/v1/chat/completions", "POST", payload, args.timeout)
    sys.stdout.write(read_completion(body))
    sys.stdout.write("\n")


class _FakeHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _send(self, code, body, content_type="application/json"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/props":
            self._send(200, json.dumps({"model_path": "fixture.gguf"}))
            return
        if self.path == "/v1/models":
            self._send(200, json.dumps({"object": "list", "data": [{"id": "fixture", "object": "model"}]}))
            return
        self._send(404, "{}")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        payload = json.loads(raw.decode("utf-8"))
        if payload.get("model") != "fixture":
            self._send(400, json.dumps({"error": "unexpected model"}))
            return
        text = payload["messages"][0]["content"]
        if payload.get("stream"):
            chunk = {
                "choices": [{"delta": {"content": "echo:" + text}}],
            }
            body = "data: %s\n\ndata: [DONE]\n" % json.dumps(chunk)
            self._send(200, body, "text/event-stream")
            return
        self._send(200, json.dumps({
            "choices": [{"message": {"role": "assistant", "content": "echo:" + text}}],
        }))


def self_test():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = "http://127.0.0.1:%d" % server.server_address[1]
    try:
        probe = argparse.Namespace(base_url=base, allow_remote=False, timeout=5)
        cmd_probe(probe)
        complete = argparse.Namespace(
            base_url=base, allow_remote=False, timeout=5, prompt="ping", model=None, stream=False)
        cmd_complete(complete)
        streamed = argparse.Namespace(
            base_url=base, allow_remote=False, timeout=5, prompt="ping", model=None, stream=True)
        cmd_complete(streamed)
        try:
            assert_allowed("http://example.com", False)
        except SystemExit:
            pass
        else:
            raise SystemExit("remote URL was accepted")
    finally:
        server.shutdown()
    print("self-test ok")


def main(argv):
    if argv and argv[0] == "--self-test":
        self_test()
        return 0
    parser = argparse.ArgumentParser(description="Call a local llama-server")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--allow-remote", action="store_true")
    parser.add_argument("--timeout", type=float, default=30)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("probe")
    complete = sub.add_parser("complete")
    complete.add_argument("--prompt", default=None)
    complete.add_argument("--model", default=None)
    complete.add_argument("--stream", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "probe":
        cmd_probe(args)
    else:
        cmd_complete(args)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
