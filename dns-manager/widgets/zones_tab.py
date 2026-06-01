"""Onglet « Zones » : liste des zones DNS hébergées par le domaine (lecture seule)."""

from __future__ import annotations

import logging

from models.dns_zone import DnsZone
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
from services.dns_service import DnsService

from core.theme import ThemeManager

logger = logging.getLogger(__name__)

_COLUMNS = ("Zone", "Type")
_TYPE_FORWARD = "Directe"
_TYPE_REVERSE = "Inverse"

# Erreurs métier remontées à l'utilisateur sans planter l'application.
_ACTION_ERRORS = (PermissionError, RuntimeError)


class ZonesTab(QWidget):
    """Onglet listant les zones DNS du domaine (lecture seule)."""

    def __init__(
        self,
        service: DnsService,
        theme: ThemeManager,
        parent: QWidget | None = None,
    ) -> None:
        """Initialise l'onglet.

        Args:
            service: Service des opérations DNS.
            theme: Gestionnaire de thème pour les styles.
            parent: Widget parent optionnel.
        """
        super().__init__(parent)
        self._service = service
        self._theme = theme
        self._zones: list[DnsZone] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Construit l'interface (table des zones, bouton Rafraîchir)."""
        layout = QVBoxLayout(self)

        self._table = QTableWidget(0, len(_COLUMNS), self)
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self._table)

        buttons = QHBoxLayout()
        self._btn_refresh = QPushButton("Rafraîchir", self)
        self._btn_refresh.clicked.connect(self._on_refresh_clicked)
        buttons.addWidget(self._btn_refresh)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self._apply_theme()

    def _apply_theme(self) -> None:
        """Applique le thème courant aux widgets de l'onglet."""
        self.setStyleSheet(self._theme.global_style())
        self._btn_refresh.setStyleSheet(self._theme.button_style())

    def refresh(self) -> None:
        """Recharge la liste des zones depuis le service."""
        try:
            self._zones = self._service.list_zones()
        except _ACTION_ERRORS as exc:
            logger.error("Chargement des zones échoué: %s", exc)
            self._on_error(str(exc))
            return

        self._table.setRowCount(len(self._zones))
        for row, zone in enumerate(self._zones):
            kind = _TYPE_REVERSE if zone.reverse else _TYPE_FORWARD
            self._table.setItem(row, 0, QTableWidgetItem(zone.name))
            self._table.setItem(row, 1, QTableWidgetItem(kind))

    def _on_refresh_clicked(self) -> None:
        """Slot : recharge la liste des zones."""
        self.refresh()

    def _on_error(self, message: str) -> None:
        """Slot : affiche une erreur via ``QMessageBox``.

        Args:
            message: Message d'erreur à afficher.
        """
        QMessageBox.critical(self, "Erreur", message)
