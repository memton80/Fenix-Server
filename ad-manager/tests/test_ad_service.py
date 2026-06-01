"""Tests pour services.ad_service — LDAPService et Polkit mockés."""

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


def _service(*, authorized: bool = True) -> tuple[ADService, MagicMock, MagicMock]:
    ldap = _ldap()
    polkit = MagicMock()
    polkit.check_authorization.return_value = authorized
    return ADService(ldap, polkit=polkit), ldap, polkit


# --- utilisateurs : lecture ------------------------------------------------


def test_list_users_mappe_les_entrees():
    service, ldap, _ = _service()
    ldap.search.return_value = [
        _entry("CN=jdoe,CN=Users,DC=example,DC=lan", sAMAccountName=["jdoe"], cn=["John"]),
    ]
    users = service.list_users()
    assert users == [
        ADUser("jdoe", "John", "", True, "CN=jdoe,CN=Users,DC=example,DC=lan"),
    ]
    assert ldap.search.call_args.args[0] == ads._USER_FILTER


def test_get_user_inconnu_leve_keyerror():
    service, ldap, _ = _service()
    ldap.search.return_value = []
    with pytest.raises(KeyError):
        service.get_user("ghost")


# --- create_user -----------------------------------------------------------


def test_create_user_ajoute_et_definit_le_mot_de_passe():
    service, ldap, polkit = _service(authorized=True)

    with patch("subprocess.run") as run:
        user = service.create_user(
            "jdoe", "S3cret!", display_name="John Doe", email="jdoe@example.lan"
        )

    polkit.check_authorization.assert_called_once_with(ads.POLKIT_ACTION_CREATE_USER)
    dn = "cn=jdoe,cn=Users,dc=example,dc=lan"
    ldap.add.assert_called_once()
    assert ldap.add.call_args.args[0] == dn
    assert ldap.add.call_args.args[1] == ads._USER_OBJECT_CLASSES
    attributes = ldap.add.call_args.args[2]
    assert attributes["sAMAccountName"] == "jdoe"
    assert attributes["displayName"] == "John Doe"
    assert attributes["mail"] == "jdoe@example.lan"
    # Plus de unicodePwd LDAP : le mot de passe passe par samba-tool (pkexec).
    assert "unicodePwd" not in attributes
    ldap.modify.assert_not_called()
    run.assert_called_once()
    assert run.call_args.args[0] == [
        "pkexec",
        "samba-tool",
        "user",
        "setpassword",
        "jdoe",
        "--newpassword=S3cret!",
    ]
    assert user == ADUser("jdoe", "John Doe", "jdoe@example.lan", True, dn)


def test_create_user_sans_mot_de_passe_n_appelle_pas_samba_tool():
    service, _, _ = _service(authorized=True)
    with patch("subprocess.run") as run:
        service.create_user("jdoe", "")
    run.assert_not_called()


def test_create_user_echec_setpassword_leve_runtimeerror():
    service, _, _ = _service(authorized=True)
    err = subprocess.CalledProcessError(1, ["pkexec", "samba-tool"], stderr="mot de passe faible")
    with patch("subprocess.run", side_effect=err):
        with pytest.raises(RuntimeError, match="mot de passe"):
            service.create_user("jdoe", "faible")


def test_create_user_refuse_par_polkit_leve_permissionerror():
    service, ldap, polkit = _service(authorized=False)
    with patch("subprocess.run") as run:
        with pytest.raises(PermissionError):
            service.create_user("jdoe", "pw")
    polkit.check_authorization.assert_called_once_with(ads.POLKIT_ACTION_CREATE_USER)
    ldap.add.assert_not_called()
    run.assert_not_called()


# --- modify_user -----------------------------------------------------------


def test_modify_user_applique_les_changements():
    service, ldap, polkit = _service(authorized=True)
    ldap.search.return_value = [
        _entry(
            "CN=jdoe,CN=Users,DC=example,DC=lan",
            sAMAccountName=["jdoe"],
            displayName=["John"],
            mail=["old@example.lan"],
        )
    ]

    user = service.modify_user("jdoe", email="new@example.lan")

    polkit.check_authorization.assert_called_once_with(ads.POLKIT_ACTION_MODIFY_USER)
    ldap.modify.assert_called_once_with(
        "CN=jdoe,CN=Users,DC=example,DC=lan", {"mail": "new@example.lan"}
    )
    assert user.email == "new@example.lan"
    assert user.display_name == "John"  # inchangé


