from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QToolButton, QInputDialog, QMessageBox
from qgis.PyQt import QtGui, QtWidgets, uic
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from qgis.PyQt.QtGui import QIcon
from lightmodels.helpers.icon_paths import ICON_SETTINGS_PATH, ICON_225DEGREES_PATH
import os

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'resources', 'ui', 'gravity_model_widget.ui'))

class GravityModelWidget(QtWidgets.QDockWidget, FORM_CLASS):
    
    closingPlugin = pyqtSignal()
    
    configure_signal = pyqtSignal()
    diagram_tool_signal = pyqtSignal()
    start_signal = pyqtSignal()
    cancel_signal = pyqtSignal()

    def __init__(self, parent=None):
        super(GravityModelWidget, self).__init__()
        self.iface = parent.iface
        
        self.setupUi(self)
        self.init_ui()

    def init_ui(self):
        self.configure_button.setIcon(QIcon(ICON_SETTINGS_PATH))
        self.diagram_tool_button.setIcon(QIcon(ICON_225DEGREES_PATH))
        
        # Connect buttons
        self.start_button.clicked.connect(self.send_start_signal)
        self.configure_button.clicked.connect(self.send_configure_signal)
        self.diagram_tool_button.clicked.connect(self.send_diagram_tool_signal)
        self.cancel_button.clicked.connect(self.send_cancel_signal)

    def run(self):
        self.iface.addDockWidget(Qt.TopDockWidgetArea, self)

    def disconnect_buttons(self):
        self.start_button.clicked.disconnect(self.send_start_signal)
        self.configure_button.clicked.disconnect(self.send_configure_signal)
        self.diagram_tool_button.clicked.disconnect(self.send_diagram_tool_signal)
        self.cancel_button.clicked.disconnect(self.send_cancel_signal)

    def send_configure_signal(self):
        self.configure_signal.emit()

    def send_start_signal(self):
        self.start_signal.emit()

    def send_cancel_signal(self):
        self.cancel_signal.emit()

    def send_diagram_tool_signal(self):
        self.diagram_tool_signal.emit()
        
    def closeEvent(self, event):
        self.disconnect_buttons()
        event.accept()
