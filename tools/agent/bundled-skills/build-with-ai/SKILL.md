---
name: build-with-ai
description: Wire an application to the local llama-server OpenAI-compatible API on loopback (GET /props, GET /v1/models, POST /v1/chat/completions). Use when adding a chatbot, completions, streaming, or any LLM call. Run scripts/local_chat.py. Triggers include add a chatbot, call an LLM, integrate AI, and which model.
license: MIT
compatibility: python3. Talks only to a loopback llama-server unless the user names another URL.
allowed-tools: bash read write edit glob
---

# Local model API

The model serving this session is reached through llama-server. Applications call that HTTP API. Do not add a cloud SDK, an API key, or a hosted model name.

## Find the server

1. Use the URL the user gave with `--server-url` or `LLAMA_SERVER_URL`.
2. Otherwise use `http://127.0.0.1:8080`, which is llama-server's default.
3. Run `python3 <skill_dir>/scripts/local_chat.py probe`. `<skill_dir>` is the directory that contains this file.
4. Read `model_id` from the probe JSON. Pass that id as the `model` field. Do not invent one.

Refuse a non-loopback host unless the user wrote that URL. Then add `--allow-remote`.

## Call shape

`POST /v1/chat/completions`

```json
{"model":"<model_id>","messages":[{"role":"user","content":"..."}],"stream":false}
```

Streaming is the same path with `"stream": true` and `data:` lines ending in `data: [DONE]`. The script implements both:

```bash
python3 <skill_dir>/scripts/local_chat.py complete --prompt "ping"
python3 <skill_dir>/scripts/local_chat.py complete --stream --prompt "ping"
```

If this agent is already generating on a server started with one slot, `complete` can sit until timeout. On that timeout, stop calling the server and write the application code instead. Probe is safe.

## What to write in the app

Use the language of the application. Prefer the standard library (`urllib` in Python, `fetch` in the browser only when the page is allowed to call loopback). Point the base URL at the server above. Read `/v1/models` at startup and use the returned id. Surface the server error body when the status is not 2xx.

Do not vendor a client for a hosted provider. Do not put a secret in the repo. The local server does not need a bearer token.

After the code is written, run the project's existing check. If the server from the probe is free, run one `complete` call and show the reply.
