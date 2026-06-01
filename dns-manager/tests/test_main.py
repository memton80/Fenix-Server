"""Tests pour le point d'entrée du DNS Manager."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import main


def test_main_construit_et_lance_la_fenetre():
    app = MagicMock()
    app.exec.return_value = 0
    with (
        patch("main.QApplication", return_value=app),
        patch("main.ThemeManager") as theme_cls,
        patch("main.DnsManagerWindow") as window_cls,
    ):
        theme_cls.from_system.return_value = MagicMock()
        code = main.main()
    window_cls.assert_called_once()
    window_cls.return_value.show.assert_called_once()
    assert code == 0
