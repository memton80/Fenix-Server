"""Tests pour models.update_item."""

from __future__ import annotations

import pytest

from models.update_item import ServiceUpdate, SystemPackageUpdate


def _service(current: str, latest: str) -> ServiceUpdate:
    return ServiceUpdate(
        service_id="ad",
        name="Active Directory",
        current_version=current,
        latest_version=latest,
        release_url="https://github.com/fenix/ad/releases/latest",
    )


# --- SystemPackageUpdate --------------------------------------------------


def test_system_package_update_champs():
    pkg = SystemPackageUpdate("bash;5.2-1;amd64;debian", "bash", "5.2-1", "GNU Bash")
    assert pkg.name == "bash"
    assert pkg.version == "5.2-1"
    assert pkg.package_id.startswith("bash;")


def test_system_package_update_est_frozen():
    pkg = SystemPackageUpdate("bash;5.2-1;amd64;debian", "bash", "5.2-1", "GNU Bash")
    with pytest.raises(Exception):
        pkg.name = "zsh"  # type: ignore[misc]


# --- ServiceUpdate.update_available ---------------------------------------


def test_update_available_version_plus_recente():
    assert _service("1.0.0", "1.2.0").update_available is True


def test_update_available_versions_egales():
    assert _service("1.2.0", "1.2.0").update_available is False


def test_update_available_ignore_le_prefixe_v():
    assert _service("v1.2.0", "1.2.0").update_available is False
    assert _service("1.2.0", "v1.3.0").update_available is True


def test_update_available_comparaison_numerique():
    # 1.10.0 doit être considéré plus récent que 1.9.0 (pas une comparaison texte).
    assert _service("1.9.0", "1.10.0").update_available is True


def test_update_available_latest_vide():
    assert _service("1.0.0", "").update_available is False


def test_update_available_version_anterieure():
    assert _service("2.0.0", "1.0.0").update_available is False
