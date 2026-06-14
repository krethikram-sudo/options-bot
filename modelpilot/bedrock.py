"""AWS Bedrock Intelligent Prompt Routing (IPR) arm for `modelpilot compare`.

Lets you run a genuine head-to-head: the same prompts through Maven's
router vs. an AWS Bedrock prompt router, with cost and non-inferiority side by
side — so "isn't this just Bedrock?" gets a measured answer, not a slogan.

Two honesty points this module makes explicit rather than hiding:

  1. Bedrock IPR routes within a fixed, *older* model set — you configure two
     models from one family (e.g. Claude Sonnet 3.5 + Haiku 3.5). It cannot
     route the current first-party lineup (Fable 5, Opus 4.x, Sonnet 4.6,
     Haiku 4.5), so on a modern workload it isn't even applicable. The report
     flags that.
  2. Each arm is priced at what you'd *actually pay in that system*: the
     Maven arm at Anthropic first-party list prices, the Bedrock arm at
     Bedrock on-demand list prices for whatever model IPR selected. This is the
     buyer's-eye comparison ("what's my bill in each"), not a routing-only
     abstraction. Prices are data below — edit to match your region/contract.

Live runs need boto3 + AWS credentials with bedrock:InvokeModel on your prompt
router ARN. Offline (`--offline --bedrock-router sim`) simulates the arm so you
can see the report shape with no AWS account.
"""

from .pricing import Usage

# Models Bedrock IPR can route to, by family (informational — surfaced in the
# report so a reader sees the capability gap vs. the current lineup). Source:
# AWS "Intelligent Prompt Routing" GA docs, 2025.
IPR_SUPPORTED_MODELS = {
    "Anthropic Claude": [
        "claude-3-haiku", "claude-3-5-haiku",
        "claude-3-5-sonnet-v1", "claude-3-5-sonnet-v2",
    ],
    "Meta Llama": [
        "llama-3-1-8b", "llama-3-1-70b",
        "llama-3-2-11b", "llama-3-2-90b", "llama-3-3-70b",
    ],
    "Amazon Nova": ["nova-pro", "nova-lite"],
}

# Bedrock on-demand list prices, USD per MTok (us-east-1, edit to taste). Kept
# separate from first-party PRICES because Bedrock bills its own rates; the
# Bedrock arm is priced here so the comparison reflects a real Bedrock bill.
BEDROCK_PRICES = {
    "claude-3-haiku": (0.25, 1.25),
    "claude-3-5-haiku": (0.80, 4.00),
    "claude-3-5-sonnet": (3.00, 15.00),  # v1 and v2
    "nova-lite": (0.06, 0.24),
    "nova-pro": (0.80, 3.20),
    "llama-3-1-8b": (0.22, 0.22),
    "llama-3-1-70b": (0.72, 0.72),
    "llama-3-3-70b": (0.72, 0.72),
}


def _short_model(model_id: str) -> str:
    """Strip a Bedrock ARN/model id down to a price-table key fragment.

    e.g. 'anthropic.claude-3-5-sonnet-20241022-v2:0' -> 'claude-3-5-sonnet'
    """
    tail = model_id.split(".")[-1] if "." in model_id else model_id
    for key in sorted(BEDROCK_PRICES, key=len, reverse=True):
        if key in tail:
            return key
    return tail


def bedrock_cost(model_id: str, usage: Usage) -> float | None:
    """Dollar cost of a Bedrock-routed request at Bedrock list prices."""
    price = BEDROCK_PRICES.get(_short_model(model_id))
    if price is None:
        return None
    in_per_tok, out_per_tok = price[0] / 1_000_000, price[1] / 1_000_000
    return usage.input_tokens * in_per_tok + usage.output_tokens * out_per_tok


def bedrock_router_run_fn(router_arn: str, region: str | None = None,
                          max_tokens: int = 1024):
    """Live arm: invoke a Bedrock prompt router via the Converse API.

    Returns a callable prompt -> (text, Usage, routed_model_id). The routed
    model is read from the prompt-router trace so the report can show which tier
    Bedrock actually picked per prompt.
    """
    import boto3  # lazy: only needed for live Bedrock runs

    client = boto3.client("bedrock-runtime", region_name=region)

    def run(prompt: str):
        resp = client.converse(
            modelId=router_arn,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": max_tokens},
        )
        out = resp.get("output", {}).get("message", {}).get("content", [])
        text = "".join(b.get("text", "") for b in out if "text" in b)
        u = resp.get("usage", {})
        usage = Usage(input_tokens=u.get("inputTokens") or 0,
                      output_tokens=u.get("outputTokens") or 0,
                      cache_read_input_tokens=u.get("cacheReadInputTokens") or 0,
                      cache_creation_input_tokens=u.get("cacheWriteInputTokens") or 0)
        trace = resp.get("trace", {}).get("promptRouter", {})
        routed = trace.get("invokedModelId") or router_arn
        return text, usage, _short_model(routed)

    return run


def offline_bedrock_run_fn(simple_categories=("classification", "extraction",
                                              "rewrite_format", "codegen_simple"),
                           big="claude-3-5-sonnet", small="claude-3-5-haiku"):
    """Offline sim of a 2-model Claude prompt router (report-shape only).

    Mirrors IPR's documented behavior — route 'simple-looking' prompts to the
    cheaper model, everything else to the stronger one — over its *older* model
    pair, so the simulated arm is realistic about what IPR can and can't pick.
    """
    import random

    from .router import recommend

    def run(prompt: str):
        body = {"model": big, "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}]}
        rec = recommend(body)
        model = small if rec.category in simple_categories else big
        rng = random.Random(hash(("bedrock", model, prompt)) & 0xFFFF)
        text = (f"[offline Bedrock-IPR sample from {model}]\n"
                f"Response to: {prompt[:80]}…")
        usage = Usage(input_tokens=max(len(prompt) // 4, 30),
                      output_tokens=rng.randint(80, 400))
        return text, usage, model

    return run
