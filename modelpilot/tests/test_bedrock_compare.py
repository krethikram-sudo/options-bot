"""Three-arm comparison: all-baseline vs ModelPilot vs Bedrock IPR."""

from modelpilot.bedrock import (
    BEDROCK_PRICES,
    bedrock_cost,
    offline_bedrock_run_fn,
    _short_model,
)
from modelpilot.compare import (
    offline_judge_fn,
    offline_run_fn,
    render_report,
    run_comparison,
)
from modelpilot.pricing import Usage

PROMPTS = [
    {"id": "a", "prompt": "Classify this review as positive or negative: 'broke in a day'"},
    {"id": "b", "prompt": "Walk me through deriving the closed-form solution and prove convergence."},
]


def test_short_model_strips_arn():
    assert _short_model("anthropic.claude-3-5-sonnet-20241022-v2:0") == "claude-3-5-sonnet"
    assert _short_model("claude-3-5-haiku") == "claude-3-5-haiku"


def test_bedrock_cost_uses_bedrock_prices():
    usage = Usage(input_tokens=1_000_000, output_tokens=0)
    # haiku 3.5 bedrock input price is the table value, not first-party Haiku 4.5
    assert bedrock_cost("claude-3-5-haiku", usage) == BEDROCK_PRICES["claude-3-5-haiku"][0]
    assert bedrock_cost("totally-unknown-model", usage) is None


def test_three_arm_comparison_populates_bedrock_fields():
    result = run_comparison(
        PROMPTS, "claude-fable-5", offline_run_fn,
        judge_fn=offline_judge_fn, bedrock_fn=offline_bedrock_run_fn(),
        progress=lambda *_: None,
    )
    assert result["has_bedrock"]
    assert "total_bedrock_cost" in result
    assert result["bedrock_savings_pct"] is not None
    for row in result["rows"]:
        assert "bedrock_model" in row
        assert row["bedrock_model"] in {"claude-3-5-sonnet", "claude-3-5-haiku"}
        assert row["bedrock_cost"] >= 0.0


def test_report_renders_head_to_head_only_with_bedrock():
    base = run_comparison(PROMPTS, "claude-fable-5", offline_run_fn,
                          progress=lambda *_: None)
    assert "Head-to-head" not in render_report(base)

    withbr = run_comparison(PROMPTS, "claude-fable-5", offline_run_fn,
                            bedrock_fn=offline_bedrock_run_fn(),
                            progress=lambda *_: None)
    html = render_report(withbr)
    assert "Head-to-head" in html
    assert "Bedrock IPR" in html
    # surfaces the capability gap honestly
    assert "older models per router" in html
