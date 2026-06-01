"""Tests pour main — point d'entrée QApplication (dépendances Qt mockées)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import main as main_module


def test_main_construit_applique_le_theme_et_lance():
    app = MagicMock()
    app.exec.return_value = 0
    theme = MagicMock()
    window = MagicMock()

    with patch.object(main_module, "QApplication", return_value=app) as app_cls, patch.object(
        main_module.ThemeManager, "from_system", return_value=theme
    ) as from_system, patch.object(
        main_module, "ADManagerWindow", return_value=window
    ) as window_cls:
        code = main_module.main()

    app_cls.assert_called_once()
    from_system.assert_called_once_with()  # thème issu de la préférence système
    theme.apply.assert_called_once_with(app)
    window_cls.assert_called_once_with(theme)
    window.show.assert_called_once_with()
    app.exec.assert_called_once_with()
    assert code == 0
