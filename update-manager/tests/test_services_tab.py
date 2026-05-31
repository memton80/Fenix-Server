"""Tests pour widgets.services_tab — GitHubReleaseService et QThread mockés."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.theme import ThemeManager
from models.update_item import ServiceUpdate
from widgets.services_tab import ServicesUpdateTab, _CheckWorker


@pytest.fixture
def service() -> MagicMock:
    return MagicMock()


@pytest.fixture
def tab(service: MagicMock) -> ServicesUpdateTab:
    return ServicesUpdateTab(service, ThemeManager())


def _updates() -> list[ServiceUpdate]:
    return [
        ServiceUpdate("ad", "ad", "1.0.0", "1.2.0", "https://x/ad"),
        ServiceUpdate("upd", "upd", "2.0.0", "2.0.0", "https://x/upd"),
    ]


# --- état initial / construction ------------------------------------------


def test_etat_initial(tab: ServicesUpdateTab):
    assert tab._table.rowCount() == 0


def test_theme_applique_sur_les_boutons(tab: ServicesUpdateTab):
    expected = ThemeManager().button_style()
    assert tab._btn_check.styleSheet() == expected
    assert tab._btn_update.styleSheet() == expected


# --- vérification dans un thread ------------------------------------------


def test_verifier_demarre_un_worker_dans_un_thread(tab: ServicesUpdateTab, service):
    tab.set_services({"ad": ("fenix/ad", "1.0.0")})
    with patch("widgets.services_tab._CheckWorker") as worker_cls:
        worker = worker_cls.return_value
        worker.isRunning.return_value = False
        tab._btn_check.click()

    worker_cls.assert_called_once_with(service, {"ad": ("fenix/ad", "1.0.0")}, tab)
    worker.start.assert_called_once_with()
    worker.checked.connect.assert_called_once()
    worker.failed.connect.assert_called_once()


def test_worker_run_emet_checked(service):
    service.check_all.return_value = _updates()
    worker = _CheckWorker(service, {"ad": ("fenix/ad", "1.0.0")})
    received: list = []
    worker.checked.connect(received.append)

    worker.run()  # exécution synchrone directe (pas via start())

    service.check_all.assert_called_once_with({"ad": ("fenix/ad", "1.0.0")})
    assert received == [_updates()] or received[0][0].service_id == "ad"


def test_worker_run_emet_failed_sur_exception(service):
    service.check_all.side_effect = RuntimeError("boom")
    worker = _CheckWorker(service, {})
    errors: list = []
    worker.failed.connect(errors.append)

    worker.run()

    assert errors and "boom" in errors[0]


# --- affichage des résultats ----------------------------------------------


def test_services_checked_peuple_la_table(tab: ServicesUpdateTab):
    tab._on_services_checked(_updates())
    assert tab._table.rowCount() == 2
    assert tab._table.item(0, 0).text() == "ad"
    assert tab._table.item(0, 1).text() == "1.0.0"
    assert tab._table.item(0, 2).text() == "1.2.0"
    assert tab._table.item(0, 3).text() == "Mise à jour disponible"
    assert tab._table.item(1, 3).text() == "À jour"


# --- bouton Mettre à jour --------------------------------------------------


def test_update_sans_selection_affiche_warning(tab: ServicesUpdateTab):
    tab._on_services_checked(_updates())
    tab._table.clearSelection()
    tab._table.setCurrentCell(-1, -1)
    with patch("widgets.services_tab.QMessageBox.warning") as warning:
        tab._btn_update.click()
    warning.assert_called_once()


def test_update_service_a_jour_affiche_info(tab: ServicesUpdateTab):
    tab._on_services_checked(_updates())
    tab._table.selectRow(1)  # service "upd" déjà à jour
    with patch("widgets.services_tab.QMessageBox.information") as info:
        tab._btn_update.click()
    info.assert_called_once()


def test_update_service_disponible_affiche_info(tab: ServicesUpdateTab):
    tab._on_services_checked(_updates())
    tab._table.selectRow(0)  # service "ad" avec mise à jour
    with patch("widgets.services_tab.QMessageBox.information") as info:
        tab._btn_update.click()
    info.assert_called_once()
    assert "1.2.0" in info.call_args.args[2]


# --- erreur ----------------------------------------------------------------


def test_error_affiche_messagebox(tab: ServicesUpdateTab):
    with patch("widgets.services_tab.QMessageBox.critical") as critical:
        tab._on_error("réseau indisponible")
    critical.assert_called_once()
    assert "réseau indisponible" in critical.call_args.args
