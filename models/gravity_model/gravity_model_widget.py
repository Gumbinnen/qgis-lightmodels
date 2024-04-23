from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QToolButton, QInputDialog, QMessageBox, QDockWidget
from qgis.PyQt import QtGui, QtWidgets, uic
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from qgis.PyQt.QtGui import QIcon
import os

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'res', 'ui', 'gravity_model_dockwidget.ui'))

class GravityModelWidget(QtWidgets.QDockWidget, FORM_CLASS):
    def __init__(self, parent=None):
        super(GravityModelWidget, self).__init__()
        self.iface = parent.iface
        
        self.setupUi(self)
        
