"""Tests pour models.ad_group — entrées ldap3 simulées."""

from __future__ import annotations

from types import SimpleNamespace

from models.ad_group import ADGroup


def _entry(dn: str, **attrs: list[object]) -> SimpleNamespace:
    """Entrée ldap3 factice : entry_dn + entry_attributes_as_dict."""
    return SimpleNamespace(entry_dn=dn, entry_attributes_as_dict=attrs)


def test_from_ldap_entry_complet():
    entry = _entry(
        "CN=admins,CN=Users,DC=example,DC=lan",
        sAMAccountName=["admins"],
        description=["Administrateurs"],
        member=[
            "CN=jdoe,CN=Users,DC=example,DC=lan",
            "CN=asmith,CN=Users,DC=example,DC=lan",
        ],
    )
    group = ADGroup.from_ldap_entry(entry)
    assert group.name == "admins"
    assert group.description == "Administrateurs"
    assert group.dn == "CN=admins,CN=Users,DC=example,DC=lan"
    assert group.members == (
        "CN=jdoe,CN=Users,DC=example,DC=lan",
        "CN=asmith,CN=Users,DC=example,DC=lan",
    )


def test_from_ldap_entry_nom_repli_sur_cn():
    entry = _entry("CN=ventes,DC=x", cn=["ventes"])
    assert ADGroup.from_ldap_entry(entry).name == "ventes"


def test_from_ldap_entry_sans_membres_ni_description():
    entry = _entry("CN=vide,DC=x", sAMAccountName=["vide"])
    group = ADGroup.from_ldap_entry(entry)
    assert group.description == ""
    assert group.members == ()
