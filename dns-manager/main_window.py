"""Fenêtre principale du DNS Manager : onglets Zones / Enregistrements."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMainWindow,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from services.dns_service import DnsService
from widgets.records_tab import RecordsTab
from widgets.zones_tab import ZonesTab

from core.theme import ThemeManager

logger = logging.getLogger(__name__)

WINDOW_TITLE = "Fenix Server — Gestionnaire DNS"
WINDOW_ICON_NAME = "network-server"

_DEFAULT_ADMIN = "Administrator"


class LoginDialog(QDialog):
    """Dialogue de connexion au domaine (utilisateur + mot de passe)."""

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
        """Construit le formulaire (utilisateur, mot de passe)."""
        self.setWindowTitle("Connexion au domaine")
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._edit_user = QLineEdit(_DEFAULT_ADMIN, self)
        self._edit_password = QLineEdit(self)
        self._edit_password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Utilisateur", self._edit_user)
        form.addRow("Mot de passe", self._edit_password)
        layout.addLayout(form)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self.setStyleSheet(self._theme.global_style())

    def credentials(self) -> tuple[str, str]:
        """Retourne les identifiants saisis (``utilisateur``, ``mot de passe``)."""
        return self._edit_user.text().strip(), self._edit_password.text()


class DnsManagerWindow(QMainWindow):
    """Fenêtre principale avec un ``QTabWidget`` à deux onglets.

    Onglets :
        - « Zones »          : zones DNS hébergées par le domaine (lecture seule).
        - « Enregistrements » : gestion des enregistrements A/CNAME/PTR d'une zone.
    """

    def __init__(self, theme: ThemeManager, parent: QWidget | None = None) -> None:
        """Initialise la fenêtre, le service et les onglets.

        Args:
            theme: Gestionnaire de thème appliqué à la fenêtre.
            parent: Widget parent optionnel.
        """
        super().__init__(parent)
        self._theme = theme
        self.dns_service = self._build_service()
        self._build_ui()

    def _build_service(self) -> DnsService:
        """Construit le service DNS avec les identifiants saisis au démarrage.

        Affiche le ``LoginDialog`` ; les identifiants sont transmis au
        :class:`DnsService` qui les injecte dans chaque commande ``samba-tool``.
        Si le dialogue est annulé, le service est créé sans identifiants (les
        commandes échoueront, l'erreur étant remontée par les onglets).

        Returns:
            Le service DNS prêt à être utilisé par les onglets.
        """
        credentials = self._prompt_credentials()
        if credentials is None:
            logger.info("Connexion au domaine annulée par l'utilisateur")
            return DnsService()
        username, password = credentials
        return DnsService(username=username, password=password)

    def _prompt_credentials(self) -> tuple[str, str] | None:
        """Affiche le dialogue de connexion et retourne les identifiants saisis.

        Returns:
            Le couple ``(utilisateur, mot de passe)``, ou ``None`` si le dialogue
            est annulé.
        """
        dialog = LoginDialog(self._theme, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.credentials()

    def _build_ui(self) -> None:
        """Construit la barre d'onglets et instancie les deux onglets."""
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowIcon(self._theme.icon(WINDOW_ICON_NAME))
        self.setStyleSheet(self._theme.global_style())

        self.zones_tab = ZonesTab(self.dns_service, self._theme, self)
        self.records_tab = RecordsTab(self.dns_service, self._theme, self)

        self._tabs = QTabWidget(self)
        self._tabs.addTab(self.zones_tab, "Zones")
        self._tabs.addTab(self.records_tab, "Enregistrements")
        self.setCentralWidget(self._tabs)
