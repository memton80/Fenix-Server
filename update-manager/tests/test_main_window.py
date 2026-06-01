"""Tests pour main_window — assemblage des deux onglets (Qt offscreen)."""

from __future__ import annotations

import pytest
from main_window import WINDOW_TITLE, UpdateManagerWindow
from widgets.services_tab import ServicesUpdateTab
from widgets.system_tab import SystemUpdateTab

from core.theme import ThemeManager


@pytest.fixture
def window() -> UpdateManagerWindow:
    return UpdateManagerWindow(ThemeManager())


def test_titre_de_la_fenetre(window: UpdateManagerWindow):
    assert window.windowTitle() == WINDOW_TITLE
    assert window.windowTitle() == "Fenix Server — Gestionnaire de mises à jour"


def test_deux_onglets_systeme_et_services(window: UpdateManagerWindow):
    tabs = window._tabs
    assert tabs.count() == 2
    assert tabs.tabText(0) == "Système"
    assert tabs.tabText(1) == "Services"


def test_les_onglets_sont_du_bon_type(window: UpdateManagerWindow):
    assert isinstance(window.system_tab, SystemUpdateTab)
    assert isinstance(window.services_tab, ServicesUpdateTab)


def test_les_onglets_partagent_les_services_de_la_fenetre(window: UpdateManagerWindow):
    assert window.system_tab._service is window.packagekit_service
    assert window.services_tab._service is window.github_service


def test_icone_appliquee(window: UpdateManagerWindow):
    # Une icône (même vide en environnement sans thème) doit être posée.
    assert window.windowIcon() is not None


def test_style_global_applique(window: UpdateManagerWindow):
    assert window.styleSheet() == ThemeManager().global_style()
