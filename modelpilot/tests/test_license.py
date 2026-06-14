import time

import pytest

from modelpilot.license import LicenseError, check, make_token, verify_token


def test_roundtrip_valid():
    tok = make_token({"licensee": "Acme", "exp": int(time.time()) + 3600})
    claims = verify_token(tok)
    assert claims["licensee"] == "Acme"


def test_no_expiry_ok():
    claims = verify_token(make_token({"licensee": "Forever", "exp": None}))
    assert claims["licensee"] == "Forever"


def test_expired_rejected():
    tok = make_token({"licensee": "Old", "exp": int(time.time()) - 10})
    with pytest.raises(LicenseError):
        verify_token(tok)


def test_tampered_rejected():
    tok = make_token({"licensee": "Acme", "exp": None})
    payload, sig = tok.split(".")
    forged = make_token({"licensee": "Pirate", "exp": None}).split(".")[0] + "." + sig
    with pytest.raises(LicenseError):
        verify_token(forged)


def test_wrong_secret_rejected():
    tok = make_token({"licensee": "Acme", "exp": None})
    with pytest.raises(LicenseError):
        verify_token(tok, secret=b"not-our-secret")


def test_check_env(monkeypatch):
    monkeypatch.delenv("MODELPILOT_LICENSE", raising=False)
    assert check() is None  # no token -> None (guidance/shadow allowed)
    monkeypatch.setenv("MODELPILOT_LICENSE", make_token({"licensee": "Acme", "exp": None}))
    assert check()["licensee"] == "Acme"


def test_check_file(tmp_path, monkeypatch):
    f = tmp_path / "lic.txt"
    f.write_text(make_token({"licensee": "Acme", "exp": None}))
    monkeypatch.setenv("MODELPILOT_LICENSE", "@" + str(f))
    assert check()["licensee"] == "Acme"
