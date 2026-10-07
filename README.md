# Hyperion

Hyperion is the assistant for the [HyperAI IDE](https://ide.hyperai.di.uoa.gr/). It is a FastAPI service on port **8000**. The IDE posts each chat turn to `POST /chat` and reads a stream of Server-Sent Events.

The model is `llama3.1` through an OpenAI-compatible API. `API_KEY`, `BASE_URL`, and `MODEL` come from the environment (see `.env.example`). Retrieval uses `nomic-embed-text` on that same server (`EMBED_MODEL` overrides it).

## What it does

Each message is classified, then handled in code:

- **HYPER-AI questions** are answered only from the documents in `knowledge/` (project deliverables and the IDE's native-app and device-app specs). Keyword search and embeddings are combined. If the documents do not contain the answer, Hyperion says it does not know.
- **Anything else** (weather, news, jokes, prompt injection) gets one fixed refusal and does not call the model.
- **Greetings and this conversation** are answered normally. Memory is per `user_id`, in the running process, and keeps the last 10 messages.
- **File requests** create, show, validate, or delete a file in the IDE workspace. A service becomes a native application profile. A phone, Android APK, or ESP32 becomes a device manifest. The image, tag, and port are taken from the sentence. The IDE validator checks the file. Delete and overwrite wait until the user replies yes or no.

File changes are IDE actions in the stream, not chat text:

```
data: {"action": "edit_file", "path": "nginx.yaml", "content": "..."}

data: {"action": "delete_file", "path": "nginx.yaml"}
```

`agent/tools/ide_client.py` calls the IDE backend. From inside the agent container that address is `http://host.docker.internal:3001/api`.

## Code layout

```
main.py              HTTP only: POST /chat streams SSE from agent.generate_reply
agent/
  chat.py            the flow for one message: pending yes/no, route, reply
  router.py          classifies a message into hyperai | ide_action | chitchat | off_topic
  memory.py          last 10 messages per user_id, one lock per user
  prompts.py         every prompt and fixed reply
  config.py          environment variables and limits
  llm.py             the chat, router and tool LLM clients
  sse.py             SSE event formatting
  tools/             IDE actions: planner, IDE HTTP client, file ops, confirmation
  templates/         YAML templates, service catalogue, sentence parsing, rendering
rag/
  retriever.py       BM25 + embeddings, fused by rank
  chunking.py        knowledge/*.md into chunks
  embeddings.py      POST /embeddings on the LLM server
  text.py            tokenizing, stopwords.py, fusion.py, config.py
knowledge/           the documents Hyperion answers from
```

## Run it

Start the IDE, then the agent. One terminal each:

```bash
docker run --rm -p 3001:3001 -e AUTH_ENABLED=false --name ide-backend donmichael/ide-backend:latest
docker run --rm -p 5000:80 --name ide-gui donmichael/ide-gui:latest
docker compose up --build
```

Open <http://localhost:5000/> and use the robot icon. The agent is at <http://localhost:8000/>.

```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "123e4567-e89b-12d3-a456-426614174000", "text": "What is a DeviceNode?"}'
```

The browser calls this service directly, so the CORS middleware in `main.py` stays enabled.

## The chat protocol

The IDE sends:

```json
{ "user_id": "...", "text": "..." }
```

`user_id` is a UUID from the IDE. `text` is what the user typed.

Each event is a `data:` line, a JSON object, and a blank line. A `response` value is only the new text, which the IDE appends. An `action` value is performed in the IDE and is not shown as chat text. The stream ends with `data: [DONE]`.

```
data: {"response": "Wrote nginx.yaml"}

data: {"action": "edit_file", "path": "nginx.yaml", "content": "..."}

data: [DONE]
```

## License

[Apache 2.0](LICENCE)
