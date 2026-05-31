"""Tests pour core.roles — chargement JSON sur disque, état des services mocké."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from dasbus.error import DBusError

from core import roles
from core.roles import Role, RoleRegistry


def _write_role(roles_dir: Path, role_id: str, **overrides) -> None:
    """Écrit un fichier <role>.json valide, surchargé par overrides."""
    data = {
        "id": role_id,
        "name": overrides.get("name", role_id.upper()),
        "description": overrides.get("description", f"Rôle {role_id}"),
        "service_name": overrides.get("service_name", f"{role_id}.service"),
        "app": overrides.get("app", f"{role_id}-manager"),
    }
    (roles_dir / f"{role_id}.json").write_text(json.dumps(data), encoding="utf-8")


# --- load -----------------------------------------------------------------


def test_load_charge_les_roles(tmp_path: Path):
    """load lit tous les fichiers JSON et all_roles les trie par nom."""
    _write_role(tmp_path, "updates", name="Mises à jour")
    _write_role(tmp_path, "ad", name="Active Directory")

    registry = RoleRegistry(tmp_path)
    registry.load()

    noms = [role.name for role in registry.all_roles()]
    assert noms == ["Active Directory", "Mises à jour"]
    assert registry.get("ad").app == "ad-manager"


def test_load_dossier_absent_leve_filenotfounderror(tmp_path: Path):
    """Un dossier de rôles inexistant lève FileNotFoundError."""
    registry = RoleRegistry(tmp_path / "inexistant")
    with pytest.raises(FileNotFoundError):
        registry.load()


def test_load_json_invalide_leve_valueerror(tmp_path: Path):
    """Un fichier JSON mal formé lève ValueError."""
    (tmp_path / "broken.json").write_text("{pas du json", encoding="utf-8")
    registry = RoleRegistry(tmp_path)
    with pytest.raises(ValueError, match="JSON invalide"):
        registry.load()


def test_load_champ_manquant_leve_valueerror(tmp_path: Path):
    """Un fichier de rôle sans champ obligatoire lève ValueError."""
    (tmp_path / "ad.json").write_text(json.dumps({"id": "ad", "name": "AD"}), encoding="utf-8")
    registry = RoleRegistry(tmp_path)
    with pytest.raises(ValueError, match="Champs manquants"):
        registry.load()


def test_load_id_duplique_leve_valueerror(tmp_path: Path):
    """Deux fichiers décrivant le même id lèvent ValueError."""
    _write_role(tmp_path, "ad")
    (tmp_path / "ad-bis.json").write_text(
        json.dumps(
            {
                "id": "ad",
                "name": "AD bis",
                "description": "doublon",
                "service_name": "smbd",
                "app": "ad-manager",
            }
        ),
        encoding="utf-8",
    )
    registry = RoleRegistry(tmp_path)
    with pytest.raises(ValueError, match="dupliqué"):
        registry.load()


# --- get ------------------------------------------------------------------


def test_get_role_inconnu_leve_keyerror(tmp_path: Path):
    """get sur un id inconnu lève KeyError."""
    _write_role(tmp_path, "ad")
    registry = RoleRegistry(tmp_path)
    registry.load()
    with pytest.raises(KeyError):
        registry.get("inexistant")


# --- is_active : nom de bus D-Bus -----------------------------------------


def test_is_active_dbus_name_actif(tmp_path: Path):
    """Un rôle dont le service est un nom de bus actif est is_active=True."""
    _write_role(tmp_path, "updates", service_name="org.freedesktop.PackageKit")
    registry = RoleRegistry(tmp_path)
    registry.load()

    daemon = MagicMock()
    daemon.NameHasOwner.return_value = True
    bus = MagicMock(proxy=daemon)

    with patch.object(roles, "get_system_bus", return_value=bus):
        assert registry.is_active("updates") is True

    daemon.NameHasOwner.assert_called_once_with("org.freedesktop.PackageKit")


def test_is_active_dbus_name_inactif(tmp_path: Path):
    """Un nom de bus sans propriétaire est is_active=False."""
    _write_role(tmp_path, "updates", service_name="org.freedesktop.PackageKit")
    registry = RoleRegistry(tmp_path)
    registry.load()

    daemon = MagicMock()
    daemon.NameHasOwner.return_value = False
    bus = MagicMock(proxy=daemon)

    with patch.object(roles, "get_system_bus", return_value=bus):
        assert registry.is_active("updates") is False


# --- is_active : unité systemd --------------------------------------------


def test_is_active_unite_systemd_active(tmp_path: Path):
    """Un service systemd dans l'état active est is_active=True."""
    _write_role(tmp_path, "ad", service_name="smbd")
    registry = RoleRegistry(tmp_path)
    registry.load()

    manager = MagicMock()
    manager.GetUnit.return_value = "/org/freedesktop/systemd1/unit/smbd_2eservice"
    unit = MagicMock()
    unit.ActiveState = "active"
    bus = MagicMock()
    bus.get_proxy.return_value = unit

    with patch.object(roles, "get_service_proxy", return_value=manager), patch.object(
        roles, "get_system_bus", return_value=bus
    ):
        assert registry.is_active("ad") is True

    # Le nom d'unité est normalisé avec le suffixe .service.
    manager.GetUnit.assert_called_once_with("smbd.service")


