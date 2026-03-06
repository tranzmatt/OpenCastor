"""Unit tests for castor.secret_provider — JWT key loading and rotation."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider():
    """Return a fresh, uncached JWTSecretProvider."""
    from castor.secret_provider import JWTSecretProvider

    return JWTSecretProvider()


def _clear_jwt_env(monkeypatch):
    """Remove all JWT-related env vars so loaders start from a clean state."""
    for key in (
        "OPENCASTOR_JWT_SECRET_KEYRING_ID",
        "OPENCASTOR_JWT_SECRET_CREDENTIAL",
        "CREDENTIALS_DIRECTORY",
        "OPENCASTOR_JWT_SECRETS_FILE",
        "OPENCASTOR_JWT_SECRET_FILE",
        "OPENCASTOR_JWT_ROTATION_FILE",
        "JWT_SECRET",
        "OPENCASTOR_JWT_SECRET",
        "OPENCASTOR_API_TOKEN",
        "OPENCASTOR_JWT_KID",
        "JWT_KID",
        "OPENCASTOR_JWT_PREVIOUS_SECRET",
        "OPENCASTOR_JWT_PREVIOUS_KID",
        "OPENCASTOR_ENV",
        "OPENCASTOR_PROFILE",
        "OPENCASTOR_SECURITY_PROFILE",
        "OPENCASTOR_JWT_WEAK_SOURCE_POLICY",
    ):
        monkeypatch.delenv(key, raising=False)


# ---------------------------------------------------------------------------
# JWTKeyMaterial & JWTSecretBundle dataclasses
# ---------------------------------------------------------------------------


def test_jwt_key_material_fields():
    """JWTKeyMaterial stores kid and secret."""
    from castor.secret_provider import JWTKeyMaterial

    km = JWTKeyMaterial(kid="test-kid", secret="s3cr3t")
    assert km.kid == "test-kid"
    assert km.secret == "s3cr3t"


def test_jwt_secret_bundle_weak_source_env():
    """JWTSecretBundle.weak_source is True when source is 'env'."""
    from castor.secret_provider import JWTKeyMaterial, JWTSecretBundle

    bundle = JWTSecretBundle(
        active=JWTKeyMaterial(kid="k1", secret="abc"),
        previous=None,
        source="env",
    )
    assert bundle.weak_source is True


def test_jwt_secret_bundle_weak_source_false_for_file():
    """JWTSecretBundle.weak_source is False when source is not 'env'."""
    from castor.secret_provider import JWTKeyMaterial, JWTSecretBundle

    bundle = JWTSecretBundle(
        active=JWTKeyMaterial(kid="k1", secret="abc"),
        previous=None,
        source="file:/some/path",
    )
    assert bundle.weak_source is False


# ---------------------------------------------------------------------------
# get_jwt_secret_provider singleton
# ---------------------------------------------------------------------------


def test_get_jwt_secret_provider_returns_same_instance():
    """Module-level singleton is consistent across calls."""
    from castor.secret_provider import get_jwt_secret_provider

    p1 = get_jwt_secret_provider()
    p2 = get_jwt_secret_provider()
    assert p1 is p2


# ---------------------------------------------------------------------------
# _from_env loader
# ---------------------------------------------------------------------------


def test_from_env_jwt_secret(monkeypatch):
    """JWT_SECRET env var produces an env-source bundle."""
    _clear_jwt_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "my-env-secret")

    provider = _make_provider()
    bundle = provider.get_bundle()

    assert bundle.active.secret == "my-env-secret"
    assert bundle.source == "env"
    assert bundle.previous is None


def test_from_env_opencastor_jwt_secret(monkeypatch):
    """OPENCASTOR_JWT_SECRET is used as fallback when JWT_SECRET is absent."""
    _clear_jwt_env(monkeypatch)
    monkeypatch.setenv("OPENCASTOR_JWT_SECRET", "ocastor-secret")

    provider = _make_provider()
    bundle = provider.get_bundle()

    assert bundle.active.secret == "ocastor-secret"
    assert bundle.source == "env"


def test_from_env_api_token(monkeypatch):
    """OPENCASTOR_API_TOKEN is used when neither JWT_SECRET nor OPENCASTOR_JWT_SECRET are set."""
    _clear_jwt_env(monkeypatch)
    monkeypatch.setenv("OPENCASTOR_API_TOKEN", "api-tok-xyz")

    provider = _make_provider()
    bundle = provider.get_bundle()

    assert bundle.active.secret == "api-tok-xyz"
    assert bundle.source == "env"


def test_from_env_custom_kid(monkeypatch):
    """OPENCASTOR_JWT_KID overrides the default kid."""
    _clear_jwt_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "sec")
    monkeypatch.setenv("OPENCASTOR_JWT_KID", "my-kid-42")

    provider = _make_provider()
    bundle = provider.get_bundle()

    assert bundle.active.kid == "my-kid-42"


def test_from_env_previous_secret(monkeypatch):
    """OPENCASTOR_JWT_PREVIOUS_SECRET populates bundle.previous."""
    _clear_jwt_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "active-sec")
    monkeypatch.setenv("OPENCASTOR_JWT_PREVIOUS_SECRET", "old-sec")
    monkeypatch.setenv("OPENCASTOR_JWT_PREVIOUS_KID", "old-kid")

    provider = _make_provider()
    bundle = provider.get_bundle()

    assert bundle.previous is not None
    assert bundle.previous.secret == "old-sec"
    assert bundle.previous.kid == "old-kid"


# ---------------------------------------------------------------------------
# _from_vault_file loader
# ---------------------------------------------------------------------------


def test_from_vault_file_json_with_previous(monkeypatch, tmp_path):
    """A JSON secrets file with active+previous is parsed correctly."""
    _clear_jwt_env(monkeypatch)

    payload = {
        "active": {"kid": "vault-k1", "secret": "vault-secret-1"},
        "previous": {"kid": "vault-k0", "secret": "vault-secret-0"},
    }
    secrets_file = tmp_path / "jwt-keys.json"
    secrets_file.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("OPENCASTOR_JWT_SECRETS_FILE", str(secrets_file))

    provider = _make_provider()
    bundle = provider.get_bundle()

    assert bundle.active.kid == "vault-k1"
    assert bundle.active.secret == "vault-secret-1"
    assert bundle.previous is not None
    assert bundle.previous.kid == "vault-k0"
    assert bundle.source.startswith("file:")


def test_from_vault_file_plain_text(monkeypatch, tmp_path):
    """A non-JSON secrets file is treated as a plain-text secret."""
    _clear_jwt_env(monkeypatch)

    secrets_file = tmp_path / "jwt.secret"
    secrets_file.write_text("plain-text-secret\n", encoding="utf-8")
    monkeypatch.setenv("OPENCASTOR_JWT_SECRETS_FILE", str(secrets_file))

    provider = _make_provider()
    bundle = provider.get_bundle()

    assert bundle.active.secret == "plain-text-secret"
    assert bundle.source.startswith("file:")


def test_from_vault_file_missing_secret_skipped(monkeypatch, tmp_path):
    """A JSON file with empty active.secret is skipped; fallback to next loader."""
    _clear_jwt_env(monkeypatch)

    payload = {"active": {"kid": "bad-kid", "secret": ""}}
    secrets_file = tmp_path / "jwt-bad.json"
    secrets_file.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("OPENCASTOR_JWT_SECRETS_FILE", str(secrets_file))
    # Provide env fallback so we don't fall through to ephemeral
    monkeypatch.setenv("JWT_SECRET", "env-fallback")

    provider = _make_provider()
    bundle = provider.get_bundle()

    assert bundle.source == "env"
    assert bundle.active.secret == "env-fallback"


def test_from_vault_file_nonexistent_path_skipped(monkeypatch):
    """A configured path that does not exist is silently skipped."""
    _clear_jwt_env(monkeypatch)
    monkeypatch.setenv("OPENCASTOR_JWT_SECRETS_FILE", "/nonexistent/path/jwt.json")
    monkeypatch.setenv("JWT_SECRET", "fallback")

    provider = _make_provider()
    bundle = provider.get_bundle()

    assert bundle.source == "env"


# ---------------------------------------------------------------------------
# _from_systemd_credentials loader
# ---------------------------------------------------------------------------


def test_from_systemd_credentials_via_credentials_dir(monkeypatch, tmp_path):
    """CREDENTIALS_DIRECTORY path is checked for the credential file."""
    _clear_jwt_env(monkeypatch)

    cred_name = "opencastor_jwt_secret"
    cred_file = tmp_path / cred_name
    cred_file.write_text("systemd-secret-value", encoding="utf-8")
    monkeypatch.setenv("CREDENTIALS_DIRECTORY", str(tmp_path))

    provider = _make_provider()
    bundle = provider.get_bundle()

    assert bundle.source == "systemd"
    assert bundle.active.secret == "systemd-secret-value"


def test_from_systemd_credentials_custom_name(monkeypatch, tmp_path):
    """OPENCASTOR_JWT_SECRET_CREDENTIAL overrides the default credential name."""
    _clear_jwt_env(monkeypatch)

    cred_name = "my_custom_jwt_cred"
    cred_file = tmp_path / cred_name
    cred_file.write_text("custom-cred-secret", encoding="utf-8")
    monkeypatch.setenv("CREDENTIALS_DIRECTORY", str(tmp_path))
    monkeypatch.setenv("OPENCASTOR_JWT_SECRET_CREDENTIAL", cred_name)

    provider = _make_provider()
    bundle = provider.get_bundle()

    assert bundle.source == "systemd"
    assert bundle.active.secret == "custom-cred-secret"


def test_from_systemd_credentials_empty_file_skipped(monkeypatch, tmp_path):
    """An empty credential file is skipped in favour of the next loader."""
    _clear_jwt_env(monkeypatch)

    cred_file = tmp_path / "opencastor_jwt_secret"
    cred_file.write_text("   ", encoding="utf-8")  # whitespace only
    monkeypatch.setenv("CREDENTIALS_DIRECTORY", str(tmp_path))
    monkeypatch.setenv("JWT_SECRET", "env-after-systemd")

    provider = _make_provider()
    bundle = provider.get_bundle()

    assert bundle.source == "env"


# ---------------------------------------------------------------------------
# _from_keyring loader
# ---------------------------------------------------------------------------


def test_from_keyring_success(monkeypatch):
    """Successful keyctl output is returned as a keyring-source bundle."""
    _clear_jwt_env(monkeypatch)
    monkeypatch.setenv("OPENCASTOR_JWT_SECRET_KEYRING_ID", "12345")

    with patch("subprocess.check_output", return_value="keyring-secret"):
        provider = _make_provider()
        bundle = provider.get_bundle()

    assert bundle.source == "keyring"
    assert bundle.active.secret == "keyring-secret"


def test_from_keyring_subprocess_error_falls_through(monkeypatch):
    """A failing keyctl call logs a warning and falls through to the next loader."""
    _clear_jwt_env(monkeypatch)
    monkeypatch.setenv("OPENCASTOR_JWT_SECRET_KEYRING_ID", "99999")
    monkeypatch.setenv("JWT_SECRET", "fallback-env")

    with patch("subprocess.check_output", side_effect=Exception("keyctl not found")):
        provider = _make_provider()
        bundle = provider.get_bundle()

    assert bundle.source == "env"


def test_from_keyring_not_configured(monkeypatch):
    """Without OPENCASTOR_JWT_SECRET_KEYRING_ID the keyring loader returns None."""
    _clear_jwt_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "env-only")

    provider = _make_provider()
    bundle = provider.get_bundle()

    assert bundle.source == "env"


# ---------------------------------------------------------------------------
# Ephemeral fallback
# ---------------------------------------------------------------------------


def test_ephemeral_fallback_when_no_sources(monkeypatch):
    """When no secret source is configured, an ephemeral random secret is used."""
    _clear_jwt_env(monkeypatch)

    # Ensure no systemd credential files exist at default paths
    with patch("pathlib.Path.exists", return_value=False):
        provider = _make_provider()
        bundle = provider.get_bundle()

    assert bundle.source == "ephemeral"
    assert bundle.active.kid == "ephemeral"
    assert len(bundle.active.secret) > 0
    assert bundle.previous is None


# ---------------------------------------------------------------------------
# Caching and invalidation
# ---------------------------------------------------------------------------


def test_get_bundle_is_cached(monkeypatch):
    """Repeated calls to get_bundle() return the same object without re-loading."""
    _clear_jwt_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "cached-secret")

    provider = _make_provider()
    b1 = provider.get_bundle()
    b2 = provider.get_bundle()

    assert b1 is b2


def test_invalidate_clears_cache(monkeypatch):
    """invalidate() forces the next get_bundle() to reload."""
    _clear_jwt_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "original")

    provider = _make_provider()
    b1 = provider.get_bundle()

    provider.invalidate()
    monkeypatch.setenv("JWT_SECRET", "refreshed")
    b2 = provider.get_bundle()

    assert b1 is not b2
    assert b2.active.secret == "refreshed"


# ---------------------------------------------------------------------------
# Key rotation
# ---------------------------------------------------------------------------


def test_rotate_writes_file_and_returns_new_bundle(monkeypatch, tmp_path):
    """rotate() persists the new key bundle and returns an updated bundle."""
    _clear_jwt_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "original-secret")

    rotation_file = tmp_path / "jwt-keys.json"
    monkeypatch.setenv("OPENCASTOR_JWT_ROTATION_FILE", str(rotation_file))

    provider = _make_provider()
    new_bundle = provider.rotate(new_secret="rotated-secret", new_kid="rotated-kid")

    assert new_bundle.active.kid == "rotated-kid"
    assert new_bundle.active.secret == "rotated-secret"
    assert new_bundle.previous is not None
    assert new_bundle.previous.secret == "original-secret"
    assert rotation_file.exists()

    on_disk = json.loads(rotation_file.read_text(encoding="utf-8"))
    assert on_disk["active"]["secret"] == "rotated-secret"
    assert on_disk["previous"]["secret"] == "original-secret"


def test_rotate_generates_random_kid_when_not_specified(monkeypatch, tmp_path):
    """rotate() auto-generates a kid when new_kid is not provided."""
    _clear_jwt_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "original")
    monkeypatch.setenv("OPENCASTOR_JWT_ROTATION_FILE", str(tmp_path / "jwt-keys.json"))

    provider = _make_provider()
    new_bundle = provider.rotate(new_secret="new-sec")

    assert new_bundle.active.kid.startswith("k-")


def test_rotate_generates_random_secret_when_not_specified(monkeypatch, tmp_path):
    """rotate() auto-generates a secret when new_secret is not provided."""
    _clear_jwt_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "original")
    monkeypatch.setenv("OPENCASTOR_JWT_ROTATION_FILE", str(tmp_path / "jwt-keys.json"))

    provider = _make_provider()
    new_bundle = provider.rotate()

    assert len(new_bundle.active.secret) > 0
    assert new_bundle.active.secret != "original"


# ---------------------------------------------------------------------------
# enforce_weak_source_policy
# ---------------------------------------------------------------------------


def test_enforce_weak_source_policy_silent_in_dev(monkeypatch):
    """Weak source in a non-production profile does not raise or warn."""
    _clear_jwt_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "dev-secret")
    monkeypatch.setenv("OPENCASTOR_ENV", "development")

    provider = _make_provider()
    # Should not raise
    provider.enforce_weak_source_policy()


def test_enforce_weak_source_policy_warns_in_prod(monkeypatch, caplog):
    """Weak source in production profile emits a warning when policy is 'warn'."""
    import logging

    _clear_jwt_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "prod-secret")
    monkeypatch.setenv("OPENCASTOR_ENV", "production")
    monkeypatch.setenv("OPENCASTOR_JWT_WEAK_SOURCE_POLICY", "warn")

    provider = _make_provider()
    with caplog.at_level(logging.WARNING, logger="OpenCastor.Secrets"):
        provider.enforce_weak_source_policy()

    assert any("plain environment variables" in r.message for r in caplog.records)


def test_enforce_weak_source_policy_raises_in_prod_with_error_policy(monkeypatch):
    """Weak source in production profile raises RuntimeError when policy is 'error'."""
    _clear_jwt_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "prod-secret")
    monkeypatch.setenv("OPENCASTOR_ENV", "prod")
    monkeypatch.setenv("OPENCASTOR_JWT_WEAK_SOURCE_POLICY", "error")

    provider = _make_provider()
    with pytest.raises(RuntimeError, match="plain environment variables"):
        provider.enforce_weak_source_policy()


def test_enforce_weak_source_policy_noop_for_strong_source(monkeypatch, tmp_path):
    """No policy is applied when the bundle comes from a non-env source."""
    _clear_jwt_env(monkeypatch)
    payload = {"active": {"kid": "file-k1", "secret": "file-secret"}}
    f = tmp_path / "jwt.json"
    f.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("OPENCASTOR_JWT_SECRETS_FILE", str(f))
    monkeypatch.setenv("OPENCASTOR_ENV", "production")
    monkeypatch.setenv("OPENCASTOR_JWT_WEAK_SOURCE_POLICY", "error")

    provider = _make_provider()
    # Should not raise — source is 'file:...', not 'env'
    provider.enforce_weak_source_policy()
