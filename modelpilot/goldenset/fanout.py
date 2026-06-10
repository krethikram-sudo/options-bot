"""Fan a prompt corpus out across candidate models via the Batch API.

Batches run at 50% of list price and the golden set is exactly the
non-latency-sensitive workload they're for.

prompts.jsonl rows: {"id": str, "prompt": str,
                     "category": str (optional),
                     "expected": str (optional — enables programmatic grading)}
"""

import json

CANDIDATE_MODELS = ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-8"]
DEFAULT_MAX_TOKENS = 2048


def load_jsonl(path: str) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def dump_jsonl(rows: list[dict], path: str):
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def build_requests(prompts: list[dict], models: list[str] = CANDIDATE_MODELS,
                   max_tokens: int = DEFAULT_MAX_TOKENS) -> list[dict]:
    """One batch request per (prompt, model). custom_id encodes both.

    The API restricts custom_id to ^[a-zA-Z0-9_-]{1,64}$, so the separator is
    "__" — prompt ids therefore must not contain a double underscore.
    """
    requests = []
    for p in prompts:
        for model in models:
            requests.append({
                "custom_id": f"{p['id']}__{model}",
                "params": {
                    "model": model,
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": p["prompt"]}],
                },
            })
    return requests


def submit(client, prompts: list[dict], models: list[str] = CANDIDATE_MODELS,
           max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    batch = client.messages.batches.create(requests=build_requests(prompts, models, max_tokens))
    return batch.id


def collect(client, batch_id: str) -> list[dict]:
    """Collect a finished batch into output rows. Raises if still processing."""
    batch = client.messages.batches.retrieve(batch_id)
    if batch.processing_status != "ended":
        raise RuntimeError(f"batch {batch_id} still {batch.processing_status}")
    rows = []
    for result in client.messages.batches.results(batch_id):
        prompt_id, model = result.custom_id.split("__", 1)
        if result.result.type != "succeeded":
            rows.append({"prompt_id": prompt_id, "model": model, "error": result.result.type})
            continue
        msg = result.result.message
        text = next((b.text for b in msg.content if b.type == "text"), "")
        rows.append({
            "prompt_id": prompt_id,
            "model": model,
            "text": text,
            "input_tokens": msg.usage.input_tokens,
            "output_tokens": msg.usage.output_tokens,
        })
    return rows
