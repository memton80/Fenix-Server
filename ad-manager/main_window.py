"""Fenêtre principale de l'AD Manager : onglets Utilisateurs / Groupes / Domaine."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QMainWindow, QMessageBox, QTabWidget, QWidget
from services.ad_service import ADService
from services.ldap_service import LDAPService
from widgets.domain_tab import DomainTab
from widgets.groups_tab import GroupsTab
from widgets.users_tab import UsersTab

from core.theme import ThemeManager

logger = logging.getLogger(__name__)

WINDOW_TITLE = "Fenix Server — Gestionnaire AD"
WINDOW_ICON_NAME = "system-users"

_UNCONFIGURED_MESSAGE = "Samba non configuré — veuillez d'abord configurer un domaine AD."


class _OfflineADService:
    """Service AD de repli quand Samba n'est pas configuré.

    N'effectue aucun accès LDAP : permet d'ouvrir la fenêtre (onglet Domaine
    accessible) sans connexion ni erreur, les onglets de gestion étant désactivés.
    """

    def list_users(self) -> list:
        """Retourne une liste vide (aucun domaine configuré)."""
        return []

    def list_groups(self) -> list:
        """Retourne une liste vide (aucun domaine configuré)."""
        return []

    def domain_info(self) -> dict[str, str]:
        """Retourne un domaine marqué « non configuré »."""
        return {"name": "", "dc": "", "samba": "non configuré"}


class ADManagerWindow(QMainWindow):
    """Fenêtre principale avec un ``QTabWidget`` à trois onglets.

    Onglets :
        - « Utilisateurs » : gestion des comptes du domaine.
        - « Groupes »      : gestion des groupes du domaine.
        - « Domaine »      : informations du domaine et état de Samba.
    """

    def __init__(self, theme: ThemeManager, parent: QWidget | None = None) -> None:
        """Initialise la fenêtre, les services et les onglets.

        Args:
            theme: Gestionnaire de thème appliqué à la fenêtre.
            parent: Widget parent optionnel.
        """
        super().__init__(parent)
        self._theme = theme
        try:
            self.ad_service = self._build_service()
            self._samba_configured = True
        except (FileNotFoundError, ValueError):
            # smb.conf absent ou sans realm : domaine AD non configuré.
            QMessageBox.warning(self, "Samba non configuré", _UNCONFIGURED_MESSAGE)
            self.ad_service = _OfflineADService()
            self._samba_configured = False
        self._build_ui()

    def _build_service(self) -> ADService:
        """Construit le service AD à partir de la configuration Samba locale.

        La connexion LDAP est tentée au démarrage ; un échec est seulement
        journalisé (les onglets afficheront l'erreur), l'app reste utilisable.

        Returns:
            Le service AD prêt à être utilisé par les onglets.
        """
        ldap = LDAPService.from_smb_conf()
        try:
            ldap.connect()
        except RuntimeError as exc:
            logger.warning("Connexion LDAP initiale impossible: %s", exc)
        return ADService(ldap)

    def _build_ui(self) -> None:
        """Construit la barre d'onglets et instancie les trois onglets."""
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowIcon(self._theme.icon(WINDOW_ICON_NAME))
        self.setStyleSheet(self._theme.global_style())

        self.users_tab = UsersTab(self.ad_service, self._theme, self)
        self.groups_tab = GroupsTab(self.ad_service, self._theme, self)
        self.domain_tab = DomainTab(self.ad_service, self._theme, self)

        self._tabs = QTabWidget(self)
        self._users_index = self._tabs.addTab(self.users_tab, "Utilisateurs")
        self._groups_index = self._tabs.addTab(self.groups_tab, "Groupes")
        self._tabs.addTab(self.domain_tab, "Domaine")
        self.setCentralWidget(self._tabs)

        if not self._samba_configured:
            # Domaine non configuré : seul l'onglet Domaine reste accessible.
            self._tabs.setTabEnabled(self._users_index, False)
            self._tabs.setTabEnabled(self._groups_index, False)
            self._tabs.setCurrentWidget(self.domain_tab)
