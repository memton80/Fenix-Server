"""Tests pour services.ad_service — LDAPService et subprocess (pkexec) mockés."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from models.ad_group import ADGroup
from models.ad_user import ADUser
from services import ad_service as ads
from services.ad_service import ADService

_BASE_DN = "dc=example,dc=lan"


def _entry(dn: str, **attrs: list[object]) -> SimpleNamespace:
    return SimpleNamespace(entry_dn=dn, entry_attributes_as_dict=attrs)


def _ldap() -> MagicMock:
    ldap = MagicMock()
    ldap.base_dn = _BASE_DN
    ldap.server_uri = "ldap://example.lan"
    ldap.is_connected.return_value = True
    ldap.search.return_value = []
    return ldap


def _service() -> tuple[ADService, MagicMock]:
    ldap = _ldap()
    return ADService(ldap), ldap


# --- utilisateurs : lecture ------------------------------------------------


def test_list_users_mappe_les_entrees():
    service, ldap = _service()
    ldap.search.return_value = [
        _entry("CN=jdoe,CN=Users,DC=example,DC=lan", sAMAccountName=["jdoe"], cn=["John"]),
    ]
    users = service.list_users()
    assert users == [
        ADUser("jdoe", "John", "", True, "CN=jdoe,CN=Users,DC=example,DC=lan"),
    ]
    assert ldap.search.call_args.args[0] == ads._USER_FILTER


def test_get_user_inconnu_leve_keyerror():
    service, ldap = _service()
    ldap.search.return_value = []
    with pytest.raises(KeyError):
        service.get_user("ghost")


# --- create_user (samba-tool) ----------------------------------------------


def test_create_user_via_samba_tool():
    service, ldap = _service()

    with patch("subprocess.run") as run:
        user = service.create_user(
            "jdoe", "S3cret!", display_name="John Doe", email="jdoe@example.lan"
        )

    # Création déléguée à pkexec samba-tool, aucune écriture LDAP.
    ldap.add.assert_not_called()
    run.assert_called_once()
    assert run.call_args.args[0] == [
        "pkexec",
        "samba-tool",
        "user",
        "create",
        "jdoe",
        "S3cret!",
        "--given-name=John Doe",
        "--mail-address=jdoe@example.lan",
    ]
    dn = "cn=jdoe,cn=Users,dc=example,dc=lan"
    assert user == ADUser("jdoe", "John Doe", "jdoe@example.lan", True, dn)


def test_create_user_minimal_sans_options():
    service, _ = _service()
    with patch("subprocess.run") as run:
        service.create_user("jdoe", "S3cret!")
    assert run.call_args.args[0] == ["pkexec", "samba-tool", "user", "create", "jdoe", "S3cret!"]


def test_create_user_echec_generique_leve_runtimeerror():
    service, _ = _service()
    err = subprocess.CalledProcessError(1, ["pkexec", "samba-tool"], stderr="connexion refusée")
    with patch("subprocess.run", side_effect=err):
        with pytest.raises(RuntimeError, match="Commande samba-tool échouée"):
            service.create_user("jdoe", "faible")


@pytest.mark.parametrize(
    "stderr",
    [
        "ERROR: Failed to set password: Password does not meet requirements",
        "Password value check failed: complexity not met",
        "check_password_restrictions: the password does not meet the policy",
    ],
)
def test_create_user_politique_mot_de_passe_message_clair(stderr: str):
    service, _ = _service()
    err = subprocess.CalledProcessError(1, ["pkexec", "samba-tool"], stderr=stderr)
    with patch("subprocess.run", side_effect=err):
        with pytest.raises(RuntimeError) as excinfo:
            service.create_user("jdoe", "weak")
    assert str(excinfo.value) == ads._PASSWORD_POLICY_MESSAGE
    assert "8 caractères minimum" in str(excinfo.value)


# --- modify_user (LDAP) ----------------------------------------------------


def test_modify_user_applique_les_changements():
    service, ldap = _service()
    ldap.search.return_value = [
        _entry(
            "CN=jdoe,CN=Users,DC=example,DC=lan",
            sAMAccountName=["jdoe"],
            displayName=["John"],
            mail=["old@example.lan"],
        )
    ]

    user = service.modify_user("jdoe", email="new@example.lan")

    ldap.modify.assert_called_once_with(
        "CN=jdoe,CN=Users,DC=example,DC=lan", {"mail": "new@example.lan"}
    )
    assert user.email == "new@example.lan"
    assert user.display_name == "John"  # inchangé


def test_modify_user_sans_changement_n_appelle_pas_modify():
    service, ldap = _service()
    ldap.search.return_value = [_entry("CN=jdoe,DC=x", sAMAccountName=["jdoe"])]
    service.modify_user("jdoe")
    ldap.modify.assert_not_called()


def test_modify_user_inconnu_leve_keyerror():
    service, ldap = _service()
    ldap.search.return_value = []
    with pytest.raises(KeyError):
        service.modify_user("ghost", email="x@y.z")


# --- delete_user (samba-tool) ----------------------------------------------


def test_delete_user_via_samba_tool():
    service, ldap = _service()
    with patch("subprocess.run") as run:
        service.delete_user("jdoe")
    ldap.delete.assert_not_called()
    assert run.call_args.args[0] == ["pkexec", "samba-tool", "user", "delete", "jdoe"]


def test_delete_user_echec_leve_runtimeerror():
    service, _ = _service()
    err = subprocess.CalledProcessError(1, ["pkexec", "samba-tool"], stderr="introuvable")
    with patch("subprocess.run", side_effect=err):
        with pytest.raises(RuntimeError, match="samba-tool"):
            service.delete_user("ghost")


# --- groupes ---------------------------------------------------------------


def test_list_groups_mappe_les_entrees():
    service, ldap = _service()
    ldap.search.return_value = [
        _entry("CN=admins,DC=example,DC=lan", sAMAccountName=["admins"], description=["Admins"]),
    ]
    groups = service.list_groups()
    assert groups == [ADGroup("admins", "Admins", "CN=admins,DC=example,DC=lan")]
    assert ldap.search.call_args.args[0] == ads._GROUP_FILTER


def test_create_group_via_samba_tool():
    service, ldap = _service()

    with patch("subprocess.run") as run:
        group = service.create_group("ventes", description="Équipe ventes")

    ldap.add.assert_not_called()
    assert run.call_args.args[0] == [
        "pkexec",
        "samba-tool",
        "group",
        "add",
        "ventes",
        "--description=Équipe ventes",
    ]
    dn = "cn=ventes,cn=Users,dc=example,dc=lan"
    assert group == ADGroup("ventes", "Équipe ventes", dn)


def test_create_group_minimal():
    service, _ = _service()
    with patch("subprocess.run") as run:
        service.create_group("ventes")
    assert run.call_args.args[0] == ["pkexec", "samba-tool", "group", "add", "ventes"]


def test_delete_group_via_samba_tool():
    service, ldap = _service()
    with patch("subprocess.run") as run:
        service.delete_group("ventes")
    ldap.delete.assert_not_called()
    assert run.call_args.args[0] == ["pkexec", "samba-tool", "group", "delete", "ventes"]


# --- domaine ---------------------------------------------------------------


def test_domain_info():
    service, _ = _service()
    info = service.domain_info()
    assert info["name"] == "example.lan"
    assert info["dc"] == "ldap://example.lan"
    assert info["samba"] == "connecté"


def test_domain_info_deconnecte():
    service, ldap = _service()
    ldap.is_connected.return_value = False
    assert service.domain_info()["samba"] == "déconnecté"
