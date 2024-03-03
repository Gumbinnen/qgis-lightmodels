# -*- coding: utf-8 -*-
"""
/***************************************************************************
 MyPluginDialog
                                 A QGIS plugin
 p
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2024-02-12
        git sha              : $Format:%H$
        copyright            : (C) 2024 by p
        email                : p
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import pyqtSignal

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'my_plugin_dialog_base.ui'))


class MyPluginDialog(QtWidgets.QDialog, FORM_CLASS):
    closingDialog = pyqtSignal()
    
    def __init__(self, parent=None):
        """Constructor."""
        super(MyPluginDialog, self).__init__(parent)
        
        self.setupUi(self)

    def closeEvent(self, event):
        # Добавьте ваш код обработки закрытия диалогового окна здесь
        self.closingDialog.emit()
        event.accept()  # Подтверждаем закрытие диалогового окна
