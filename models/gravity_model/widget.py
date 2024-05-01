from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QToolButton, QInputDialog, QMessageBox, QDockWidget
from qgis.PyQt import QtGui, QtWidgets, uic
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsMapLayerProxyModel
import os
from . import GRAVITY_MODEL_VAR_NAME, EXPORT_FILE_FORMAT

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'res', 'ui', 'gravity_model_dockwidget.ui'))

LAYER_CMBOX_NAME = {
    'consumer':'consumer',
    'site':'site',
}

class GravityModelWidget(QtWidgets.QDockWidget, FORM_CLASS):
    ready = pyqtSignal(dict)
    export = pyqtSignal(str, str, str)
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
        
        self.btn_export.clicked.connect(self.export)
        
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
        var = GRAVITY_MODEL_VAR_NAME
        layer_consumer, layer_site, field_consumer, field_site, alpha, beta, distance_limit_meters = self.get_input()
        
        input_data = {
            var['LAYER_CONSUMER']: layer_consumer,
            var['LAYER_SITE']: layer_site,
            var['FIELD_CONSUMER']: field_consumer,
            var['FIELD_SITE']: field_site,
            var['ALPHA']: alpha,
            var['BETA']: beta,
            var['DISTANCE_LIMIT_METERS']: distance_limit_meters,
        }
        
        self.ready.emit(input_data)

    def export(self):
        extension = EXPORT_FILE_FORMAT
        file_format = self.cmbox_file_format
        if file_format == extension['csv']:
            # TODO: Диалоговое окно с выбором путя к файлу и имени.
            dir_path = 
            file_name = 
            self.export.emit(dir_path, file_name, file_format)
            return

    # def d(self):
    #     var = 
    #     self.cmbox_uid_field
    #     self.cmbox_field
