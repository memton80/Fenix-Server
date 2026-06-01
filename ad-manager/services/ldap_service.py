"""Connexion LDAP et requêtes de base pour l'AD Manager.

La connexion à l'annuaire se fait via ``ldap3`` (jamais ``python-ldap``, jamais
en parsant la sortie de ``samba-tool``). Le domaine et l'adresse du contrôleur
de domaine sont lus depuis ``/etc/samba/smb.conf``.

Squelette : signatures uniquement, aucune implémentation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ldap3 import Connection

# Fichier de configuration Samba d'où sont lus le domaine et le DC.
SMB_CONF_PATH = "/etc/samba/smb.conf"


class LDAPService:
    """Gère la connexion LDAP au contrôleur de domaine et les requêtes de base."""

    def __init__(self, server_uri: str, base_dn: str, *, bind_dn: str = "", password: str = ""):
        """Initialise le service LDAP.

        Args:
            server_uri: URI du serveur LDAP, ex. ``"ldap://dc.example.lan"``.
            base_dn: Base DN de recherche, ex. ``"dc=example,dc=lan"``.
            bind_dn: DN de connexion (vide pour une liaison anonyme).
            password: Mot de passe associé à ``bind_dn``.
        """
        raise NotImplementedError

    @classmethod
    def from_smb_conf(cls, path: str = SMB_CONF_PATH) -> LDAPService:
        """Construit un :class:`LDAPService` depuis la configuration Samba.

        Lit le domaine (``realm``/``workgroup``) et l'hôte du DC dans
        ``smb.conf`` pour en déduire ``server_uri`` et ``base_dn``.

        Args:
            path: Chemin du fichier ``smb.conf``.

        Returns:
            Un service LDAP configuré pour le domaine local.

        Raises:
            FileNotFoundError: si le fichier de configuration est absent.
            ValueError: si la configuration ne permet pas de déduire le domaine.
        """
        raise NotImplementedError

    @property
    def connection(self) -> Connection:
        """Connexion ``ldap3`` active.

        Raises:
            RuntimeError: si la connexion n'est pas établie.
        """
        raise NotImplementedError

    def connect(self) -> None:
        """Établit et lie (bind) la connexion LDAP au contrôleur de domaine.

        Raises:
            RuntimeError: en cas d'échec de connexion ou de liaison.
        """
        raise NotImplementedError

    def disconnect(self) -> None:
        """Ferme la connexion LDAP si elle est ouverte."""
        raise NotImplementedError

    def is_connected(self) -> bool:
        """Indique si une connexion LDAP est actuellement établie."""
        raise NotImplementedError

    def search(
        self, search_filter: str, attributes: list[str] | None = None
    ) -> list[dict[str, object]]:
        """Effectue une recherche LDAP sous la base DN du domaine.

        Args:
            search_filter: Filtre LDAP, ex. ``"(objectClass=user)"``.
            attributes: Attributs à retourner (tous par défaut si ``None``).

        Returns:
            La liste des entrées trouvées, chaque entrée étant un mapping
            ``attribut -> valeur``.

        Raises:
            RuntimeError: si la connexion n'est pas établie ou si la recherche
                échoue.
        """
        raise NotImplementedError

    def add(self, dn: str, object_classes: list[str], attributes: dict[str, object]) -> None:
        """Crée une entrée LDAP.

        Args:
            dn: Distinguished Name de la nouvelle entrée.
            object_classes: Classes d'objet de l'entrée.
            attributes: Attributs initiaux de l'entrée.

        Raises:
            RuntimeError: si l'opération échoue.
        """
        raise NotImplementedError

    def modify(self, dn: str, changes: dict[str, object]) -> None:
        """Modifie les attributs d'une entrée LDAP existante.

        Args:
            dn: Distinguished Name de l'entrée à modifier.
            changes: Modifications à appliquer (attribut -> nouvelle valeur).

        Raises:
            RuntimeError: si l'opération échoue.
        """
        raise NotImplementedError

    def delete(self, dn: str) -> None:
        """Supprime une entrée LDAP.

        Args:
            dn: Distinguished Name de l'entrée à supprimer.

        Raises:
            RuntimeError: si l'opération échoue.
        """
        raise NotImplementedError
