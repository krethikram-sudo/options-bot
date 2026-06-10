"""Golden-set pipeline: fan prompts out across models, judge non-inferiority,
label each prompt with the cheapest acceptable model, evaluate the router.

Flow (see ROUTER_TUNING_PLAN.md §3):

  prompts.jsonl --submit--> Batch API --collect--> outputs.jsonl
      --judge--> judgments.jsonl --label--> labels.jsonl
      --evaluate--> router metrics + confidence-threshold sweep
"""
