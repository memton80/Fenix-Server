"""Fenêtre principale du DHCP Manager : onglets Baux / Plages / Réservations."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QMainWindow, QTabWidget, QWidget
from services.kea_service import KeaService
from widgets.leases_tab import LeasesTab
from widgets.reservations_tab import ReservationsTab
from widgets.subnets_tab import SubnetsTab

from core.theme import ThemeManager

logger = logging.getLogger(__name__)

WINDOW_TITLE = "Fenix Server — Gestionnaire DHCP"
WINDOW_ICON_NAME = "network-wired"


class DhcpManagerWindow(QMainWindow):
    """Fenêtre principale avec un ``QTabWidget`` à trois onglets.

    Onglets :
        - « Baux actifs »  : baux DHCP en cours et contrôle du service.
        - « Plages »       : gestion des plages (subnets) d'attribution.
        - « Réservations » : réservations MAC → IP par plage.
    """

    def __init__(self, theme: ThemeManager, parent: QWidget | None = None) -> None:
        """Initialise la fenêtre, le service et les onglets.

        Args:
            theme: Gestionnaire de thème appliqué à la fenêtre.
            parent: Widget parent optionnel.
        """
        super().__init__(parent)
        self._theme = theme
        self.kea_service = KeaService()
        self._build_ui()

    def _build_ui(self) -> None:
        """Construit la barre d'onglets et instancie les trois onglets."""
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowIcon(self._theme.icon(WINDOW_ICON_NAME))
        self.setStyleSheet(self._theme.global_style())

        self.leases_tab = LeasesTab(self.kea_service, self._theme, self)
        self.subnets_tab = SubnetsTab(self.kea_service, self._theme, self)
        self.reservations_tab = ReservationsTab(self.kea_service, self._theme, self)

        self._tabs = QTabWidget(self)
        self._tabs.addTab(self.leases_tab, "Baux actifs")
        self._tabs.addTab(self.subnets_tab, "Plages")
        self._tabs.addTab(self.reservations_tab, "Réservations")
        self.setCentralWidget(self._tabs)
