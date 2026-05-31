"""Onglet « Services » : mises à jour des services Fenix via GitHub Releases.

``GitHubReleaseService`` est synchrone (requêtes HTTP bloquantes) ; il est donc
exécuté dans un :class:`QThread` dédié pour ne pas geler l'interface.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QThread, Signal
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

from core.theme import ThemeManager
from models.update_item import ServiceUpdate
from services.github_service import GitHubReleaseService

logger = logging.getLogger(__name__)

_COLUMNS = ("Service", "Version actuelle", "Disponible", "État")


class _CheckWorker(QThread):
    """Thread exécutant ``GitHubReleaseService.check_all`` hors du thread UI.

    Signals:
        checked: Émis avec la ``list[ServiceUpdate]`` en cas de succès.
        failed: Émis avec un message d'erreur en cas d'échec inattendu.
    """

    checked = Signal(list)
    failed = Signal(str)

    def __init__(
        self,
        service: GitHubReleaseService,
        services: dict[str, tuple[str, str]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._services = services

    def run(self) -> None:
        """Exécute la vérification GitHub et émet le résultat."""
        try:
            results = self._service.check_all(self._services)
        except Exception as exc:  # noqa: BLE001 - remonté à l'UI après log
            logger.exception("Vérification GitHub échouée")
            self.failed.emit(str(exc))
            return
        self.checked.emit(results)


class ServicesUpdateTab(QWidget):
    """Onglet listant les mises à jour des services Fenix (releases GitHub)."""

    def __init__(
        self,
        service: GitHubReleaseService,
        theme: ThemeManager,
        parent: QWidget | None = None,
    ) -> None:
        """Initialise l'onglet.

        Args:
            service: Service interrogeant l'API GitHub Releases.
            theme: Gestionnaire de thème pour les styles.
            parent: Widget parent optionnel.
        """
        super().__init__(parent)
        self._service = service
        self._theme = theme
        self._services: dict[str, tuple[str, str]] = {}
        self._updates: list[ServiceUpdate] = []
        self._worker: _CheckWorker | None = None
        self._build_ui()

    def set_services(self, services: dict[str, tuple[str, str]]) -> None:
        """Définit les services à vérifier.

        Args:
            services: Mapping ``service_id -> (repo GitHub, version installée)``.
        """
        self._services = dict(services)

    def _build_ui(self) -> None:
        """Construit l'interface (liste des services, versions, boutons)."""
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
        self._btn_check = QPushButton("Vérifier", self)
        self._btn_update = QPushButton("Mettre à jour", self)
        self._btn_check.clicked.connect(self._on_refresh_clicked)
        self._btn_update.clicked.connect(self._on_update_clicked)
        buttons.addWidget(self._btn_check)
        buttons.addWidget(self._btn_update)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self._apply_theme()

    def _apply_theme(self) -> None:
        """Applique le thème courant aux widgets de l'onglet."""
        self.setStyleSheet(self._theme.global_style())
        self._btn_check.setStyleSheet(self._theme.button_style())
        self._btn_update.setStyleSheet(self._theme.button_style())

    def _on_refresh_clicked(self) -> None:
        """Slot : interroge GitHub (dans un thread) pour rafraîchir l'état."""
        if self._worker is not None and self._worker.isRunning():
            return
        self._btn_check.setEnabled(False)
        worker = _CheckWorker(self._service, self._services, self)
        worker.checked.connect(self._on_services_checked)
        worker.failed.connect(self._on_error)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        worker.start()

    def _on_worker_finished(self) -> None:
        """Slot : nettoyage à la fin du thread de vérification."""
        self._btn_check.setEnabled(True)
        self._worker = None

    def _on_update_clicked(self) -> None:
        """Slot : déclenche la mise à jour du service sélectionné."""
        row = self._table.currentRow()
        if row < 0 or row >= len(self._updates):
            QMessageBox.warning(self, "Aucune sélection", "Sélectionnez un service à mettre à jour.")
            return
        update = self._updates[row]
        if not update.update_available:
            QMessageBox.information(self, "À jour", f"{update.name} est déjà à jour.")
            return
        # Le déploiement effectif (download + redémarrage via systemd) relève du
        # flux protégé par Polkit org.fenixserver.update.install-service.
        QMessageBox.information(
            self,
            "Mise à jour du service",
            f"Mise à jour de {update.name} vers {update.latest_version}.",
        )

    def _on_services_checked(self, updates: list) -> None:
        """Slot : peuple la liste avec l'état de mise à jour des services.

        Args:
            updates: Liste de ``ServiceUpdate`` à afficher.
        """
        self._updates = list(updates)
        self._table.setRowCount(len(self._updates))
        for row, update in enumerate(self._updates):
            available = update.update_available
            etat = "Mise à jour disponible" if available else "À jour"
            self._table.setItem(row, 0, QTableWidgetItem(update.name))
            self._table.setItem(row, 1, QTableWidgetItem(update.current_version))
            self._table.setItem(row, 2, QTableWidgetItem(update.latest_version))
            self._table.setItem(row, 3, QTableWidgetItem(etat))

    def _on_error(self, message: str) -> None:
        """Slot : affiche une erreur via ``QMessageBox``.

        Args:
            message: Message d'erreur à afficher.
        """
        QMessageBox.critical(self, "Erreur", message)
