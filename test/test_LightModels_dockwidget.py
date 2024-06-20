# coding=utf-8
"""DockWidget test.

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""

__author__ = 'dvornikov_alesha@mail.ru'
__date__ = '2023-07-25'
__copyright__ = 'Copyright 2023, LightModels'

import unittest

from qgis.PyQt.QtGui import QDockWidget

from OLD.LightModels_dockwidget import ModelsDockWidget

from utilities import get_qgis_app

QGIS_APP = get_qgis_app()


class ModelsDockWidgetTest(unittest.TestCase):
    """Test dockwidget works."""

    def setUp(self):
        """Runs before each test."""
        self.dockwidget = ModelsDockWidget(None)

    def tearDown(self):
        """Runs after each test."""
        self.dockwidget = None

    def test_dockwidget_ok(self):
        """Test we can click OK."""
        pass

if __name__ == "__main__":
    suite = unittest.makeSuite(ModelsDialogTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)

