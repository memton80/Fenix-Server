"""Tests pour core.theme — portail XDG (bus de session) et Qt mockés."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from dasbus.error import DBusError

from core import theme
from core.theme import ThemeManager, ThemeMode


def _patch_portal(read_return=None, read_side_effect=None):
    """Patche SessionMessageBus pour simuler la réponse du portail XDG."""
    portal = MagicMock()
    if read_side_effect is not None:
        portal.Read.side_effect = read_side_effect
    else:
        portal.Read.return_value = read_return
    bus = MagicMock()
    bus.get_proxy.return_value = portal
    return patch.object(theme, "SessionMessageBus", return_value=bus), portal


# --- mode / couleurs ------------------------------------------------------


def test_mode_par_defaut_dark():
    """Le mode par défaut est sombre."""
    assert ThemeManager().mode is ThemeMode.DARK


def test_init_avec_mode_light():
    """Le mode initial peut être imposé."""
    assert ThemeManager(ThemeMode.LIGHT).mode is ThemeMode.LIGHT


def test_set_mode_change_les_couleurs():
    """Changer de mode change la couleur retournée pour un même token."""
    tm = ThemeManager(ThemeMode.DARK)
    dark_bg = tm.color("background")
    tm.set_mode(ThemeMode.LIGHT)
    assert tm.mode is ThemeMode.LIGHT
    assert tm.color("background") != dark_bg


def test_color_token_inconnu_leve_keyerror():
    """Un token de couleur inconnu lève KeyError."""
    with pytest.raises(KeyError):
        ThemeManager().color("inexistant")


def test_les_deux_palettes_ont_les_memes_tokens():
    """DARK et LIGHT exposent exactement les mêmes tokens."""
    assert set(theme._PALETTES[ThemeMode.DARK]) == set(theme._PALETTES[ThemeMode.LIGHT])


# --- styles Qt ------------------------------------------------------------


def test_label_style_contient_la_couleur_de_texte():
    tm = ThemeManager(ThemeMode.DARK)
    assert tm.color("text") in tm.label_style()


def test_button_style_contient_accent_et_hover():
    tm = ThemeManager(ThemeMode.DARK)
    style = tm.button_style()
    assert tm.color("accent") in style
    assert tm.color("accent_hover") in style


def test_apply_pose_le_style_global_sur_lapp():
    """apply délègue à QApplication.setStyleSheet avec le style global."""
    tm = ThemeManager(ThemeMode.LIGHT)
    app = MagicMock()
    tm.apply(app)
    app.setStyleSheet.assert_called_once_with(tm.global_style())


# --- détection KDE / portail XDG -----------------------------------------


def test_detect_system_mode_prefer_dark():
    """color-scheme == 1 -> DARK."""
    p, portal = _patch_portal(read_return=1)
    with p:
        assert ThemeManager.detect_system_mode() is ThemeMode.DARK
    portal.Read.assert_called_once_with(
        theme.APPEARANCE_NAMESPACE, theme.COLOR_SCHEME_KEY
    )


def test_detect_system_mode_prefer_light():
    """color-scheme == 2 -> LIGHT."""
    p, _ = _patch_portal(read_return=2)
    with p:
        assert ThemeManager.detect_system_mode() is ThemeMode.LIGHT


def test_detect_system_mode_no_preference():
    """color-scheme == 0 -> None (pas de préférence)."""
    p, _ = _patch_portal(read_return=0)
    with p:
        assert ThemeManager.detect_system_mode() is None


def test_detect_system_mode_variant_enveloppe():
    """Une valeur enveloppée en variant est correctement déballée."""
    inner = MagicMock()
    inner.unpack.return_value = 1
    p, _ = _patch_portal(read_return=inner)
    with p:
        assert ThemeManager.detect_system_mode() is ThemeMode.DARK


def test_detect_system_mode_erreur_dbus_retourne_none():
    """Une DBusError pendant la lecture du portail donne None (pas de propagation)."""
    p, _ = _patch_portal(read_side_effect=DBusError("pas de portail"))
    with p:
        assert ThemeManager.detect_system_mode() is None


# --- sync / from_system ---------------------------------------------------


def test_sync_with_system_applique_le_mode_detecte():
    tm = ThemeManager(ThemeMode.DARK)
    with patch.object(ThemeManager, "detect_system_mode", return_value=ThemeMode.LIGHT):
        assert tm.sync_with_system() is True
    assert tm.mode is ThemeMode.LIGHT


def test_sync_with_system_conserve_le_mode_si_indetectable():
    tm = ThemeManager(ThemeMode.DARK)
    with patch.object(ThemeManager, "detect_system_mode", return_value=None):
        assert tm.sync_with_system() is False
    assert tm.mode is ThemeMode.DARK


def test_from_system_utilise_le_mode_detecte():
    with patch.object(ThemeManager, "detect_system_mode", return_value=ThemeMode.LIGHT):
        assert ThemeManager.from_system().mode is ThemeMode.LIGHT


def test_from_system_retombe_sur_le_fallback():
    with patch.object(ThemeManager, "detect_system_mode", return_value=None):
        tm = ThemeManager.from_system(fallback=ThemeMode.LIGHT)
    assert tm.mode is ThemeMode.LIGHT


# --- icônes ---------------------------------------------------------------


def test_icon_delegue_a_qicon_fromtheme():
    """icon() délègue à QIcon.fromTheme avec le nom demandé."""
    sentinel = object()
    with patch("PySide6.QtGui.QIcon") as mock_qicon:
        mock_qicon.fromTheme.return_value = sentinel
        result = ThemeManager().icon("dialog-warning")
    assert result is sentinel
    mock_qicon.fromTheme.assert_called_once_with("dialog-warning")
