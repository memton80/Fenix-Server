"""Tests pour services.ldap_service — ldap3 mocké (pas de connexion réelle)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from services import ldap_service as ls
from services.ldap_service import LDAPService

# --- from_smb_conf ---------------------------------------------------------


def test_from_smb_conf_deduit_uri_et_base_dn(tmp_path: Path):
    conf = tmp_path / "smb.conf"
    conf.write_text("[global]\n   realm = EXAMPLE.LAN\n   workgroup = EXAMPLE\n", encoding="utf-8")

    svc = LDAPService.from_smb_conf(str(conf))

    assert svc.server_uri == "ldap://example.lan"
    assert svc.base_dn == "dc=example,dc=lan"


def test_from_smb_conf_fichier_absent_leve_filenotfound(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        LDAPService.from_smb_conf(str(tmp_path / "inexistant.conf"))


def test_from_smb_conf_sans_realm_leve_valueerror(tmp_path: Path):
    conf = tmp_path / "smb.conf"
    conf.write_text("[global]\n   workgroup = EXAMPLE\n", encoding="utf-8")
    with pytest.raises(ValueError, match="realm"):
        LDAPService.from_smb_conf(str(conf))


# --- connect / disconnect / is_connected ----------------------------------


def test_connect_etablit_la_connexion():
    svc = LDAPService("ldap://dc.example.lan", "dc=example,dc=lan", bind_dn="u", password="p")

    with patch.object(ls, "Server") as server_cls, patch.object(ls, "Connection") as conn_cls:
        conn_cls.return_value.bound = True
        svc.connect()

    server_cls.assert_called_once()
    conn_cls.assert_called_once()
    assert conn_cls.call_args.kwargs["user"] == "u"
    assert conn_cls.call_args.kwargs["auto_bind"] is True
    assert svc.is_connected() is True


def test_set_credentials_utilise_au_bind():
    svc = LDAPService("ldap://dc", "dc=x")
    svc.set_credentials(bind_dn="Administrator", password="pw")
    with patch.object(ls, "Server"), patch.object(ls, "Connection") as conn_cls:
        conn_cls.return_value.bound = True
        svc.connect()
    assert conn_cls.call_args.kwargs["user"] == "Administrator"
    assert conn_cls.call_args.kwargs["password"] == "pw"


def test_connect_echec_leve_runtimeerror():
    svc = LDAPService("ldap://dc", "dc=x")
    with patch.object(ls, "Server"), patch.object(ls, "Connection", side_effect=Exception("boom")):
        with pytest.raises(RuntimeError, match="Connexion LDAP échouée"):
            svc.connect()


def test_disconnect_unbind_et_reinitialise():
    svc = LDAPService("ldap://dc", "dc=x")
    conn = MagicMock()
    svc._connection = conn

    svc.disconnect()

    conn.unbind.assert_called_once_with()
    assert svc.is_connected() is False


def test_connection_sans_connexion_leve_runtimeerror():
    svc = LDAPService("ldap://dc", "dc=x")
    with pytest.raises(RuntimeError, match="non établie"):
        _ = svc.connection


# --- search ----------------------------------------------------------------


def test_search_retourne_les_entrees():
    svc = LDAPService("ldap://dc", "dc=base")
    conn = MagicMock(bound=True)
    entries = [object(), object()]
    conn.entries = entries
    svc._connection = conn

    result = svc.search("(objectClass=user)", ["cn", "mail"])

    conn.search.assert_called_once()
    assert conn.search.call_args.args[0] == "dc=base"
    assert conn.search.call_args.args[1] == "(objectClass=user)"
    assert conn.search.call_args.kwargs["attributes"] == ["cn", "mail"]
    assert result == entries


def test_search_sans_attributs_demande_tous():
    svc = LDAPService("ldap://dc", "dc=base")
    svc._connection = MagicMock(bound=True, entries=[])
    svc.search("(objectClass=group)")
    assert svc._connection.search.call_args.kwargs["attributes"] == ls._ALL_ATTRIBUTES


def test_search_echec_leve_runtimeerror():
    svc = LDAPService("ldap://dc", "dc=base")
    svc._connection = MagicMock(bound=True)
    svc._connection.search.side_effect = Exception("réseau")
    with pytest.raises(RuntimeError, match="Recherche LDAP échouée"):
        svc.search("(objectClass=user)")


# --- add / modify / delete -------------------------------------------------


def test_add_appelle_conn_add():
    svc = LDAPService("ldap://dc", "dc=base")
    conn = MagicMock(bound=True)
    conn.add.return_value = True
    svc._connection = conn

    svc.add("cn=x,dc=base", ["top", "user"], {"sAMAccountName": ["x"]})

    conn.add.assert_called_once_with("cn=x,dc=base", ["top", "user"], {"sAMAccountName": ["x"]})


def test_add_echec_leve_runtimeerror():
    svc = LDAPService("ldap://dc", "dc=base")
    conn = MagicMock(bound=True)
    conn.add.return_value = False
    svc._connection = conn
    with pytest.raises(RuntimeError, match="Échec LDAP"):
        svc.add("cn=x,dc=base", ["top"], {})


def test_modify_formate_en_modify_replace():
    svc = LDAPService("ldap://dc", "dc=base")
    conn = MagicMock(bound=True)
    conn.modify.return_value = True
    svc._connection = conn

    svc.modify("cn=x,dc=base", {"mail": "x@example.lan"})

    dn, changes = conn.modify.call_args.args
    assert dn == "cn=x,dc=base"
    assert changes == {"mail": [(ls.MODIFY_REPLACE, ["x@example.lan"])]}


def test_delete_appelle_conn_delete():
    svc = LDAPService("ldap://dc", "dc=base")
    conn = MagicMock(bound=True)
    conn.delete.return_value = True
    svc._connection = conn

    svc.delete("cn=x,dc=base")

    conn.delete.assert_called_once_with("cn=x,dc=base")
