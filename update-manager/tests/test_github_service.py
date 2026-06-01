"""Tests pour services.github_service — API GitHub mockée (pas de réseau réel)."""

from __future__ import annotations

import subprocess
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.roles import InstallSpec
from services.github_service import (
    POLKIT_ACTION_INSTALL_SERVICE,
    GitHubReleaseService,
    ManualInstallRequired,
)


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


# --- find_asset ------------------------------------------------------------


def _release_with_assets(*names: str) -> dict:
    return {
        "assets": [
            {"name": name, "browser_download_url": f"https://dl/{name}"} for name in names
        ]
    }


def test_find_asset_matche_le_motif():
    svc = GitHubReleaseService()
    release = _release_with_assets("fenix-ad_1.2.0_amd64.deb", "notes.txt")
    name, url = svc.find_asset(release, "*.deb")
    assert name == "fenix-ad_1.2.0_amd64.deb"
    assert url == "https://dl/fenix-ad_1.2.0_amd64.deb"


def test_find_asset_motif_exact():
    svc = GitHubReleaseService()
    release = _release_with_assets("install.sh", "README.md")
    name, _ = svc.find_asset(release, "install.sh")
    assert name == "install.sh"


def test_find_asset_aucun_match_leve_runtimeerror():
    svc = GitHubReleaseService()
    release = _release_with_assets("README.md")
    with pytest.raises(RuntimeError, match="Aucun asset"):
        svc.find_asset(release, "*.deb")


def test_find_asset_release_sans_assets():
    svc = GitHubReleaseService()
    with pytest.raises(RuntimeError, match="Aucun asset"):
        svc.find_asset({}, "*.deb")


# --- download_asset --------------------------------------------------------


def test_download_asset_ecrit_le_fichier(tmp_path: Path):
    svc = GitHubReleaseService()

    class _FakeResponse:
        def __init__(self) -> None:
            self._read = False

        def read(self, *args, **kwargs) -> bytes:
            if self._read:
                return b""
            self._read = True
            return b"contenu-deb"

        def __enter__(self):
            return self

        def __exit__(self, *exc) -> None:
            return None

    with patch("urllib.request.urlopen", return_value=_FakeResponse()):
        dest = svc.download_asset("https://dl/fenix-ad_1.2.0_amd64.deb", tmp_path)

    assert dest == tmp_path / "fenix-ad_1.2.0_amd64.deb"
    assert dest.read_bytes() == b"contenu-deb"


def test_download_asset_erreur_reseau_leve_runtimeerror(tmp_path: Path):
    svc = GitHubReleaseService()
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
        with pytest.raises(RuntimeError, match="Téléchargement de l'asset échoué"):
            svc.download_asset("https://dl/x.deb", tmp_path)


# --- install_service -------------------------------------------------------


def _svc_with_polkit(authorized: bool = True) -> tuple[GitHubReleaseService, MagicMock]:
    polkit = MagicMock()
    polkit.check_authorization.return_value = authorized
    return GitHubReleaseService(polkit=polkit), polkit


def test_install_service_sans_install_leve_manual(tmp_path: Path):
    svc, polkit = _svc_with_polkit()
    with pytest.raises(ManualInstallRequired, match="installation manuelle"):
        svc.install_service("fenix/ad", None)
    # Aucune vérification Polkit ni appel réseau ne doit avoir lieu.
    polkit.check_authorization.assert_not_called()


def test_install_service_polkit_refuse_leve_permissionerror():
    svc, polkit = _svc_with_polkit(authorized=False)
    install = InstallSpec("deb", "*.deb")
    with patch.object(svc, "latest_release") as latest:
        with pytest.raises(PermissionError):
            svc.install_service("fenix/ad", install)
    polkit.check_authorization.assert_called_once_with(POLKIT_ACTION_INSTALL_SERVICE)
    latest.assert_not_called()


def test_install_service_deb_telecharge_et_dpkg():
    svc, polkit = _svc_with_polkit()
    install = InstallSpec("deb", "*.deb")
    release = _release_with_assets("fenix-ad_1.2.0_amd64.deb")

    with patch.object(svc, "latest_release", return_value=release), patch.object(
        svc, "download_asset", return_value=Path("/tmp/fenix.deb")
    ) as dl, patch("subprocess.run") as run:
        svc.install_service("fenix/ad", install)

    dl.assert_called_once()
    assert dl.call_args.args[0] == "https://dl/fenix-ad_1.2.0_amd64.deb"
    run.assert_called_once()
    command = run.call_args.args[0]
    assert command == ["pkexec", "dpkg", "-i", "/tmp/fenix.deb"]


def test_install_service_script_execute_le_script():
    svc, _ = _svc_with_polkit()
    install = InstallSpec("script", "install.sh")
    release = _release_with_assets("install.sh")

    with patch.object(svc, "latest_release", return_value=release), patch.object(
        svc, "download_asset", return_value=Path("/tmp/install.sh")
    ), patch("subprocess.run") as run:
        svc.install_service("fenix/upd", install)

    assert run.call_args.args[0] == ["pkexec", "sh", "/tmp/install.sh"]


def test_install_service_echec_dpkg_leve_runtimeerror():
    svc, _ = _svc_with_polkit()
    install = InstallSpec("deb", "*.deb")
    release = _release_with_assets("x.deb")

    err = subprocess.CalledProcessError(1, ["pkexec", "dpkg"], stderr="dépendances manquantes")
    with patch.object(svc, "latest_release", return_value=release), patch.object(
        svc, "download_asset", return_value=Path("/tmp/x.deb")
    ), patch("subprocess.run", side_effect=err):
        with pytest.raises(RuntimeError, match="Installation échouée"):
            svc.install_service("fenix/ad", install)


def test_install_service_asset_introuvable_leve_runtimeerror():
    svc, _ = _svc_with_polkit()
    install = InstallSpec("deb", "*.deb")
    release = _release_with_assets("README.md")

    with patch.object(svc, "latest_release", return_value=release), patch(
        "subprocess.run"
    ) as run:
        with pytest.raises(RuntimeError, match="Aucun asset"):
            svc.install_service("fenix/ad", install)
    run.assert_not_called()
