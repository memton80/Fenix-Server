"""Onglet « Système » : mises à jour des paquets via PackageKit."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.theme import ThemeManager
from models.update_item import SystemPackageUpdate
from services.packagekit_service import PackageKitService

_COLUMNS = ("Paquet", "Version", "Résumé")


class SystemUpdateTab(QWidget):
    """Onglet listant et appliquant les mises à jour système (PackageKit)."""

    def __init__(
        self,
        service: PackageKitService,
        theme: ThemeManager,
        parent: QWidget | None = None,
    ) -> None:
        """Initialise l'onglet.

        Args:
            service: Service PackageKit fournissant les mises à jour système.
            theme: Gestionnaire de thème pour les styles.
            parent: Widget parent optionnel.
        """
        super().__init__(parent)
        self._service = service
        self._theme = theme
        self._updates: list[SystemPackageUpdate] = []
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        """Construit l'interface (liste des paquets, boutons, barre de progression)."""
        layout = QVBoxLayout(self)

        self._table = QTableWidget(0, len(_COLUMNS), self)
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setSectionResizeMode(
            len(_COLUMNS) - 1, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self._table)

        self._progress = QProgressBar(self)
        self._progress.setRange(0, 100)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        buttons = QHBoxLayout()
        self._btn_refresh = QPushButton("Rafraîchir", self)
        self._btn_install = QPushButton("Installer", self)
        self._btn_refresh.clicked.connect(self._on_refresh_clicked)
        self._btn_install.clicked.connect(self._on_install_clicked)
        buttons.addWidget(self._btn_refresh)
        buttons.addWidget(self._btn_install)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self._apply_theme()

    def _apply_theme(self) -> None:
        """Applique le thème courant aux widgets de l'onglet."""
        self.setStyleSheet(self._theme.global_style())
        self._btn_refresh.setStyleSheet(self._theme.button_style())
        self._btn_install.setStyleSheet(self._theme.button_style())

    def _connect_signals(self) -> None:
        """Connecte les signaux du service PackageKit aux slots de l'onglet."""
        self._service.updates_found.connect(self._on_updates_found)
        self._service.progress_changed.connect(self._on_progress_changed)
        self._service.finished.connect(self._on_finished)
        self._service.error_occurred.connect(self._on_error)

    def _set_busy(self, busy: bool) -> None:
        """Active/désactive les boutons et affiche la barre de progression."""
        self._btn_refresh.setEnabled(not busy)
        self._btn_install.setEnabled(not busy)
        self._progress.setVisible(busy)
        if busy:
            self._progress.setValue(0)

    def _on_refresh_clicked(self) -> None:
        """Slot : demande la liste des mises à jour disponibles."""
        self._service.request_updates()

    def _on_install_clicked(self) -> None:
        """Slot : installe toutes les mises à jour système listées."""
        if not self._updates:
            QMessageBox.information(self, "Mises à jour", "Aucune mise à jour à installer.")
            return
        package_ids = [update.package_id for update in self._updates]
        self._set_busy(True)
        try:
            self._service.install_updates(package_ids)
        except PermissionError:
            self._set_busy(False)
            QMessageBox.warning(
                self, "Autorisation refusée", "L'installation a été refusée par Polkit."
            )

    def _on_updates_found(self, updates: list) -> None:
        """Slot : peuple la liste avec les mises à jour trouvées.

        Args:
            updates: Liste de ``SystemPackageUpdate`` émise par le service.
        """
        self._updates = list(updates)
        self._table.setRowCount(len(self._updates))
        for row, update in enumerate(self._updates):
            self._table.setItem(row, 0, QTableWidgetItem(update.name))
            self._table.setItem(row, 1, QTableWidgetItem(update.version))
            self._table.setItem(row, 2, QTableWidgetItem(update.summary))

    def _on_progress_changed(self, percent: int) -> None:
        """Slot : met à jour la barre de progression.

        Args:
            percent: Avancement de la transaction (0-100).
        """
        self._progress.setVisible(True)
        self._progress.setValue(percent)

    def _on_finished(self) -> None:
        """Slot : transaction terminée — réinitialise l'état de l'interface."""
        self._set_busy(False)

    def _on_error(self, message: str) -> None:
        """Slot : affiche une erreur via ``QMessageBox``.

        Args:
            message: Message d'erreur à afficher.
        """
        self._set_busy(False)
        QMessageBox.critical(self, "Erreur", message)
