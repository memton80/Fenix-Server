"""Onglet « Plages » : gestion des plages (subnets) DHCP Kea."""

from __future__ import annotations

import logging

from models.dhcp_subnet import DhcpSubnet
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
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from services.kea_service import KeaService

from core.theme import ThemeManager

logger = logging.getLogger(__name__)

_COLUMNS = ("ID", "Réseau", "Plage d'attribution")
_MAX_SUBNET_ID = 9999

# Erreurs métier remontées à l'utilisateur sans planter l'application.
_ACTION_ERRORS = (PermissionError, RuntimeError)


class SubnetDialog(QDialog):
    """Dialogue de saisie d'une plage DHCP (ID, réseau, pool).

    En mode modification (``subnet`` fourni), l'ID est verrouillé.
    """

    def __init__(
        self,
        theme: ThemeManager,
        subnet: DhcpSubnet | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Initialise le dialogue.

        Args:
            theme: Gestionnaire de thème pour les styles.
            subnet: Plage à pré-remplir (mode modification), ou ``None``.
            parent: Widget parent optionnel.
        """
        super().__init__(parent)
        self._theme = theme
        self._subnet = subnet
        self._build_ui()

    def _build_ui(self) -> None:
        """Construit le formulaire (ID, réseau, pool)."""
        self.setWindowTitle("Modifier la plage" if self._subnet else "Créer une plage")
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._spin_id = QSpinBox(self)
        self._spin_id.setRange(1, _MAX_SUBNET_ID)
        self._edit_subnet = QLineEdit(self)
        self._edit_subnet.setPlaceholderText("192.168.1.0/24")
        self._edit_pool = QLineEdit(self)
        self._edit_pool.setPlaceholderText("192.168.1.100-192.168.1.200")

        if self._subnet is not None:
            self._spin_id.setValue(self._subnet.subnet_id)
            self._spin_id.setEnabled(False)  # l'ID identifie la plage à remplacer
            self._edit_subnet.setText(self._subnet.subnet)
            self._edit_pool.setText(self._subnet.pool)

        form.addRow("ID", self._spin_id)
        form.addRow("Réseau (CIDR)", self._edit_subnet)
        form.addRow("Plage", self._edit_pool)
        layout.addLayout(form)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self.setStyleSheet(self._theme.global_style())

    def values(self) -> dict[str, object]:
        """Retourne les valeurs saisies.

        Returns:
            Un mapping ``subnet_id``/``subnet``/``pool``.
        """
        return {
            "subnet_id": self._spin_id.value(),
            "subnet": self._edit_subnet.text().strip(),
            "pool": self._edit_pool.text().strip(),
        }


class SubnetsTab(QWidget):
    """Onglet de gestion des plages DHCP (créer / modifier)."""

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
        self._subnets: list[DhcpSubnet] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Construit l'interface (table des plages, boutons d'action)."""
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
        self._btn_modify = QPushButton("Modifier", self)
        self._btn_create.clicked.connect(self._on_create_clicked)
        self._btn_modify.clicked.connect(self._on_modify_clicked)
        buttons.addWidget(self._btn_create)
        buttons.addWidget(self._btn_modify)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self._apply_theme()

    def _apply_theme(self) -> None:
        """Applique le thème courant aux widgets de l'onglet."""
        self.setStyleSheet(self._theme.global_style())
        self._btn_create.setStyleSheet(self._theme.button_style())
        self._btn_modify.setStyleSheet(self._theme.button_style())

    def refresh(self) -> None:
        """Recharge la liste des plages depuis le service."""
        try:
            self._subnets = self._service.list_subnets()
        except _ACTION_ERRORS as exc:
            logger.error("Chargement des plages échoué: %s", exc)
            self._on_error(str(exc))
            return

        self._table.setRowCount(len(self._subnets))
        for row, subnet in enumerate(self._subnets):
            self._table.setItem(row, 0, QTableWidgetItem(str(subnet.subnet_id)))
            self._table.setItem(row, 1, QTableWidgetItem(subnet.subnet))
            self._table.setItem(row, 2, QTableWidgetItem(subnet.pool))

    def _selected_subnet(self) -> DhcpSubnet | None:
        """Retourne la plage de la ligne sélectionnée, ou ``None``."""
        row = self._table.currentRow()
        if row < 0 or row >= len(self._subnets):
            return None
        return self._subnets[row]

    def _next_subnet_id(self) -> int:
        """Retourne un identifiant de subnet libre (max connu + 1)."""
        return max((subnet.subnet_id for subnet in self._subnets), default=0) + 1

    def _on_create_clicked(self) -> None:
        """Slot : ouvre le dialogue de création et enregistre la plage."""
        dialog = SubnetDialog(self._theme, parent=self)
        dialog._spin_id.setValue(self._next_subnet_id())
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._save(dialog.values())

    def _on_modify_clicked(self) -> None:
        """Slot : ouvre le dialogue pré-rempli et enregistre la plage."""
        subnet = self._selected_subnet()
        if subnet is None:
            QMessageBox.warning(self, "Aucune sélection", "Sélectionnez une plage à modifier.")
            return
        dialog = SubnetDialog(self._theme, subnet=subnet, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._save(dialog.values())

    def _save(self, values: dict[str, object]) -> None:
        """Enregistre une plage via le service puis rafraîchit la table."""
        try:
            self._service.set_subnet(
                str(values["subnet"]),
                str(values["pool"]),
                subnet_id=int(values["subnet_id"]),
            )
        except _ACTION_ERRORS as exc:
            logger.error("Enregistrement de la plage échoué: %s", exc)
            self._on_error(str(exc))
            return
        self.refresh()

    def _on_error(self, message: str) -> None:
        """Slot : affiche une erreur via ``QMessageBox``.

        Args:
            message: Message d'erreur à afficher.
        """
        QMessageBox.critical(self, "Erreur", message)
