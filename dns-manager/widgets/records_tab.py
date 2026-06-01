"""Onglet « Enregistrements » : gestion des enregistrements A/CNAME/PTR d'une zone."""

from __future__ import annotations

import logging

from models.dns_record import RECORD_TYPES, DnsRecord
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
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

_COLUMNS = ("Nom", "Type", "Donnée")

# Erreurs métier remontées à l'utilisateur sans planter l'application.
_ACTION_ERRORS = (PermissionError, KeyError, RuntimeError)


class RecordDialog(QDialog):
    """Dialogue de saisie d'un enregistrement DNS (nom, type, donnée)."""

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
        """Construit le formulaire (nom, type, donnée)."""
        self.setWindowTitle("Ajouter un enregistrement")
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._edit_name = QLineEdit(self)
        self._combo_type = QComboBox(self)
        self._combo_type.addItems(RECORD_TYPES)
        self._edit_data = QLineEdit(self)
        form.addRow("Nom", self._edit_name)
        form.addRow("Type", self._combo_type)
        form.addRow("Donnée", self._edit_data)
        layout.addLayout(form)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self.setStyleSheet(self._theme.global_style())

    def values(self) -> dict[str, str]:
        """Retourne les valeurs saisies.

        Returns:
            Un mapping ``name``/``record_type``/``data``.
        """
        return {
            "name": self._edit_name.text().strip(),
            "record_type": self._combo_type.currentText(),
            "data": self._edit_data.text().strip(),
        }


class RecordsTab(QWidget):
    """Onglet de gestion des enregistrements d'une zone (ajouter / supprimer)."""

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
        self._records: list[DnsRecord] = []
        self._build_ui()
        self.reload_zones()

    def _build_ui(self) -> None:
        """Construit l'interface (sélecteur de zone, table, boutons d'action)."""
        layout = QVBoxLayout(self)

        selector = QHBoxLayout()
        selector.addWidget(QLabel("Zone", self))
        self._combo_zone = QComboBox(self)
        self._combo_zone.currentIndexChanged.connect(self._on_zone_changed)
        selector.addWidget(self._combo_zone, 1)
        layout.addLayout(selector)

        self._table = QTableWidget(0, len(_COLUMNS), self)
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setSectionResizeMode(
            len(_COLUMNS) - 1, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self._table)

        buttons = QHBoxLayout()
        self._btn_add = QPushButton("Ajouter", self)
        self._btn_delete = QPushButton("Supprimer", self)
        self._btn_add.clicked.connect(self._on_add_clicked)
        self._btn_delete.clicked.connect(self._on_delete_clicked)
        buttons.addWidget(self._btn_add)
        buttons.addWidget(self._btn_delete)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self._apply_theme()

    def _apply_theme(self) -> None:
        """Applique le thème courant aux widgets de l'onglet."""
        self.setStyleSheet(self._theme.global_style())
        self._btn_add.setStyleSheet(self._theme.button_style())
        self._btn_delete.setStyleSheet(self._theme.button_style())

    def reload_zones(self) -> None:
        """Recharge la liste des zones disponibles dans le sélecteur."""
        try:
            zones = self._service.list_zones()
        except _ACTION_ERRORS as exc:
            logger.error("Chargement des zones échoué: %s", exc)
            self._on_error(str(exc))
            return
        self._combo_zone.clear()
        self._combo_zone.addItems([zone.name for zone in zones])
        self.refresh()

    def _current_zone(self) -> str | None:
        """Retourne la zone sélectionnée, ou ``None`` si aucune."""
        zone = self._combo_zone.currentText().strip()
        return zone or None

    def refresh(self) -> None:
        """Recharge les enregistrements de la zone sélectionnée."""
        zone = self._current_zone()
        if zone is None:
            self._records = []
            self._table.setRowCount(0)
            return
        try:
            self._records = self._service.list_records(zone)
        except _ACTION_ERRORS as exc:
            logger.error("Chargement des enregistrements échoué: %s", exc)
            self._on_error(str(exc))
            return

        self._table.setRowCount(len(self._records))
        for row, record in enumerate(self._records):
            self._table.setItem(row, 0, QTableWidgetItem(record.name))
            self._table.setItem(row, 1, QTableWidgetItem(record.record_type))
            self._table.setItem(row, 2, QTableWidgetItem(record.data))

    def _selected_record(self) -> DnsRecord | None:
        """Retourne l'enregistrement de la ligne sélectionnée, ou ``None``."""
        row = self._table.currentRow()
        if row < 0 or row >= len(self._records):
            return None
        return self._records[row]

    def _on_zone_changed(self, _index: int) -> None:
        """Slot : recharge les enregistrements quand la zone change."""
        self.refresh()

    def _on_add_clicked(self) -> None:
        """Slot : ouvre le dialogue d'ajout et crée l'enregistrement."""
        zone = self._current_zone()
        if zone is None:
            QMessageBox.warning(self, "Aucune zone", "Sélectionnez d'abord une zone.")
            return
        dialog = RecordDialog(self._theme, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            self._service.add_record(
                zone, values["name"], values["record_type"], values["data"]
            )
        except _ACTION_ERRORS as exc:
            logger.error("Ajout d'enregistrement échoué: %s", exc)
            self._on_error(str(exc))
            return
        self.refresh()

    def _on_delete_clicked(self) -> None:
        """Slot : supprime l'enregistrement sélectionné après confirmation."""
        record = self._selected_record()
        if record is None:
            QMessageBox.warning(
                self, "Aucune sélection", "Sélectionnez un enregistrement à supprimer."
            )
            return
        confirm = QMessageBox.question(
            self,
            "Confirmer la suppression",
            f"Supprimer l'enregistrement {record.record_type} {record.name} ?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self._service.delete_record(
                record.zone, record.name, record.record_type, record.data
            )
        except _ACTION_ERRORS as exc:
            logger.error("Suppression d'enregistrement échouée: %s", exc)
            self._on_error(str(exc))
            return
        self.refresh()

    def _on_error(self, message: str) -> None:
        """Slot : affiche une erreur via ``QMessageBox``.

        Args:
            message: Message d'erreur à afficher.
        """
        QMessageBox.critical(self, "Erreur", message)
