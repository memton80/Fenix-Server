"""Registre des rôles Fenix Server.

Un « rôle » est un service Linux exposé via une app KDE dédiée. Chaque rôle est
décrit par un fichier JSON ``roles/<role>.json``. Le :class:`RoleRegistry`
charge ces définitions et expose l'état (disponible / actif) des rôles.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from dasbus.error import DBusError

from core.dbus_helper import get_service_proxy, get_system_bus

logger = logging.getLogger(__name__)

SYSTEMD_SERVICE = "org.freedesktop.systemd1"
SYSTEMD_OBJECT = "/org/freedesktop/systemd1"

# Suffixe ajouté à un service_name systemd quand aucune unité n'est précisée.
_DEFAULT_SYSTEMD_SUFFIX = ".service"
_SYSTEMD_SUFFIXES = (
    ".service",
    ".socket",
    ".target",
    ".timer",
    ".mount",
    ".path",
    ".slice",
)

# Types de service supportés pour la détection d'état (champ "service_type").
SERVICE_TYPE_SYSTEMD = "systemd"
SERVICE_TYPE_DBUS = "dbus"
_VALID_SERVICE_TYPES = (SERVICE_TYPE_SYSTEMD, SERVICE_TYPE_DBUS)

# Types d'installation supportés pour le champ optionnel "install".
INSTALL_TYPE_DEB = "deb"
INSTALL_TYPE_SCRIPT = "script"
_VALID_INSTALL_TYPES = (INSTALL_TYPE_DEB, INSTALL_TYPE_SCRIPT)

# Champs obligatoires d'un fichier de rôle JSON.
_REQUIRED_FIELDS = ("id", "name", "description", "service_name", "service_type", "app")


@dataclass(frozen=True)
class InstallSpec:
    """Modalités d'installation d'un service, depuis le champ JSON ``install``.

    Décrit comment l'Update Manager installe (ou met à jour) un service Fenix à
    partir d'un asset de release GitHub. Champ optionnel : un rôle sans
    ``install`` requiert une installation manuelle.

    Attributes:
        type: Type d'installation : ``"deb"`` (paquet Debian via ``dpkg``) ou
            ``"script"`` (script shell d'installation).
        asset_pattern: Motif glob (``fnmatch``) identifiant l'asset à
            télécharger dans la release, ex. ``"*.deb"`` ou ``"install.sh"``.
    """

    type: str
    asset_pattern: str

    @classmethod
    def from_dict(cls, data: dict[str, object], source: Path) -> "InstallSpec":
        """Construit un :class:`InstallSpec` depuis le sous-objet ``install``.

        Args:
            data: Contenu du champ ``install`` du fichier JSON.
            source: Chemin du fichier source (pour les messages d'erreur).

        Returns:
            Les modalités d'installation correspondantes.

        Raises:
            ValueError: si ``type`` est absent/invalide ou si ``asset_pattern``
                est absent ou vide.
        """
        install_type = str(data.get("type", ""))
        if install_type not in _VALID_INSTALL_TYPES:
            raise ValueError(
                f"type d'installation invalide '{install_type}' dans {source} "
                f"(attendu: {', '.join(_VALID_INSTALL_TYPES)})"
            )

        asset_pattern = str(data.get("asset_pattern", ""))
        if not asset_pattern:
            raise ValueError(f"asset_pattern manquant pour l'installation dans {source}")

        return cls(type=install_type, asset_pattern=asset_pattern)


@dataclass(frozen=True)
class Role:
    """Définition d'un rôle, chargée depuis ``roles/<role>.json``.

    Attributes:
        id: Identifiant unique du rôle, ex. ``"ad"``, ``"updates"``.
        name: Nom affiché du rôle.
        description: Description courte du rôle.
        service_name: Nom du service système associé. Selon ``service_type`` :
            une unité systemd (ex. ``"smbd"``) ou un nom de bus D-Bus
            (ex. ``"org.freedesktop.PackageKit"``).
        service_type: Type de service, déterminant comment l'état est lu :
            ``"systemd"`` (état de l'unité) ou ``"dbus"`` (propriétaire du nom
            de bus).
        app: Répertoire de l'app KDE qui gère le rôle, ex. ``"ad-manager"``.
        install: Modalités d'installation du service (asset GitHub), ou ``None``
            si le rôle requiert une installation manuelle.
    """

    id: str
    name: str
    description: str
    service_name: str
    service_type: str
    app: str
    install: InstallSpec | None = None

    @classmethod
    def from_dict(cls, data: dict[str, object], source: Path) -> "Role":
        """Construit un :class:`Role` depuis un dict JSON.

        Args:
            data: Données décodées du fichier JSON.
            source: Chemin du fichier source (pour les messages d'erreur).

        Returns:
            Le rôle correspondant.

        Raises:
            ValueError: si un champ obligatoire est absent, si ``service_type``
                n'est pas une valeur supportée, ou si le champ optionnel
                ``install`` est mal formé.
        """
        missing = [field for field in _REQUIRED_FIELDS if field not in data]
        if missing:
            raise ValueError(f"Champs manquants {missing} dans {source}")

        service_type = str(data["service_type"])
        if service_type not in _VALID_SERVICE_TYPES:
            raise ValueError(
                f"service_type invalide '{service_type}' dans {source} "
                f"(attendu: {', '.join(_VALID_SERVICE_TYPES)})"
            )

        install_data = data.get("install")
        if install_data is not None and not isinstance(install_data, dict):
            raise ValueError(f"champ 'install' invalide (objet attendu) dans {source}")
        install = InstallSpec.from_dict(install_data, source) if install_data else None

        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            description=str(data["description"]),
            service_name=str(data["service_name"]),
            service_type=service_type,
            app=str(data["app"]),
            install=install,
        )


class RoleRegistry:
    """Charge et expose les rôles définis dans le dossier ``roles/``."""

    def __init__(self, roles_dir: Path) -> None:
        """Initialise le registre.

        Args:
            roles_dir: Dossier contenant les fichiers ``<role>.json``.
        """
        self._roles_dir = Path(roles_dir)
        self._roles: dict[str, Role] = {}

    def load(self) -> None:
        """Charge (ou recharge) toutes les définitions de rôles depuis le disque.

        Raises:
            FileNotFoundError: si le dossier des rôles est introuvable.
            ValueError: si un fichier JSON de rôle est invalide.
        """
        if not self._roles_dir.is_dir():
            raise FileNotFoundError(f"Dossier des rôles introuvable: {self._roles_dir}")

        roles: dict[str, Role] = {}
        for path in sorted(self._roles_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSON invalide dans {path}: {exc}") from exc

            role = Role.from_dict(data, path)
            if role.id in roles:
                raise ValueError(f"Identifiant de rôle dupliqué: {role.id} ({path})")
            roles[role.id] = role

        self._roles = roles

    def all_roles(self) -> list[Role]:
        """Retourne tous les rôles connus (disponibles), triés par nom."""
        return sorted(self._roles.values(), key=lambda role: role.name)

    def get(self, role_id: str) -> Role:
        """Retourne un rôle par son identifiant.

        Args:
            role_id: Identifiant du rôle.

        Returns:
            Le rôle correspondant.

        Raises:
            KeyError: si aucun rôle ne porte cet identifiant.
        """
        return self._roles[role_id]

    def is_active(self, role_id: str) -> bool:
        """Indique si le rôle est actuellement actif (service en cours d'exécution).

        Args:
            role_id: Identifiant du rôle.

        Returns:
            ``True`` si le service associé est actif, ``False`` sinon.
        """
        role = self.get(role_id)
        return self._service_running(role)

    def active_roles(self) -> list[Role]:
        """Retourne la liste des rôles actuellement actifs."""
        return [role for role in self.all_roles() if self.is_active(role.id)]

    # --- état des services ------------------------------------------------

    def _service_running(self, role: Role) -> bool:
        """Détermine si le service d'un rôle tourne, via D-Bus.

        Le mode de détection est choisi explicitement par ``role.service_type`` :
        ``"dbus"`` (propriétaire présent sur le bus) ou ``"systemd"``
        (``ActiveState == "active"``). Toute erreur D-Bus est loggée et traitée
        comme « inactif ».
        """
        try:
            if role.service_type == SERVICE_TYPE_DBUS:
                return self._dbus_name_running(role.service_name)
            return self._systemd_unit_active(role.service_name)
        except (DBusError, RuntimeError) as exc:
            logger.error("État du service %s indéterminé: %s", role.service_name, exc)
            return False

    def _dbus_name_running(self, bus_name: str) -> bool:
        """Vrai si un nom de bus D-Bus possède un propriétaire (service actif)."""
        return bool(get_system_bus().proxy.NameHasOwner(bus_name))

    def _systemd_unit_active(self, service_name: str) -> bool:
        """Vrai si l'unité systemd correspondante est dans l'état ``active``."""
        unit_name = service_name
        if not service_name.endswith(_SYSTEMD_SUFFIXES):
            unit_name = f"{service_name}{_DEFAULT_SYSTEMD_SUFFIX}"

        manager = get_service_proxy(SYSTEMD_SERVICE, SYSTEMD_OBJECT)
        try:
            unit_path = manager.GetUnit(unit_name)
        except DBusError:
            # Unité non chargée par systemd → considérée inactive.
            return False

        unit = get_system_bus().get_proxy(SYSTEMD_SERVICE, unit_path)
        return str(unit.ActiveState) == "active"
