from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QInputDialog, QMessageBox, QDockWidget
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from lightmodels.widgets.GravityModelWidget import GravityModelWidget
from lightmodels.widgets.GravityModelConfigWidget import GravityModelConfigWidget
from qgis.PyQt.QtCore import QVariant, QThread
from PyQt5.QtCore import pyqtSignal
from qgis.core import QgsField, QgsProject, QgsVectorLayer, QgsLayerTreeLayer, QgsVectorFileWriter
from qgis.core import QgsLayerTreeGroup, QgsGraduatedSymbolRenderer
from qgis.core import QgsGeometry, QgsPoint, QgsFeature, QgsWkbTypes
from qgis.core import QgsSymbol, QgsSpatialIndex, QgsRendererCategory, QgsSingleSymbolRenderer, QgsCoordinateTransformContext
from qgis.core import QgsProject, QgsTask, QgsApplication
from qgis.core import QgsMarkerSymbol, QgsFeatureRequest, QgsCategorizedSymbolRenderer
import uuid
from qgis.core import QgsApplication, QgsTask, Qgis, QgsMessageLog
from concurrent.futures import ThreadPoolExecutor
from time import sleep
from models.gravity_model import GravityModelWidget
import os
import re
import json

class GravityModel(QObject):
    def __init__(self, parent=None):
        super(GravityModel, self).__init__()
        self.iface = parent.iface
        
        self.ui_widget = None
        self.config = None

        self.init_ui()
        
    def init_ui(self):
        self.ui_widget = GravityModelWidget(self)
        
        
    def run(self):
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.ui_widget)
        self.ui_widget.show()
        
    