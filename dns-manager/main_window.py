"""Fenêtre principale du DNS Manager : onglets Zones / Enregistrements."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QMainWindow, QTabWidget, QWidget
from services.dns_service import DnsService
from widgets.records_tab import RecordsTab
from widgets.zones_tab import ZonesTab

from core.theme import ThemeManager

logger = logging.getLogger(__name__)

WINDOW_TITLE = "Fenix Server — Gestionnaire DNS"
WINDOW_ICON_NAME = "network-server"


class DnsManagerWindow(QMainWindow):
    """Fenêtre principale avec un ``QTabWidget`` à deux onglets.

    Onglets :
        - « Zones »          : zones DNS hébergées par le domaine (lecture seule).
        - « Enregistrements » : gestion des enregistrements A/CNAME/PTR d'une zone.
    """

    def __init__(self, theme: ThemeManager, parent: QWidget | None = None) -> None:
        """Initialise la fenêtre, le service et les onglets.

        Args:
            theme: Gestionnaire de thème appliqué à la fenêtre.
            parent: Widget parent optionnel.
        """
        super().__init__(parent)
        self._theme = theme
        self.dns_service = DnsService()
        self._build_ui()

    def _build_ui(self) -> None:
        """Construit la barre d'onglets et instancie les deux onglets."""
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowIcon(self._theme.icon(WINDOW_ICON_NAME))
        self.setStyleSheet(self._theme.global_style())

        self.zones_tab = ZonesTab(self.dns_service, self._theme, self)
        self.records_tab = RecordsTab(self.dns_service, self._theme, self)

        self._tabs = QTabWidget(self)
        self._tabs.addTab(self.zones_tab, "Zones")
        self._tabs.addTab(self.records_tab, "Enregistrements")
        self.setCentralWidget(self._tabs)
