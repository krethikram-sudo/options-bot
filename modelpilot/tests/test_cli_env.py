from modelpilot.cli import _gateway_env, build_parser


def test_gateway_db_respects_env(monkeypatch):
    monkeypatch.setenv("MODELPILOT_DB", "/tmp/custom.db")
    args = build_parser().parse_args(["gateway"])
    assert args.db == "/tmp/custom.db"
    # _gateway_env re-exports the resolved value, not the built-in default,
    # so os.environ.update() can't clobber the operator's setting.
    assert _gateway_env(args)["MODELPILOT_DB"] == "/tmp/custom.db"


def test_explicit_flag_overrides_env(monkeypatch):
    monkeypatch.setenv("MODELPILOT_DB", "/tmp/env.db")
    args = build_parser().parse_args(["gateway", "--db", "/tmp/flag.db"])
    assert args.db == "/tmp/flag.db"


def test_env_mode_upstream_capture(monkeypatch):
    monkeypatch.setenv("MODELPILOT_MODE", "autopilot")
    monkeypatch.setenv("MODELPILOT_UPSTREAM", "http://up:9000")
    monkeypatch.setenv("MODELPILOT_CAPTURE_PCT", "0.25")
    args = build_parser().parse_args(["gateway"])
    assert args.mode == "autopilot"
    assert args.upstream == "http://up:9000"
    assert args.capture == 0.25


def test_defaults_without_env(monkeypatch):
    for v in ("MODELPILOT_DB", "MODELPILOT_MODE", "MODELPILOT_UPSTREAM",
              "MODELPILOT_CAPTURE_PCT", "MODELPILOT_PORT"):
        monkeypatch.delenv(v, raising=False)
    args = build_parser().parse_args(["gateway"])
    assert args.db == "modelpilot.db"
    assert args.mode == "shadow"
    assert args.port == 8400
