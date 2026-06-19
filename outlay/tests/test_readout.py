"""VP-ready HTML audit readout."""

from outlay.cli import run
from outlay.readout import render_html
from outlay.serialize import to_dict
from outlay.tests.test_pipeline import FIX

from outlay.attribute import attribute
from outlay.backtest import backtest
from outlay.forecast import class_stats, find_anomalies, forecast_roadmap
from outlay.ingest import parse_anthropic_usage, parse_github_issues
from outlay.policy import build_policy
from outlay.recommend import recommend
from outlay.size import fit_size_models


def _fixture_dict():
    events = parse_anthropic_usage(FIX / "anthropic_usage.json")
    work = parse_github_issues(FIX / "github_issues.json")
    res = attribute(events, work)
    stats = class_stats(res)
    fc = forecast_roadmap([w for w in work if w.is_open], stats, fit_size_models(res, work))
    recs = recommend(res)
    return to_dict(res, stats, fc, find_anomalies(res, stats), recs,
                   calibration=backtest(res, work), policy=build_policy(recs),
                   window_days=9)


def test_render_html_is_standalone_and_branded():
    html = render_html(_fixture_dict(), company="Acme Corp")
    assert html.startswith("<!doctype html>")
    assert html.rstrip().endswith("</html>")
    assert "Acme Corp" in html
    assert "AI spend audit" in html
    # Headline numbers present.
    assert "Total AI spend" in html
    assert "Mapped to a ticket" in html
    assert "Savings opportunity" in html
    assert "Forecast for open work" in html


def test_html_escapes_company_name():
    html = render_html(_fixture_dict(), company='Ac<me> & "Co"')
    assert "Ac<me>" not in html
    assert "Ac&lt;me&gt; &amp; &quot;Co&quot;" in html


def test_default_company_label():
    html = render_html(_fixture_dict())
    assert "Your team" in html


def test_cli_html_flag():
    out = run(FIX / "anthropic_usage.json", FIX / "github_issues.json",
              window_days=9, as_html=True, company="Pilot Co")
    assert out.startswith("<!doctype html>")
    assert "Pilot Co" in out
    # measured-accuracy trust line surfaces (fixtures have calibratable history)
    assert "Forecast accuracy" in out
