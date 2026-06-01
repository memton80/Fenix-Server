"""Opérations Active Directory de l'AD Manager.

Les lectures (liste / recherche / infos domaine) passent par LDAP
(:class:`LDAPService`). Les opérations privilégiées — création et suppression
d'utilisateurs et de groupes, définition du mot de passe — sont déléguées à
``samba-tool`` exécuté via ``pkexec`` (même approche que ``role_service`` avec
``systemctl``) : l'élévation et l'autorisation sont gérées par pkexec/Polkit,
sans vérification Polkit explicite dans le code.

La modification d'attributs (nom affiché, e-mail) reste une écriture LDAP sous
le bind administrateur authentifié : ``samba-tool`` n'offre pas d'éditeur
d'attributs non interactif.
"""

from __future__ import annotations

import logging
import subprocess

from models.ad_group import ADGroup
from models.ad_user import ADUser

from services.ldap_service import LDAPService

logger = logging.getLogger(__name__)

# Filtres et attributs LDAP des objets manipulés (lectures).
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

# Conteneur par défaut des comptes/groupes (pour reconstituer leur DN).
_USERS_CONTAINER = "cn=Users"

# Échappement des caractères spéciaux dans une valeur de filtre LDAP (RFC 4515),
# pour éviter toute injection via un nom d'utilisateur/groupe.
_FILTER_ESCAPE = {"*": "\\2a", "(": "\\28", ")": "\\29", "\\": "\\5c", "\x00": "\\00"}

# Indices, dans la sortie d'erreur de samba-tool, d'un rejet lié à la politique
# de mot de passe AD (messages en anglais).
_PASSWORD_POLICY_HINTS = ("password", "complexity", "policy")
_PASSWORD_POLICY_MESSAGE = (
    "Le mot de passe ne respecte pas la politique de complexité AD :\n"
    "- 8 caractères minimum\n"
    "- Majuscule, minuscule, chiffre et caractère spécial requis"
)


def _escape_filter(value: str) -> str:
    """Échappe une valeur destinée à un filtre LDAP (RFC 4515)."""
    return "".join(_FILTER_ESCAPE.get(char, char) for char in value)


class ADService:
    """Expose les opérations AD (utilisateurs, groupes, domaine)."""

    def __init__(self, ldap: LDAPService) -> None:
        """Initialise le service AD.

        Args:
            ldap: Service LDAP connecté au contrôleur de domaine (lectures).
        """
        self._ldap = ldap

    def _run_samba_tool(self, *args: str) -> None:
        """Exécute ``pkexec samba-tool <args>`` (opération privilégiée).

        L'élévation et l'autorisation sont assurées par ``pkexec`` (Polkit) ;
        aucune vérification Polkit explicite n'est faite ici.

        Args:
            args: Arguments passés à ``samba-tool`` (ex. ``("user", "delete", name)``).

        Raises:
            RuntimeError: si la commande ``samba-tool`` échoue. Un échec lié à
                la politique de mot de passe donne un message d'aide explicite.
        """
        command = ["pkexec", "samba-tool", *args]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            # On ne journalise que la sous-commande (args[:2]) pour ne pas
            # divulguer de secret (mot de passe, e-mail) passé en argument.
            operation = " ".join(args[:2])
            logger.error(
                "samba-tool %s a échoué: code=%s stderr=%s",
                operation,
                exc.returncode,
                exc.stderr,
            )
            stderr = (exc.stderr or "").lower()
            if any(hint in stderr for hint in _PASSWORD_POLICY_HINTS):
                raise RuntimeError(_PASSWORD_POLICY_MESSAGE) from exc
            raise RuntimeError(f"Commande samba-tool échouée: {operation}") from exc

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
        """Crée un utilisateur dans le domaine via ``samba-tool user create``.

        Args:
            username: Identifiant de connexion (``sAMAccountName``).
            password: Mot de passe initial.
            display_name: Nom affiché ; déduit de ``username`` si vide.
            email: Adresse e-mail principale, optionnelle.

        Returns:
            L'utilisateur créé.

        Raises:
            RuntimeError: si la commande ``samba-tool`` échoue.
        """
        args = ["user", "create", username, password]
        if display_name:
            args.append(f"--given-name={display_name}")
        if email:
            args.append(f"--mail-address={email}")
        self._run_samba_tool(*args)

        return ADUser(
            username=username,
            display_name=display_name or username,
            email=email,
            enabled=True,
            dn=self._user_dn(username),
        )

    def modify_user(
        self, username: str, *, display_name: str | None = None, email: str | None = None
    ) -> ADUser:
        """Modifie les attributs d'un utilisateur existant (écriture LDAP).

        ``samba-tool`` n'offrant pas d'éditeur d'attributs non interactif, la
        mise à jour passe par LDAP, sous le bind administrateur authentifié.

        Args:
            username: Identifiant de l'utilisateur à modifier.
            display_name: Nouveau nom affiché, ou ``None`` pour conserver.
            email: Nouvelle adresse e-mail, ou ``None`` pour conserver.

        Returns:
            L'utilisateur mis à jour.

        Raises:
            KeyError: si l'utilisateur est inconnu.
            RuntimeError: en cas d'erreur LDAP.
        """
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
        """Supprime un utilisateur du domaine via ``samba-tool user delete``.

        Args:
            username: Identifiant de l'utilisateur à supprimer.

        Raises:
            RuntimeError: si la commande ``samba-tool`` échoue.
        """
        self._run_samba_tool("user", "delete", username)

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
        """Crée un groupe dans le domaine via ``samba-tool group add``.

        Args:
            name: Nom du groupe.
            description: Description optionnelle.

        Returns:
            Le groupe créé.

        Raises:
            RuntimeError: si la commande ``samba-tool`` échoue.
        """
        args = ["group", "add", name]
        if description:
            args.append(f"--description={description}")
        self._run_samba_tool(*args)
        return ADGroup(name=name, description=description, dn=self._group_dn(name))

    def delete_group(self, name: str) -> None:
        """Supprime un groupe du domaine via ``samba-tool group delete``.

        Args:
            name: Nom du groupe à supprimer.

        Raises:
            RuntimeError: si la commande ``samba-tool`` échoue.
        """
        self._run_samba_tool("group", "delete", name)

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
