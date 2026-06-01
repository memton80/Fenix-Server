"""Opérations Active Directory de l'AD Manager (au-dessus de LDAP).

Compose les requêtes LDAP de :class:`LDAPService` en opérations métier
(utilisateurs, groupes, domaine) et protège chaque opération modifiant
l'annuaire par une vérification Polkit effectuée AVANT l'action.

Nomenclature Polkit : ``org.fenixserver.ad.<action>``
(``create-user``, ``modify-user``, ``delete-user``, ``create-group``,
``delete-group``).
"""

from __future__ import annotations

import logging
import subprocess

from models.ad_group import ADGroup
from models.ad_user import ADUser

from core.polkit import PolkitClient
from services.ldap_service import LDAPService

logger = logging.getLogger(__name__)

POLKIT_ACTION_CREATE_USER = "org.fenixserver.ad.create-user"
POLKIT_ACTION_MODIFY_USER = "org.fenixserver.ad.modify-user"
POLKIT_ACTION_DELETE_USER = "org.fenixserver.ad.delete-user"
POLKIT_ACTION_CREATE_GROUP = "org.fenixserver.ad.create-group"
POLKIT_ACTION_DELETE_GROUP = "org.fenixserver.ad.delete-group"

# Filtres et attributs LDAP des objets manipulés.
_USER_FILTER = "(&(objectClass=user)(objectCategory=person))"
_USER_ATTRIBUTES = [
    "sAMAccountName",
    "displayName",
    "cn",
    "mail",
    "userAccountControl",
    "memberOf",
]
_GROUP_FILTER = "(objectClass=group)"
_GROUP_ATTRIBUTES = ["sAMAccountName", "cn", "description", "member"]

_USER_OBJECT_CLASSES = ["top", "person", "organizationalPerson", "user"]
_GROUP_OBJECT_CLASSES = ["top", "group"]

# Conteneur par défaut des comptes/groupes et valeur userAccountControl d'un
# compte normal activé.
_USERS_CONTAINER = "cn=Users"
_UF_NORMAL_ACCOUNT = 512

# Échappement des caractères spéciaux dans une valeur de filtre LDAP (RFC 4515),
# pour éviter toute injection via un nom d'utilisateur/groupe.
_FILTER_ESCAPE = {"*": "\\2a", "(": "\\28", ")": "\\29", "\\": "\\5c", "\x00": "\\00"}


def _escape_filter(value: str) -> str:
    """Échappe une valeur destinée à un filtre LDAP (RFC 4515)."""
    return "".join(_FILTER_ESCAPE.get(char, char) for char in value)


