"""Connexion LDAP et requêtes de base pour l'AD Manager.

La connexion à l'annuaire se fait via ``ldap3`` (jamais ``python-ldap``, jamais
en parsant la sortie de ``samba-tool``). Le domaine et l'adresse du contrôleur
de domaine sont lus depuis ``/etc/samba/smb.conf``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from ldap3 import ALL, MODIFY_REPLACE, SUBTREE, Connection, Server

if TYPE_CHECKING:
    from ldap3.abstract.entry import Entry

logger = logging.getLogger(__name__)

# Fichier de configuration Samba d'où sont lus le domaine et le DC.
SMB_CONF_PATH = "/etc/samba/smb.conf"

# Jeton ldap3 « tous les attributs » pour une recherche.
_ALL_ATTRIBUTES = "*"


def _realm_to_base_dn(realm: str) -> str:
    """Convertit un realm DNS en base DN LDAP (``example.lan`` -> ``dc=example,dc=lan``)."""
    return ",".join(f"dc={part}" for part in realm.split(".") if part)


class LDAPService:
    """Gère la connexion LDAP au contrôleur de domaine et les requêtes de base."""

    def __init__(
        self,
        server_uri: str,
        base_dn: str,
        *,
        bind_dn: str = "",
        password: str = "",
        realm: str = "",
    ):
        """Initialise le service LDAP.

        Args:
            server_uri: URI du serveur LDAP, ex. ``"ldap://dc.example.lan"``.
            base_dn: Base DN de recherche, ex. ``"dc=example,dc=lan"``.
            bind_dn: DN de connexion (vide pour une liaison anonyme).
            password: Mot de passe associé à ``bind_dn``.
            realm: Realm Kerberos du domaine (ex. ``"FENIX.LOCAL"``) ; sert à
                composer le UPN d'un utilisateur saisi sans domaine.
        """
        self._server_uri = server_uri
        self._base_dn = base_dn
        self._bind_dn = bind_dn
        self._password = password
        self._realm = realm
        self._connection: Connection | None = None

    @property
    def server_uri(self) -> str:
        """URI du serveur LDAP (contrôleur de domaine)."""
        return self._server_uri

    @property
    def base_dn(self) -> str:
        """Base DN de recherche du domaine."""
        return self._base_dn

    def set_credentials(self, bind_dn: str, password: str) -> None:
        """Définit les identifiants de liaison (bind) utilisés par :meth:`connect`.

        Si ``bind_dn`` est un simple nom d'utilisateur (sans ``@`` ni ``\\``) et
        qu'un realm est connu, il est complété en UPN ``utilisateur@REALM``
        (ex. ``Administrator`` -> ``Administrator@FENIX.LOCAL``).

        Args:
            bind_dn: Identité de connexion (DN, UPN ``user@realm``, ``DOMAINE\\user``
                ou simple nom d'utilisateur).
            password: Mot de passe associé.
        """
        self._bind_dn = self._qualify_user(bind_dn)
        self._password = password

    def _qualify_user(self, user: str) -> str:
        """Complète un nom d'utilisateur nu en UPN ``user@REALM`` si possible."""
        if user and self._realm and "@" not in user and "\\" not in user:
            return f"{user}@{self._realm}"
        return user

    @classmethod
    def from_smb_conf(cls, path: str = SMB_CONF_PATH) -> LDAPService:
        """Construit un :class:`LDAPService` depuis la configuration Samba.

        Lit le ``realm`` dans la section ``[global]`` de ``smb.conf`` pour en
        déduire ``server_uri`` (``ldap://<realm>``) et ``base_dn``.

        Args:
            path: Chemin du fichier ``smb.conf``.

        Returns:
            Un service LDAP configuré pour le domaine local.

        Raises:
            FileNotFoundError: si le fichier de configuration est absent.
            ValueError: si aucun ``realm`` n'est défini.
        """
        realm = ""
        for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line[0] in "#;[":
                continue
            key, sep, value = line.partition("=")
            if sep and key.strip().lower() == "realm":
                realm = value.strip()

        if not realm:
            raise ValueError(f"Aucun 'realm' trouvé dans {path}")

        # DNS/DN insensibles à la casse → minuscules ; realm Kerberos (UPN) en
        # majuscules par convention.
        realm_dns = realm.lower()
        return cls(
            server_uri=f"ldap://{realm_dns}",
            base_dn=_realm_to_base_dn(realm_dns),
            realm=realm.upper(),
        )

    @property
    def connection(self) -> Connection:
        """Connexion ``ldap3`` active.

        Raises:
            RuntimeError: si la connexion n'est pas établie.
        """
        if self._connection is None:
            raise RuntimeError("Connexion LDAP non établie")
        return self._connection

    def connect(self) -> None:
        """Établit et lie (bind) la connexion LDAP au contrôleur de domaine.

        Raises:
            RuntimeError: en cas d'échec de connexion ou de liaison.
        """
        try:
            server = Server(self._server_uri, get_info=ALL)
            self._connection = Connection(
                server,
                user=self._bind_dn or None,
                password=self._password or None,
                auto_bind=True,
            )
        except Exception as exc:
            logger.error("Connexion LDAP échouée (%s): %s", self._server_uri, exc)
            raise RuntimeError(f"Connexion LDAP échouée: {self._server_uri}") from exc

    def disconnect(self) -> None:
        """Ferme la connexion LDAP si elle est ouverte."""
        if self._connection is not None:
            self._connection.unbind()
            self._connection = None

    def is_connected(self) -> bool:
        """Indique si une connexion LDAP est actuellement établie et liée."""
        return self._connection is not None and bool(self._connection.bound)

    def search(self, search_filter: str, attributes: list[str] | None = None) -> list[Entry]:
        """Effectue une recherche LDAP sous la base DN du domaine.

        Args:
            search_filter: Filtre LDAP, ex. ``"(objectClass=user)"``.
            attributes: Attributs à retourner (tous par défaut si ``None``).

        Returns:
            La liste des entrées ``ldap3`` trouvées.

        Raises:
            RuntimeError: si la connexion n'est pas établie ou si la recherche
                échoue.
        """
        conn = self.connection
        try:
            conn.search(
                self._base_dn,
                search_filter,
                search_scope=SUBTREE,
                attributes=attributes if attributes is not None else _ALL_ATTRIBUTES,
            )
        except Exception as exc:
            logger.error("Recherche LDAP échouée (%s): %s", search_filter, exc)
            raise RuntimeError(f"Recherche LDAP échouée: {search_filter}") from exc
        return list(conn.entries)

    def add(self, dn: str, object_classes: list[str], attributes: dict[str, object]) -> None:
        """Crée une entrée LDAP.

        Args:
            dn: Distinguished Name de la nouvelle entrée.
            object_classes: Classes d'objet de l'entrée.
            attributes: Attributs initiaux de l'entrée.

        Raises:
            RuntimeError: si l'opération échoue.
        """
        conn = self.connection
        try:
            success = conn.add(dn, object_classes, attributes)
        except Exception as exc:
            logger.error("Ajout LDAP échoué (%s): %s", dn, exc)
            raise RuntimeError(f"Ajout LDAP échoué: {dn}") from exc
        self._ensure(success, "ajout", dn)

    def modify(self, dn: str, changes: dict[str, object]) -> None:
        """Remplace les attributs d'une entrée LDAP existante.

        Args:
            dn: Distinguished Name de l'entrée à modifier.
            changes: Modifications à appliquer (attribut -> nouvelle valeur ;
                une valeur scalaire est encapsulée dans une liste).

        Raises:
            RuntimeError: si l'opération échoue.
        """
        conn = self.connection
        ldap_changes = {
            attr: [(MODIFY_REPLACE, value if isinstance(value, list) else [value])]
            for attr, value in changes.items()
        }
        try:
            success = conn.modify(dn, ldap_changes)
        except Exception as exc:
            logger.error("Modification LDAP échouée (%s): %s", dn, exc)
            raise RuntimeError(f"Modification LDAP échouée: {dn}") from exc
        self._ensure(success, "modification", dn)

    def delete(self, dn: str) -> None:
        """Supprime une entrée LDAP.

        Args:
            dn: Distinguished Name de l'entrée à supprimer.

        Raises:
            RuntimeError: si l'opération échoue.
        """
        conn = self.connection
        try:
            success = conn.delete(dn)
        except Exception as exc:
            logger.error("Suppression LDAP échouée (%s): %s", dn, exc)
            raise RuntimeError(f"Suppression LDAP échouée: {dn}") from exc
        self._ensure(success, "suppression", dn)

    def _ensure(self, success: object, action: str, dn: str) -> None:
        """Lève ``RuntimeError`` si une opération ``ldap3`` a renvoyé un échec.

        Args:
            success: Valeur de retour booléenne de l'opération ``ldap3``.
            action: Nom de l'opération (pour le message d'erreur).
            dn: DN concerné.

        Raises:
            RuntimeError: si ``success`` est faux.
        """
        if not success:
            result = getattr(self._connection, "result", None)
            raise RuntimeError(f"Échec LDAP ({action}) sur {dn}: {result}")
