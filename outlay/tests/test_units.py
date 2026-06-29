"""Hero metric — cost per delivered unit of work."""

from outlay.units import cost_per_unit


def test_cost_per_unit_only_counts_shipped():
    report = {"tickets": [
        {"task_class": "feature", "status": "done", "cost_usd": 40.0},
        {"task_class": "bugfix", "status": "done", "cost_usd": 20.0},
        {"task_class": "feature", "status": "open", "cost_usd": 99.0},  # not shipped — excluded
    ]}
    u = cost_per_unit(report)
    assert u["units_shipped"] == 2
    assert u["cost_per_unit_usd"] == 30.0          # (40+20)/2
    assert u["total_attributed_usd"] == 60.0


def test_cost_per_unit_by_class_sorted_desc():
    report = {"tickets": [
        {"task_class": "feature", "status": "done", "cost_usd": 40.0},
        {"task_class": "test", "status": "done", "cost_usd": 2.0},
        {"task_class": "test", "status": "done", "cost_usd": 4.0},
    ]}
    bc = cost_per_unit(report)["by_class"]
    assert bc[0]["task_class"] == "feature" and bc[0]["cost_per_unit_usd"] == 40.0
    assert bc[1]["task_class"] == "test" and bc[1]["cost_per_unit_usd"] == 3.0
    assert bc[1]["units"] == 2


def test_cost_per_unit_empty():
    assert cost_per_unit({"tickets": []})["cost_per_unit_usd"] == 0.0
    assert cost_per_unit({})["units_shipped"] == 0
