"""Onglet « Groupes » : liste des groupes et actions de gestion."""

from __future__ import annotations

import logging

from models.ad_group import ADGroup
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from services.ad_service import ADService

from core.theme import ThemeManager

logger = logging.getLogger(__name__)

_COLUMNS = ("Nom", "Description", "Membres")

# Erreurs métier remontées à l'utilisateur sans planter l'application.
_ACTION_ERRORS = (PermissionError, KeyError, RuntimeError)


class GroupDialog(QDialog):
    """Dialogue de création d'un groupe (nom, description)."""

    def __init__(self, theme: ThemeManager, parent: QWidget | None = None) -> None:
        """Initialise le dialogue.

        Args:
            theme: Gestionnaire de thème pour les styles.
            parent: Widget parent optionnel.
        """
        super().__init__(parent)
        self._theme = theme
        self._build_ui()

    def _build_ui(self) -> None:
        """Construit le formulaire (nom, description)."""
        self.setWindowTitle("Créer un groupe")
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._edit_name = QLineEdit(self)
        self._edit_description = QLineEdit(self)
        form.addRow("Nom", self._edit_name)
        form.addRow("Description", self._edit_description)
        layout.addLayout(form)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self.setStyleSheet(self._theme.global_style())

    def values(self) -> dict[str, str]:
        """Retourne les valeurs saisies (``name``/``description``)."""
        return {
            "name": self._edit_name.text().strip(),
            "description": self._edit_description.text().strip(),
        }


class GroupsTab(QWidget):
    """Onglet listant les groupes du domaine (créer / supprimer)."""

    def __init__(
        self,
        service: ADService,
        theme: ThemeManager,
        parent: QWidget | None = None,
    ) -> None:
        """Initialise l'onglet.

        Args:
            service: Service des opérations AD.
            theme: Gestionnaire de thème pour les styles.
            parent: Widget parent optionnel.
        """
        super().__init__(parent)
        self._service = service
        self._theme = theme
        self._groups: list[ADGroup] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Construit l'interface (table des groupes, boutons d'action)."""
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
        self._btn_create = QPushButton("Créer", self)
        self._btn_delete = QPushButton("Supprimer", self)
        self._btn_create.clicked.connect(self._on_create_clicked)
        self._btn_delete.clicked.connect(self._on_delete_clicked)
        buttons.addWidget(self._btn_create)
        buttons.addWidget(self._btn_delete)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self._apply_theme()

    def _apply_theme(self) -> None:
        """Applique le thème courant aux widgets de l'onglet."""
        self.setStyleSheet(self._theme.global_style())
        self._btn_create.setStyleSheet(self._theme.button_style())
        self._btn_delete.setStyleSheet(self._theme.button_style())

    def refresh(self) -> None:
        """Recharge la liste des groupes depuis le service."""
        try:
            self._groups = self._service.list_groups()
        except _ACTION_ERRORS as exc:
            logger.error("Chargement des groupes échoué: %s", exc)
            self._on_error(str(exc))
            return

        self._table.setRowCount(len(self._groups))
        for row, group in enumerate(self._groups):
            self._table.setItem(row, 0, QTableWidgetItem(group.name))
            self._table.setItem(row, 1, QTableWidgetItem(group.description))
            self._table.setItem(row, 2, QTableWidgetItem(str(len(group.members))))

    def _selected_group(self) -> ADGroup | None:
        """Retourne le groupe de la ligne sélectionnée, ou ``None``."""
        row = self._table.currentRow()
        if row < 0 or row >= len(self._groups):
            return None
        return self._groups[row]

    def _on_create_clicked(self) -> None:
        """Slot : ouvre le dialogue de création et crée le groupe."""
        dialog = GroupDialog(self._theme, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            self._service.create_group(values["name"], description=values["description"])
        except _ACTION_ERRORS as exc:
            logger.error("Création de groupe échouée: %s", exc)
            self._on_error(str(exc))
            return
        self.refresh()

    def _on_delete_clicked(self) -> None:
        """Slot : supprime le groupe sélectionné après confirmation."""
        group = self._selected_group()
        if group is None:
            QMessageBox.warning(self, "Aucune sélection", "Sélectionnez un groupe à supprimer.")
            return
        confirm = QMessageBox.question(
            self, "Confirmer la suppression", f"Supprimer le groupe {group.name} ?"
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self._service.delete_group(group.name)
        except _ACTION_ERRORS as exc:
            logger.error("Suppression de groupe échouée: %s", exc)
            self._on_error(str(exc))
            return
        self.refresh()

    def _on_error(self, message: str) -> None:
        """Slot : affiche une erreur via ``QMessageBox``.

        Args:
            message: Message d'erreur à afficher.
        """
        QMessageBox.critical(self, "Erreur", message)
