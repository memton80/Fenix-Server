"""Vue dashboard : état des rôles et boutons activer/désactiver."""

from __future__ import annotations

import logging

from dasbus.error import DBusError
from models.role_status import RoleStatus
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
from services.role_service import RoleService

from core.theme import ThemeManager

logger = logging.getLogger(__name__)

_COLUMNS = ("Nom", "État", "Description")
_STATE_ACTIVE = "Actif"
_STATE_INACTIVE = "Inactif"

# Erreurs métier remontées à l'utilisateur sans planter l'application.
_ACTION_ERRORS = (PermissionError, RuntimeError, DBusError)


class DashboardWidget(QWidget):
    """Dashboard listant les rôles (actif/inactif) avec actions d'activation."""

    def __init__(
        self,
        service: RoleService,
        theme: ThemeManager,
        parent: QWidget | None = None,
    ) -> None:
        """Initialise le dashboard.

        Args:
            service: Service d'activation/désactivation des rôles.
            theme: Gestionnaire de thème pour les styles.
            parent: Widget parent optionnel.
        """
        super().__init__(parent)
        self._service = service
        self._theme = theme
        self._statuses: list[RoleStatus] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Construit l'interface (table des rôles, boutons Activer/Désactiver)."""
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
        self._btn_activate = QPushButton("Activer", self)
        self._btn_deactivate = QPushButton("Désactiver", self)
        self._btn_refresh.clicked.connect(self._on_refresh_clicked)
        self._btn_activate.clicked.connect(self._on_activate_clicked)
        self._btn_deactivate.clicked.connect(self._on_deactivate_clicked)
        buttons.addWidget(self._btn_refresh)
        buttons.addWidget(self._btn_activate)
        buttons.addWidget(self._btn_deactivate)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self._apply_theme()

    def _apply_theme(self) -> None:
        """Applique le thème courant aux widgets du dashboard."""
        self.setStyleSheet(self._theme.global_style())
        self._btn_refresh.setStyleSheet(self._theme.button_style())
        self._btn_activate.setStyleSheet(self._theme.button_style())
        self._btn_deactivate.setStyleSheet(self._theme.button_style())

    def refresh(self) -> None:
        """Recharge l'état des rôles depuis le service et met à jour la table."""
        try:
            self._statuses = self._service.list_roles()
        except _ACTION_ERRORS as exc:
            logger.error("Chargement des rôles échoué: %s", exc)
            self._on_error(str(exc))
            return

        self._table.setRowCount(len(self._statuses))
        for row, status in enumerate(self._statuses):
            etat = _STATE_ACTIVE if status.active else _STATE_INACTIVE
            self._table.setItem(row, 0, QTableWidgetItem(status.role.name))
            self._table.setItem(row, 1, QTableWidgetItem(etat))
            self._table.setItem(row, 2, QTableWidgetItem(status.role.description))

    def _selected_status(self) -> RoleStatus | None:
        """Retourne le :class:`RoleStatus` de la ligne sélectionnée, ou ``None``."""
        row = self._table.currentRow()
        if row < 0 or row >= len(self._statuses):
            return None
        return self._statuses[row]

    def _on_refresh_clicked(self) -> None:
        """Slot : rafraîchit l'état des rôles."""
        self.refresh()

    def _on_activate_clicked(self) -> None:
        """Slot : active le rôle sélectionné."""
        status = self._selected_status()
        if status is None:
            QMessageBox.warning(self, "Aucune sélection", "Sélectionnez un rôle à activer.")
            return
        if status.active:
            QMessageBox.information(self, "Déjà actif", f"{status.role.name} est déjà actif.")
            return
        try:
            self._service.enable_role(status.role.id)
        except _ACTION_ERRORS as exc:
            logger.error("Activation de %s échouée: %s", status.role.id, exc)
            self._on_error(str(exc))
            return
        self.refresh()

    def _on_deactivate_clicked(self) -> None:
        """Slot : désactive le rôle sélectionné."""
        status = self._selected_status()
        if status is None:
            QMessageBox.warning(self, "Aucune sélection", "Sélectionnez un rôle à désactiver.")
            return
        if not status.active:
            QMessageBox.information(self, "Déjà inactif", f"{status.role.name} est déjà inactif.")
            return
        try:
            self._service.disable_role(status.role.id)
        except _ACTION_ERRORS as exc:
            logger.error("Désactivation de %s échouée: %s", status.role.id, exc)
            self._on_error(str(exc))
            return
        self.refresh()

    def _on_error(self, message: str) -> None:
        """Slot : affiche une erreur via ``QMessageBox``.

        Args:
            message: Message d'erreur à afficher.
        """
        QMessageBox.critical(self, "Erreur", message)
