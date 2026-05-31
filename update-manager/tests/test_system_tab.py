"""Tests pour widgets.system_tab — service PackageKit simulé, Qt réel (offscreen)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QObject, Signal

from core.theme import ThemeManager
from models.update_item import SystemPackageUpdate
from widgets.system_tab import SystemUpdateTab


class FakePackageKitService(QObject):
    """Faux service exposant les vrais signaux Qt et des méthodes mockées."""

    updates_found = Signal(list)
    progress_changed = Signal(int)
    finished = Signal()
    error_occurred = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.request_updates = MagicMock()
        self.install_updates = MagicMock()
        self.refresh_cache = MagicMock()


@pytest.fixture
def service() -> FakePackageKitService:
    return FakePackageKitService()


@pytest.fixture
def tab(service: FakePackageKitService) -> SystemUpdateTab:
    return SystemUpdateTab(service, ThemeManager())


def _updates() -> list[SystemPackageUpdate]:
    return [
        SystemPackageUpdate("bash;5.2-1;amd64;debian", "bash", "5.2-1", "GNU Bash"),
        SystemPackageUpdate("vim;9.0;amd64;debian", "vim", "9.0", "Vi IMproved"),
    ]


def test_etat_initial(tab: SystemUpdateTab):
    assert tab._table.rowCount() == 0
    assert tab._progress.isHidden() is True


def test_rafraichir_appelle_request_updates(tab: SystemUpdateTab, service):
    tab._btn_refresh.click()
    service.request_updates.assert_called_once_with()


def test_updates_found_peuple_la_table(tab: SystemUpdateTab, service):
    service.updates_found.emit(_updates())
    assert tab._table.rowCount() == 2
    assert tab._table.item(0, 0).text() == "bash"
    assert tab._table.item(0, 1).text() == "5.2-1"
    assert tab._table.item(1, 0).text() == "vim"


def test_installer_envoie_les_package_ids_et_affiche_progress(tab: SystemUpdateTab, service):
    service.updates_found.emit(_updates())
    tab._btn_install.click()
    service.install_updates.assert_called_once_with(
        ["bash;5.2-1;amd64;debian", "vim;9.0;amd64;debian"]
    )
    assert tab._progress.isHidden() is False
    assert tab._btn_install.isEnabled() is False


def test_installer_sans_maj_affiche_info(tab: SystemUpdateTab, service):
    with patch("widgets.system_tab.QMessageBox.information") as info:
        tab._btn_install.click()
    info.assert_called_once()
    service.install_updates.assert_not_called()


def test_progress_changed_met_a_jour_la_barre(tab: SystemUpdateTab, service):
    service.progress_changed.emit(42)
    assert tab._progress.value() == 42
    assert tab._progress.isHidden() is False


def test_finished_reinitialise_letat(tab: SystemUpdateTab, service):
    service.updates_found.emit(_updates())
    tab._btn_install.click()
    assert tab._progress.isHidden() is False
    service.finished.emit()
    assert tab._progress.isHidden() is True
    assert tab._btn_install.isEnabled() is True


def test_error_affiche_messagebox(tab: SystemUpdateTab, service):
    with patch("widgets.system_tab.QMessageBox.critical") as critical:
        service.error_occurred.emit("dépôt injoignable")
    critical.assert_called_once()
    assert "dépôt injoignable" in critical.call_args.args


def test_install_permission_refusee_affiche_warning(tab: SystemUpdateTab, service):
    service.updates_found.emit(_updates())
    service.install_updates.side_effect = PermissionError("refusé")
    with patch("widgets.system_tab.QMessageBox.warning") as warning:
        tab._btn_install.click()
    warning.assert_called_once()
    # L'interface est revenue à l'état non occupé.
    assert tab._progress.isHidden() is True
    assert tab._btn_install.isEnabled() is True


def test_theme_applique_sur_les_boutons(tab: SystemUpdateTab):
    expected = ThemeManager().button_style()
    assert tab._btn_refresh.styleSheet() == expected
    assert tab._btn_install.styleSheet() == expected
