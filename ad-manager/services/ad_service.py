"""Opérations Active Directory de l'AD Manager (au-dessus de LDAP).

Compose les requêtes LDAP de :class:`LDAPService` en opérations métier
(utilisateurs, groupes, domaine) et protège chaque opération modifiant
l'annuaire par une vérification Polkit effectuée AVANT l'action.

Nomenclature Polkit : ``org.fenixserver.ad.<action>``
(``create-user``, ``delete-user``, ``create-group``, ``delete-group``).

Squelette : signatures uniquement, aucune implémentation.
"""

from __future__ import annotations

from models.ad_group import ADGroup
from models.ad_user import ADUser

from core.polkit import PolkitClient
from services.ldap_service import LDAPService

POLKIT_ACTION_CREATE_USER = "org.fenixserver.ad.create-user"
POLKIT_ACTION_DELETE_USER = "org.fenixserver.ad.delete-user"
POLKIT_ACTION_CREATE_GROUP = "org.fenixserver.ad.create-group"
POLKIT_ACTION_DELETE_GROUP = "org.fenixserver.ad.delete-group"


class ADService:
    """Expose les opérations AD (utilisateurs, groupes, domaine)."""

    def __init__(self, ldap: LDAPService, polkit: PolkitClient | None = None) -> None:
        """Initialise le service AD.

        Args:
            ldap: Service LDAP connecté au contrôleur de domaine.
            polkit: Client Polkit (injectable pour les tests) ; un client par
                défaut est créé si absent.
        """
        raise NotImplementedError

    # --- utilisateurs -----------------------------------------------------

    def list_users(self) -> list[ADUser]:
        """Retourne la liste des utilisateurs du domaine.

        Returns:
            Les :class:`ADUser` lus depuis l'annuaire.

        Raises:
            RuntimeError: en cas d'erreur LDAP.
        """
        raise NotImplementedError

    def create_user(
        self, username: str, password: str, *, display_name: str = "", email: str = ""
    ) -> ADUser:
        """Crée un utilisateur dans le domaine.

        Vérifie l'autorisation Polkit
        (``org.fenixserver.ad.create-user``) AVANT toute action.

        Args:
            username: Identifiant de connexion (``sAMAccountName``).
            password: Mot de passe initial.
            display_name: Nom affiché ; déduit de ``username`` si vide.
            email: Adresse e-mail principale, optionnelle.

        Returns:
            L'utilisateur créé.

        Raises:
            PermissionError: si l'action est refusée par Polkit.
            RuntimeError: en cas d'erreur LDAP.
        """
        raise NotImplementedError

    def modify_user(
        self, username: str, *, display_name: str | None = None, email: str | None = None
    ) -> ADUser:
        """Modifie les attributs d'un utilisateur existant.

        Args:
            username: Identifiant de l'utilisateur à modifier.
            display_name: Nouveau nom affiché, ou ``None`` pour conserver.
            email: Nouvelle adresse e-mail, ou ``None`` pour conserver.

        Returns:
            L'utilisateur mis à jour.

        Raises:
            PermissionError: si l'action est refusée par Polkit.
            KeyError: si l'utilisateur est inconnu.
            RuntimeError: en cas d'erreur LDAP.
        """
        raise NotImplementedError

    def delete_user(self, username: str) -> None:
        """Supprime un utilisateur du domaine.

        Vérifie l'autorisation Polkit
        (``org.fenixserver.ad.delete-user``) AVANT toute action.

        Args:
            username: Identifiant de l'utilisateur à supprimer.

        Raises:
            PermissionError: si l'action est refusée par Polkit.
            KeyError: si l'utilisateur est inconnu.
            RuntimeError: en cas d'erreur LDAP.
        """
        raise NotImplementedError

    # --- groupes ----------------------------------------------------------

    def list_groups(self) -> list[ADGroup]:
        """Retourne la liste des groupes du domaine.

        Returns:
            Les :class:`ADGroup` lus depuis l'annuaire.

        Raises:
            RuntimeError: en cas d'erreur LDAP.
        """
        raise NotImplementedError

    def create_group(self, name: str, *, description: str = "") -> ADGroup:
        """Crée un groupe dans le domaine.

        Vérifie l'autorisation Polkit
        (``org.fenixserver.ad.create-group``) AVANT toute action.

        Args:
            name: Nom du groupe.
            description: Description optionnelle.

        Returns:
            Le groupe créé.

        Raises:
            PermissionError: si l'action est refusée par Polkit.
            RuntimeError: en cas d'erreur LDAP.
        """
        raise NotImplementedError

    def delete_group(self, name: str) -> None:
        """Supprime un groupe du domaine.

        Vérifie l'autorisation Polkit
        (``org.fenixserver.ad.delete-group``) AVANT toute action.

        Args:
            name: Nom du groupe à supprimer.

        Raises:
            PermissionError: si l'action est refusée par Polkit.
            KeyError: si le groupe est inconnu.
            RuntimeError: en cas d'erreur LDAP.
        """
        raise NotImplementedError

    # --- domaine ----------------------------------------------------------

    def domain_info(self) -> dict[str, str]:
        """Retourne les informations du domaine.

        Returns:
            Un mapping contenant au moins le nom du domaine, l'hôte du
            contrôleur de domaine et l'état du service Samba.

        Raises:
            RuntimeError: en cas d'erreur LDAP.
        """
        raise NotImplementedError
