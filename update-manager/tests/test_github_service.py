"""Tests pour services.github_service — API GitHub mockée (pas de réseau réel)."""

from __future__ import annotations

import urllib.error
from unittest.mock import patch

import pytest

from services.github_service import GitHubReleaseService


# --- latest_release / _get_json -------------------------------------------


def test_latest_release_construit_la_bonne_url():
    svc = GitHubReleaseService("https://api.example.com")
    with patch.object(svc, "_get_json", return_value={"tag_name": "v1.0.0"}) as mock_get:
        data = svc.latest_release("fenix/ad")

    mock_get.assert_called_once_with("https://api.example.com/repos/fenix/ad/releases/latest")
    assert data["tag_name"] == "v1.0.0"


def test_api_base_trailing_slash_normalise():
    svc = GitHubReleaseService("https://api.example.com/")
    with patch.object(svc, "_get_json", return_value={}) as mock_get:
        svc.latest_release("fenix/ad")
    mock_get.assert_called_once_with("https://api.example.com/repos/fenix/ad/releases/latest")


def test_get_json_erreur_reseau_leve_runtimeerror():
    svc = GitHubReleaseService("https://api.example.com")
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
        with pytest.raises(RuntimeError, match="Requête GitHub échouée"):
            svc.latest_release("fenix/ad")


# --- check_update ----------------------------------------------------------


def test_check_update_construit_service_update_avec_maj():
    svc = GitHubReleaseService()
    release = {
        "tag_name": "v2.0.0",
        "html_url": "https://github.com/fenix/ad/releases/tag/v2.0.0",
    }
    with patch.object(svc, "latest_release", return_value=release):
        result = svc.check_update("ad", "fenix/ad", "1.0.0")

    assert result.service_id == "ad"
    assert result.name == "ad"
    assert result.current_version == "1.0.0"
    assert result.latest_version == "v2.0.0"
    assert result.release_url == "https://github.com/fenix/ad/releases/tag/v2.0.0"
    assert result.update_available is True


def test_check_update_sans_maj():
    svc = GitHubReleaseService()
    with patch.object(svc, "latest_release", return_value={"tag_name": "v1.0.0"}):
        result = svc.check_update("ad", "fenix/ad", "1.0.0")
    assert result.update_available is False


# --- check_all -------------------------------------------------------------


def test_check_all_agrege_les_resultats():
    svc = GitHubReleaseService()
    releases = {
        "fenix/ad": {"tag_name": "v1.1.0"},
        "fenix/upd": {"tag_name": "v2.0.0"},
    }
    with patch.object(svc, "latest_release", side_effect=lambda repo: releases[repo]):
        results = svc.check_all(
            {
                "ad": ("fenix/ad", "1.0.0"),
                "upd": ("fenix/upd", "2.0.0"),
            }
        )

    by_id = {r.service_id: r for r in results}
    assert set(by_id) == {"ad", "upd"}
    assert by_id["ad"].update_available is True
    assert by_id["upd"].update_available is False


def test_check_all_ignore_les_services_en_erreur():
    svc = GitHubReleaseService()

    def fake_latest(repo: str):
        if repo == "fenix/ko":
            raise RuntimeError("404")
        return {"tag_name": "v1.1.0"}

    with patch.object(svc, "latest_release", side_effect=fake_latest):
        results = svc.check_all(
            {
                "ok": ("fenix/ad", "1.0.0"),
                "ko": ("fenix/ko", "1.0.0"),
            }
        )

    assert [r.service_id for r in results] == ["ok"]
