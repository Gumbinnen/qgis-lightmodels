from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QToolButton, QInputDialog, QMessageBox, QDockWidget
from qgis.PyQt import QtGui, QtWidgets, uic
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsMapLayerProxyModel
import os
from . import GRAVITY_MODEL_VAR_NAME

# GRAVITY_MODEL_VAR_NAME = {
#     'LAYER_CONSUMER': 0,
#     'LAYER_SITE': 1,
#     'FIELD_CONSUMER': 2,
#     'FIELD_SITE': 3,
#     'ALPHA': 4,
#     'BETA': 5,
#     'DISTANCE_LIMIT_METERS': 6,
# }

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'res', 'ui', 'gravity_model_dockwidget.ui'))

LAYER_CMBOX_NAME = {
    'consumer':'consumer',
    'site':'site',
}

class GravityModelWidget(QtWidgets.QDockWidget, FORM_CLASS):
    ready = pyqtSignal(dict)
    diagram_field_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super(GravityModelWidget, self).__init__()
        
        self.setupUi(self)
        self.init_ui()

    def init_ui(self):
        # Обновление field_cmbox при выборе слоя
        self.cmbox_consumer_layer.currentIndexChanged.connect(
            lambda: self.update_field_cmbox(LAYER_CMBOX_NAME['consumer']))
        
        self.cmbox_site_layer.currentIndexChanged.connect(
            lambda: self.update_field_cmbox(LAYER_CMBOX_NAME['site']))
        
        # Фильтрация слоёв в cmbox
        self.cmbox_consumer_layer.setFilters(QgsMapLayerProxyModel.VectorLayer | QgsMapLayerProxyModel.Visible)
        self.cmbox_site_layer.setFilters(QgsMapLayerProxyModel.VectorLayer | QgsMapLayerProxyModel.Visible)
        
        self.cmbox_field.currentTextChanged.connect(
            lambda field_name: self.diagram_field_selected.emit(field_name))
        
        self.btn_ok.clicked.connect(self.ok)
        
    def update_field_cmbox(self, layer_cmbox_name: str):
        cmbox_layer, cmbox_field = {
            layer_cmbox_name == LAYER_CMBOX_NAME['consumer']: (self.cmbox_consumer_layer, self.cmbox_consumer_attractiveness_field),
            layer_cmbox_name == LAYER_CMBOX_NAME['site']: (self.cmbox_site_layer, self.cmbox_site_attractiveness_field)
        }[True]
        
        cmbox_field.setEnabled(True)
        
        # if choice_index == -1:
        #     cmbox_field.clear()
        #     cmbox_field.setEnabled(False)
        #     return
        
        layer_fields = cmbox_layer.currentLayer().dataProvider().fields()
        field_names = [field.name() for field in layer_fields]
        
        cmbox_field.clear()
        cmbox_field.addItems(field_names)

    def get_input(self):
        def get_field(layer, field_name):
            fields = layer.fields()
            field_index = fields.indexOf(field_name)
            if field_index == -1:
                return None
            return fields.field(field_index)
        
        layer_consumer = self.cmbox_consumer_layer.currentLayer()
        layer_site = self.cmbox_site_layer.currentLayer()
        
        consumer_field_name = self.cmbox_consumer_attractiveness_field
        field_consumer = get_field(layer_consumer, consumer_field_name)
        
        site_field_name = self.cmbox_site_attractiveness_field
        field_site = get_field(layer_site, site_field_name)
        
        alpha = float(self.spbox_alpha.value())
        beta = float(self.spbox_alpha.value())
        distance_limit_meters = int(self.spbox_alpha.value())
        
        return layer_consumer, layer_site, field_consumer, field_site, alpha, beta, distance_limit_meters
    

    def ok(self):
        layer_consumer, layer_site, field_consumer, field_site, alpha, beta, distance_limit_meters = self.get_input()
        
        input_data = {
            GRAVITY_MODEL_VAR_NAME['LAYER_CONSUMER']: layer_consumer,
            GRAVITY_MODEL_VAR_NAME['LAYER_SITE']: layer_site,
            GRAVITY_MODEL_VAR_NAME['FIELD_CONSUMER']: field_consumer,
            GRAVITY_MODEL_VAR_NAME['FIELD_SITE']: field_site,
            GRAVITY_MODEL_VAR_NAME['ALPHA']: alpha,
            GRAVITY_MODEL_VAR_NAME['BETA']: beta,
            GRAVITY_MODEL_VAR_NAME['DISTANCE_LIMIT_METERS']: distance_limit_meters,
        }
        
        self.ready.emit(input_data)
        