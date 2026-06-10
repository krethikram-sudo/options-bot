"""Turn per-model verdicts into the golden label: cheapest non-inferior model."""

from ..pricing import CAPABILITY_LADDER, ladder_tier


def label_from_verdicts(verdicts: dict[str, bool], baseline_model: str) -> str | None:
    """Walk the ladder from cheapest up; first non-inferior model is the label.

    Returns None when nothing passes below the baseline and the baseline has
    no verdict (degenerate row) — callers should drop those.
    """
    baseline_tier = ladder_tier(baseline_model)
    for tier, model in enumerate(CAPABILITY_LADDER):
        if baseline_tier is not None and tier > baseline_tier:
            break
        if verdicts.get(model):
            return model
    return baseline_model if verdicts.get(baseline_model) else None
