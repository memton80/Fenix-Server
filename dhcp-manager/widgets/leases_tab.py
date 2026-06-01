"""Onglet « Baux actifs » : liste des baux DHCP et contrôle du service Kea."""

from __future__ import annotations

import logging

from models.dhcp_lease import DhcpLease
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from services.kea_service import KeaService

from core.theme import ThemeManager

logger = logging.getLogger(__name__)

_COLUMNS = ("Adresse IP", "Adresse MAC", "Nom d'hôte", "État")

# Erreurs métier remontées à l'utilisateur sans planter l'application.
_ACTION_ERRORS = (PermissionError, RuntimeError)


class LeasesTab(QWidget):
    """Onglet listant les baux DHCP actifs et permettant de piloter le service."""

    def __init__(
        self,
        service: KeaService,
        theme: ThemeManager,
        parent: QWidget | None = None,
    ) -> None:
        """Initialise l'onglet.

        Args:
            service: Service des opérations Kea.
            theme: Gestionnaire de thème pour les styles.
            parent: Widget parent optionnel.
        """
        super().__init__(parent)
        self._service = service
        self._theme = theme
        self._leases: list[DhcpLease] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Construit l'interface (table des baux, boutons service/rafraîchir)."""
        layout = QVBoxLayout(self)

        self._table = QTableWidget(0, len(_COLUMNS), self)
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setSectionResizeMode(
            len(_COLUMNS) - 1, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self._table)

        buttons = QHBoxLayout()
        self._btn_refresh = QPushButton("Rafraîchir", self)
        self._btn_restart = QPushButton("Redémarrer le service", self)
        self._btn_refresh.clicked.connect(self._on_refresh_clicked)
        self._btn_restart.clicked.connect(self._on_restart_clicked)
        buttons.addWidget(self._btn_refresh)
        buttons.addStretch(1)
        buttons.addWidget(self._btn_restart)
        layout.addLayout(buttons)

        self._apply_theme()

    def _apply_theme(self) -> None:
        """Applique le thème courant aux widgets de l'onglet."""
        self.setStyleSheet(self._theme.global_style())
        self._btn_refresh.setStyleSheet(self._theme.button_style())
        self._btn_restart.setStyleSheet(self._theme.button_style())

    def refresh(self) -> None:
        """Recharge la liste des baux depuis le service."""
        try:
            self._leases = self._service.list_leases()
        except _ACTION_ERRORS as exc:
            logger.error("Chargement des baux échoué: %s", exc)
            self._on_error(str(exc))
            return

        self._table.setRowCount(len(self._leases))
        for row, lease in enumerate(self._leases):
            self._table.setItem(row, 0, QTableWidgetItem(lease.ip_address))
            self._table.setItem(row, 1, QTableWidgetItem(lease.mac_address))
            self._table.setItem(row, 2, QTableWidgetItem(lease.hostname))
            self._table.setItem(row, 3, QTableWidgetItem(lease.state))

    def _on_refresh_clicked(self) -> None:
        """Slot : recharge la liste des baux."""
        self.refresh()

    def _on_restart_clicked(self) -> None:
        """Slot : redémarre le service Kea après confirmation."""
        confirm = QMessageBox.question(
            self, "Confirmer", "Redémarrer le service DHCP (Kea) ?"
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self._service.control_service("restart")
        except (ValueError, *_ACTION_ERRORS) as exc:
            logger.error("Redémarrage du service échoué: %s", exc)
            self._on_error(str(exc))
            return
        self.refresh()

    def _on_error(self, message: str) -> None:
        """Slot : affiche une erreur via ``QMessageBox``.

        Args:
            message: Message d'erreur à afficher.
        """
        QMessageBox.critical(self, "Erreur", message)
