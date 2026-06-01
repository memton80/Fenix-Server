"""Tests pour models.ad_user — entrées ldap3 simulées."""

from __future__ import annotations

from types import SimpleNamespace

from models.ad_user import ADUser


def _entry(dn: str, **attrs: list[object]) -> SimpleNamespace:
    """Entrée ldap3 factice : entry_dn + entry_attributes_as_dict."""
    return SimpleNamespace(entry_dn=dn, entry_attributes_as_dict=attrs)


def test_from_ldap_entry_complet():
    entry = _entry(
        "CN=jdoe,CN=Users,DC=example,DC=lan",
        sAMAccountName=["jdoe"],
        displayName=["John Doe"],
        mail=["jdoe@example.lan"],
        userAccountControl=["512"],
        memberOf=["CN=admins,CN=Users,DC=example,DC=lan"],
    )
    user = ADUser.from_ldap_entry(entry)
    assert user.username == "jdoe"
    assert user.display_name == "John Doe"
    assert user.email == "jdoe@example.lan"
    assert user.enabled is True
    assert user.dn == "CN=jdoe,CN=Users,DC=example,DC=lan"
    assert user.groups == ("CN=admins,CN=Users,DC=example,DC=lan",)


def test_from_ldap_entry_compte_desactive():
    # 512 (NORMAL_ACCOUNT) | 2 (ACCOUNTDISABLE) = 514
    entry = _entry("CN=off,DC=x", sAMAccountName=["off"], userAccountControl=["514"])
    assert ADUser.from_ldap_entry(entry).enabled is False


def test_from_ldap_entry_display_name_repli_sur_cn():
    entry = _entry("CN=svc,DC=x", sAMAccountName=["svc"], cn=["Service"])
    assert ADUser.from_ldap_entry(entry).display_name == "Service"


def test_from_ldap_entry_attributs_absents():
    entry = _entry("CN=min,DC=x", sAMAccountName=["min"])
    user = ADUser.from_ldap_entry(entry)
    assert user.email == ""
    assert user.display_name == ""
    assert user.enabled is True  # userAccountControl absent → considéré actif
    assert user.groups == ()


def test_from_ldap_entry_uac_invalide_considere_actif():
    entry = _entry("CN=x,DC=x", sAMAccountName=["x"], userAccountControl=["abc"])
    assert ADUser.from_ldap_entry(entry).enabled is True
