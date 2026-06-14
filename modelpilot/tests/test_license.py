import time

import pytest

from modelpilot.license import LicenseError, check, make_token, verify_token


def _ed25519_available():
    try:  # this sandbox's cryptography is broken; CI's works
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        Ed25519PrivateKey.generate()
        return True
    except BaseException:  # noqa: BLE001 — capability probe (pyo3 panic isn't an Exception)
        return False


ED25519 = _ed25519_available()


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


@pytest.mark.skipif(not ED25519, reason="cryptography/Ed25519 unavailable in this environment")
def test_ed25519_unforgeable(tmp_path, monkeypatch):
    import modelpilot.license as lic
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    priv = Ed25519PrivateKey.generate()
    priv_pem = priv.private_bytes(serialization.Encoding.PEM,
                                  serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption())
    pub_pem = priv.public_key().public_bytes(serialization.Encoding.PEM,
                                             serialization.PublicFormat.SubjectPublicKeyInfo)
    pub_file = tmp_path / "license_pubkey.pem"
    pub_file.write_bytes(pub_pem)
    monkeypatch.setattr(lic, "_PUBKEY_PATH", str(pub_file))

    tok = lic.make_token_ed25519({"licensee": "Acme", "exp": None}, priv_pem)
    assert lic.verify_token(tok)["licensee"] == "Acme"

    # In asymmetric mode, an HMAC token (what a copier could mint from the shipped
    # secret) is rejected — the shipped client can verify but cannot forge.
    with pytest.raises(LicenseError):
        lic.verify_token(make_token({"licensee": "Pirate", "exp": None}))
