"""Usage metering: incremental deltas, marker persistence, aggregate-only payload."""

from modelpilot import metering
from modelpilot.ledger import Ledger
from modelpilot.pricing import Usage
from modelpilot.router import Recommendation


def test_compute_delta_never_negative():
    cum = {"requests": 100, "routed": 60, "baseline_cost": 10.0, "actual_cost": 6.0,
           "realized_savings": 4.0}
    marker = {"requests": 40, "routed": 25, "baseline_cost": 4.0, "actual_cost": 2.5,
              "realized_savings": 1.5}
    d = metering.compute_delta(cum, marker)
    assert d["requests"] == 60 and d["realized_savings"] == 2.5
    # a reset ledger (cumulative < marker) clamps to 0, never bills negative
    assert metering.compute_delta(marker, cum)["requests"] == 0


def _seed_ledger(path):
    led = Ledger(str(path))
    rec = Recommendation(action="switch", original_model="claude-opus-4-8",
                         recommended_model="claude-haiku-4-5", confidence=0.9,
                         category="classification", rationale="x")
    # an applied switch with real token usage -> realized savings recorded
    led.record(mode="autopilot", recommendation=rec, routed_model="claude-haiku-4-5",
               applied=True, status_code=200,
               usage=Usage(input_tokens=1000, output_tokens=1000),
               arm="treatment", retry_of=None, request_id="r1", session_key="s1")
    led.close()


def test_report_once_posts_delta_then_nothing_new(tmp_path):
    db = tmp_path / "m.db"
    _seed_ledger(db)
    posted = []
    res = metering.report_once(str(db), "http://console", "dep_abc",
                               post_fn=lambda p: posted.append(p))
    assert res["posted"] is True
    p = posted[0]
    assert p["deployment_id"] == "dep_abc"
    assert p["realized_savings"] > 0 and p["requests"] == 1
    # forbidden keys never appear in a metering payload
    assert not ({"messages", "prompt", "text"} & set(p))
    # second run with no new ledger activity -> nothing to post (marker advanced)
    res2 = metering.report_once(str(db), "http://console", "dep_abc",
                                post_fn=lambda p: posted.append(p))
    assert res2["posted"] is False and len(posted) == 1


def test_report_once_noop_without_config(tmp_path):
    db = tmp_path / "m2.db"
    _seed_ledger(db)
    res = metering.report_once(str(db), "", "")
    assert res["posted"] is False