class ADService:
    """Expose les opérations AD (utilisateurs, groupes, domaine)."""

    def __init__(self, ldap: LDAPService, polkit: PolkitClient | None = None) -> None:
        """Initialise le service AD.

        Args:
            ldap: Service LDAP connecté au contrôleur de domaine.
            polkit: Client Polkit (injectable pour les tests) ; un client par
                défaut est créé si absent.
        """
        self._ldap = ldap
        self._polkit = polkit or PolkitClient()

    def _authorize(self, action: str) -> None:
        """Vérifie l'autorisation Polkit d'une action, AVANT toute modification.

        Args:
            action: ID de l'action Polkit.

        Raises:
            PermissionError: si l'action est refusée par Polkit.
        """
        if not self._polkit.check_authorization(action):
            raise PermissionError(f"Action refusée par Polkit: {action}")

    def _user_dn(self, username: str) -> str:
        """Construit le DN d'un utilisateur dans le conteneur par défaut."""
        return f"cn={username},{_USERS_CONTAINER},{self._ldap.base_dn}"

    def _group_dn(self, name: str) -> str:
        """Construit le DN d'un groupe dans le conteneur par défaut."""
        return f"cn={name},{_USERS_CONTAINER},{self._ldap.base_dn}"

    # --- utilisateurs -----------------------------------------------------

    def list_users(self) -> list[ADUser]:
        """Retourne la liste des utilisateurs du domaine.

        Returns:
            Les :class:`ADUser` lus depuis l'annuaire.

        Raises:
            RuntimeError: en cas d'erreur LDAP.
        """
        entries = self._ldap.search(_USER_FILTER, _USER_ATTRIBUTES)
        return [ADUser.from_ldap_entry(entry) for entry in entries]

    def get_user(self, username: str) -> ADUser:
        """Retourne un utilisateur par son identifiant.

        Args:
            username: Identifiant (``sAMAccountName``) de l'utilisateur.

        Returns:
            L'utilisateur correspondant.

        Raises:
            KeyError: si l'utilisateur est inconnu.
            RuntimeError: en cas d'erreur LDAP.
        """
        entries = self._ldap.search(
            f"(sAMAccountName={_escape_filter(username)})", _USER_ATTRIBUTES
        )
        if not entries:
            raise KeyError(username)
        return ADUser.from_ldap_entry(entries[0])

    def create_user(
        self, username: str, password: str, *, display_name: str = "", email: str = ""
    ) -> ADUser:
        """Crée un utilisateur dans le domaine.

        Vérifie l'autorisation Polkit
        (``org.fenixserver.ad.create-user``) AVANT toute action.

        Args:
            username: Identifiant de connexion (``sAMAccountName``).
            password: Mot de passe initial (positionné via ``samba-tool``).
            display_name: Nom affiché ; déduit de ``username`` si vide.
            email: Adresse e-mail principale, optionnelle.

        Returns:
            L'utilisateur créé.

        Raises:
            PermissionError: si l'action est refusée par Polkit.
            RuntimeError: en cas d'erreur LDAP ou de définition du mot de passe.
        """
        self._authorize(POLKIT_ACTION_CREATE_USER)
        dn = self._user_dn(username)
        attributes: dict[str, object] = {
            "sAMAccountName": username,
            "displayName": display_name or username,
            "userAccountControl": str(_UF_NORMAL_ACCOUNT),
        }
        if email:
            attributes["mail"] = email

        self._ldap.add(dn, _USER_OBJECT_CLASSES, attributes)
        if password:
            self._set_password(username, password)

        return ADUser(
            username=username,
            display_name=display_name or username,
            email=email,
            enabled=True,
            dn=dn,
        )

    def _set_password(self, username: str, password: str) -> None:
        """Définit le mot de passe d'un utilisateur via ``samba-tool`` (élévation pkexec).

        ``samba-tool`` gère l'encodage ``unicodePwd`` et les contraintes de
        complexité AD ; l'élévation passe par ``pkexec`` (même approche que le
        flux d'installation de l'update-manager).

        Args:
            username: Identifiant de l'utilisateur.
            password: Nouveau mot de passe en clair.

        Raises:
            RuntimeError: si la commande ``samba-tool`` échoue.
        """
        command = [
            "pkexec",
            "samba-tool",
            "user",
            "setpassword",
            username,
            f"--newpassword={password}",
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            logger.error(
                "Définition du mot de passe échouée (%s): code=%s stderr=%s",
                username,
                exc.returncode,
                exc.stderr,
            )
            raise RuntimeError(f"Définition du mot de passe échouée pour {username}") from exc

    def modify_user(
        self, username: str, *, display_name: str | None = None, email: str | None = None
    ) -> ADUser:
        """Modifie les attributs d'un utilisateur existant.

        Vérifie l'autorisation Polkit
        (``org.fenixserver.ad.modify-user``) AVANT toute action.

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
        self._authorize(POLKIT_ACTION_MODIFY_USER)
        user = self.get_user(username)

        changes: dict[str, object] = {}
        if display_name is not None:
            changes["displayName"] = display_name
        if email is not None:
            changes["mail"] = email
        if changes:
            self._ldap.modify(user.dn, changes)

        return ADUser(
            username=user.username,
            display_name=user.display_name if display_name is None else display_name,
            email=user.email if email is None else email,
            enabled=user.enabled,
            dn=user.dn,
            groups=user.groups,
        )

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
        self._authorize(POLKIT_ACTION_DELETE_USER)
        user = self.get_user(username)
        self._ldap.delete(user.dn)

    # --- groupes ----------------------------------------------------------

    def list_groups(self) -> list[ADGroup]:
        """Retourne la liste des groupes du domaine.

        Returns:
            Les :class:`ADGroup` lus depuis l'annuaire.

        Raises:
            RuntimeError: en cas d'erreur LDAP.
        """
        entries = self._ldap.search(_GROUP_FILTER, _GROUP_ATTRIBUTES)
        return [ADGroup.from_ldap_entry(entry) for entry in entries]

    def get_group(self, name: str) -> ADGroup:
        """Retourne un groupe par son nom.

        Args:
            name: Nom (``sAMAccountName``) du groupe.

        Returns:
            Le groupe correspondant.

        Raises:
            KeyError: si le groupe est inconnu.
            RuntimeError: en cas d'erreur LDAP.
        """
        entries = self._ldap.search(
            f"(&{_GROUP_FILTER}(sAMAccountName={_escape_filter(name)}))", _GROUP_ATTRIBUTES
        )
        if not entries:
            raise KeyError(name)
        return ADGroup.from_ldap_entry(entries[0])

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
        self._authorize(POLKIT_ACTION_CREATE_GROUP)
        dn = self._group_dn(name)
        attributes: dict[str, object] = {"sAMAccountName": name}
        if description:
            attributes["description"] = description

        self._ldap.add(dn, _GROUP_OBJECT_CLASSES, attributes)
        return ADGroup(name=name, description=description, dn=dn)

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
        self._authorize(POLKIT_ACTION_DELETE_GROUP)
        group = self.get_group(name)
        self._ldap.delete(group.dn)

    # --- domaine ----------------------------------------------------------

    def domain_info(self) -> dict[str, str]:
        """Retourne les informations du domaine.

        Returns:
            Un mapping ``name`` (domaine DNS), ``dc`` (URI du contrôleur de
            domaine) et ``samba`` (état de la connexion LDAP).
        """
        base_dn = self._ldap.base_dn
        domain = ".".join(
            part[3:] for part in base_dn.split(",") if part.strip().lower().startswith("dc=")
        )
        return {
            "name": domain,
            "dc": self._ldap.server_uri,
            "samba": "connecté" if self._ldap.is_connected() else "déconnecté",
        }
