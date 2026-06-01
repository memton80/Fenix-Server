"""Onglet « Réservations » : gestion des réservations MAC → IP d'un subnet."""

from __future__ import annotations

import logging

from models.dhcp_reservation import DhcpReservation
from models.dhcp_subnet import DhcpSubnet
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
from services.kea_service import KeaService

from core.theme import ThemeManager

logger = logging.getLogger(__name__)

_COLUMNS = ("Adresse MAC", "Adresse IP", "Nom d'hôte")

# Erreurs métier remontées à l'utilisateur sans planter l'application.
_ACTION_ERRORS = (PermissionError, RuntimeError)


class ReservationDialog(QDialog):
    """Dialogue de saisie d'une réservation DHCP (MAC, IP, nom d'hôte)."""

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
        """Construit le formulaire (MAC, IP, nom d'hôte)."""
        self.setWindowTitle("Ajouter une réservation")
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._edit_mac = QLineEdit(self)
        self._edit_mac.setPlaceholderText("aa:bb:cc:dd:ee:ff")
        self._edit_ip = QLineEdit(self)
        self._edit_ip.setPlaceholderText("192.168.1.50")
        self._edit_hostname = QLineEdit(self)
        form.addRow("Adresse MAC", self._edit_mac)
        form.addRow("Adresse IP", self._edit_ip)
        form.addRow("Nom d'hôte", self._edit_hostname)
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
            Un mapping ``mac_address``/``ip_address``/``hostname``.
        """
        return {
            "mac_address": self._edit_mac.text().strip(),
            "ip_address": self._edit_ip.text().strip(),
            "hostname": self._edit_hostname.text().strip(),
        }


class ReservationsTab(QWidget):
    """Onglet de gestion des réservations d'un subnet (ajouter)."""

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
        self._reservations: list[DhcpReservation] = []
        self._build_ui()
        self.reload_subnets()

    def _build_ui(self) -> None:
        """Construit l'interface (sélecteur de subnet, table, bouton Ajouter)."""
        layout = QVBoxLayout(self)

        selector = QHBoxLayout()
        selector.addWidget(QLabel("Plage", self))
        self._combo_subnet = QComboBox(self)
        self._combo_subnet.currentIndexChanged.connect(self._on_subnet_changed)
        selector.addWidget(self._combo_subnet, 1)
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
        self._btn_add.clicked.connect(self._on_add_clicked)
        buttons.addWidget(self._btn_add)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self._apply_theme()

    def _apply_theme(self) -> None:
        """Applique le thème courant aux widgets de l'onglet."""
        self.setStyleSheet(self._theme.global_style())
        self._btn_add.setStyleSheet(self._theme.button_style())

    def reload_subnets(self) -> None:
        """Recharge la liste des subnets disponibles dans le sélecteur."""
        try:
            self._subnets = self._service.list_subnets()
        except _ACTION_ERRORS as exc:
            logger.error("Chargement des plages échoué: %s", exc)
            self._on_error(str(exc))
            return
        self._combo_subnet.clear()
        for subnet in self._subnets:
            self._combo_subnet.addItem(f"{subnet.subnet_id} — {subnet.subnet}", subnet.subnet_id)
        self.refresh()

    def _current_subnet_id(self) -> int | None:
        """Retourne l'ID du subnet sélectionné, ou ``None`` si aucun."""
        data = self._combo_subnet.currentData()
        return int(data) if data is not None else None

    def refresh(self) -> None:
        """Recharge les réservations du subnet sélectionné."""
        subnet_id = self._current_subnet_id()
        if subnet_id is None:
            self._reservations = []
            self._table.setRowCount(0)
            return
        try:
            self._reservations = self._service.list_reservations(subnet_id)
        except _ACTION_ERRORS as exc:
            logger.error("Chargement des réservations échoué: %s", exc)
            self._on_error(str(exc))
            return

        self._table.setRowCount(len(self._reservations))
        for row, reservation in enumerate(self._reservations):
            self._table.setItem(row, 0, QTableWidgetItem(reservation.mac_address))
            self._table.setItem(row, 1, QTableWidgetItem(reservation.ip_address))
            self._table.setItem(row, 2, QTableWidgetItem(reservation.hostname))

    def _on_subnet_changed(self, _index: int) -> None:
        """Slot : recharge les réservations quand le subnet change."""
        self.refresh()

    def _on_add_clicked(self) -> None:
        """Slot : ouvre le dialogue d'ajout et crée la réservation."""
        subnet_id = self._current_subnet_id()
        if subnet_id is None:
            QMessageBox.warning(self, "Aucune plage", "Sélectionnez d'abord une plage.")
            return
        dialog = ReservationDialog(self._theme, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        reservation = DhcpReservation(
            mac_address=values["mac_address"],
            ip_address=values["ip_address"],
            hostname=values["hostname"],
            subnet_id=subnet_id,
        )
        try:
            self._service.add_reservation(reservation)
        except _ACTION_ERRORS as exc:
            logger.error("Ajout de réservation échoué: %s", exc)
            self._on_error(str(exc))
            return
        self.refresh()

    def _on_error(self, message: str) -> None:
        """Slot : affiche une erreur via ``QMessageBox``.

        Args:
            message: Message d'erreur à afficher.
        """
        QMessageBox.critical(self, "Erreur", message)