def test_is_active_unite_systemd_inactive(tmp_path: Path):
    """Un service systemd dans un état non-active est is_active=False."""
    _write_role(tmp_path, "ad", service_name="smbd")
    registry = RoleRegistry(tmp_path)
    registry.load()

    manager = MagicMock()
    manager.GetUnit.return_value = "/org/freedesktop/systemd1/unit/smbd_2eservice"
    unit = MagicMock()
    unit.ActiveState = "inactive"
    bus = MagicMock()
    bus.get_proxy.return_value = unit

    with patch.object(roles, "get_service_proxy", return_value=manager), patch.object(
        roles, "get_system_bus", return_value=bus
    ):
        assert registry.is_active("ad") is False


def test_is_active_unite_non_chargee(tmp_path: Path):
    """Une unité non chargée (GetUnit échoue) est traitée comme inactive."""
    _write_role(tmp_path, "ad", service_name="smbd")
    registry = RoleRegistry(tmp_path)
    registry.load()

    manager = MagicMock()
    manager.GetUnit.side_effect = DBusError("NoSuchUnit")

    with patch.object(roles, "get_service_proxy", return_value=manager), patch.object(
        roles, "get_system_bus", return_value=MagicMock()
    ):
        assert registry.is_active("ad") is False


def test_is_active_erreur_dbus_retourne_false(tmp_path: Path):
    """Une erreur D-Bus pendant la vérification donne False, sans propager."""
    _write_role(tmp_path, "updates", service_name="org.freedesktop.PackageKit")
    registry = RoleRegistry(tmp_path)
    registry.load()

    daemon = MagicMock()
    daemon.NameHasOwner.side_effect = DBusError("boom")
    bus = MagicMock(proxy=daemon)

    with patch.object(roles, "get_system_bus", return_value=bus):
        assert registry.is_active("updates") is False


# --- active_roles ---------------------------------------------------------


def test_active_roles_filtre_les_actifs(tmp_path: Path):
    """active_roles ne retourne que les rôles actifs."""
    _write_role(tmp_path, "ad", name="AD", service_name="org.example.Ad")
    _write_role(tmp_path, "updates", name="Updates", service_name="org.example.Updates")
    registry = RoleRegistry(tmp_path)
    registry.load()

    def is_active(role_id: str) -> bool:
        return role_id == "updates"

    with patch.object(registry, "is_active", side_effect=is_active):
        actifs = registry.active_roles()

    assert [role.id for role in actifs] == ["updates"]


# --- Role.from_dict -------------------------------------------------------


def test_role_from_dict_valide():
    """from_dict construit un Role complet."""
    role = Role.from_dict(
        {
            "id": "ad",
            "name": "Active Directory",
            "description": "Gestion AD/Samba",
            "service_name": "smbd",
            "app": "ad-manager",
        },
        Path("ad.json"),
    )
    assert role == Role("ad", "Active Directory", "Gestion AD/Samba", "smbd", "ad-manager")