def test_modify_user_sans_changement_n_appelle_pas_modify():
    service, ldap, _ = _service(authorized=True)
    ldap.search.return_value = [_entry("CN=jdoe,DC=x", sAMAccountName=["jdoe"])]
    service.modify_user("jdoe")
    ldap.modify.assert_not_called()


def test_modify_user_inconnu_leve_keyerror():
    service, ldap, _ = _service(authorized=True)
    ldap.search.return_value = []
    with pytest.raises(KeyError):
        service.modify_user("ghost", email="x@y.z")


def test_modify_user_refuse_par_polkit():
    service, ldap, _ = _service(authorized=False)
    with pytest.raises(PermissionError):
        service.modify_user("jdoe", email="x@y.z")
    ldap.search.assert_not_called()
    ldap.modify.assert_not_called()


# --- delete_user -----------------------------------------------------------


def test_delete_user_supprime_le_dn():
    service, ldap, polkit = _service(authorized=True)
    ldap.search.return_value = [
        _entry("CN=jdoe,CN=Users,DC=example,DC=lan", sAMAccountName=["jdoe"])
    ]

    service.delete_user("jdoe")

    polkit.check_authorization.assert_called_once_with(ads.POLKIT_ACTION_DELETE_USER)
    ldap.delete.assert_called_once_with("CN=jdoe,CN=Users,DC=example,DC=lan")


def test_delete_user_refuse_par_polkit():
    service, ldap, _ = _service(authorized=False)
    with pytest.raises(PermissionError):
        service.delete_user("jdoe")
    ldap.delete.assert_not_called()


# --- groupes ---------------------------------------------------------------


def test_list_groups_mappe_les_entrees():
    service, ldap, _ = _service()
    ldap.search.return_value = [
        _entry("CN=admins,DC=example,DC=lan", sAMAccountName=["admins"], description=["Admins"]),
    ]
    groups = service.list_groups()
    assert groups == [ADGroup("admins", "Admins", "CN=admins,DC=example,DC=lan")]
    assert ldap.search.call_args.args[0] == ads._GROUP_FILTER


def test_create_group_ajoute_l_entree():
    service, ldap, polkit = _service(authorized=True)

    group = service.create_group("ventes", description="Équipe ventes")

    polkit.check_authorization.assert_called_once_with(ads.POLKIT_ACTION_CREATE_GROUP)
    dn = "cn=ventes,cn=Users,dc=example,dc=lan"
    ldap.add.assert_called_once()
    assert ldap.add.call_args.args[0] == dn
    assert ldap.add.call_args.args[1] == ads._GROUP_OBJECT_CLASSES
    assert ldap.add.call_args.args[2]["description"] == "Équipe ventes"
    assert group == ADGroup("ventes", "Équipe ventes", dn)


def test_create_group_refuse_par_polkit():
    service, ldap, _ = _service(authorized=False)
    with pytest.raises(PermissionError):
        service.create_group("ventes")
    ldap.add.assert_not_called()


def test_delete_group_supprime_le_dn():
    service, ldap, polkit = _service(authorized=True)
    ldap.search.return_value = [_entry("CN=ventes,DC=example,DC=lan", sAMAccountName=["ventes"])]

    service.delete_group("ventes")

    polkit.check_authorization.assert_called_once_with(ads.POLKIT_ACTION_DELETE_GROUP)
    ldap.delete.assert_called_once_with("CN=ventes,DC=example,DC=lan")


def test_delete_group_inconnu_leve_keyerror():
    service, ldap, _ = _service(authorized=True)
    ldap.search.return_value = []
    with pytest.raises(KeyError):
        service.delete_group("ghost")


# --- domaine ---------------------------------------------------------------


def test_domain_info():
    service, ldap, _ = _service()
    info = service.domain_info()
    assert info["name"] == "example.lan"
    assert info["dc"] == "ldap://example.lan"
    assert info["samba"] == "connecté"


def test_domain_info_deconnecte():
    service, ldap, _ = _service()
    ldap.is_connected.return_value = False
    assert service.domain_info()["samba"] == "déconnecté"
