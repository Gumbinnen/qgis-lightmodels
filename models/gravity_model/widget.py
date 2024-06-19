import os
from PyQt5.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import QFileDialog
from qgis.PyQt import QtWidgets, uic
from qgis.core import QgsLayerTreeNode, QgsMapLayerProxyModel, Qgis, QgsProject
from functools import partial
from .data_manager import GravityModelDataManager
from . import log as log_function
from . import GRAVITY_MODEL_VAR_NAME as VAR, EXPORT_FILE_FORMAT

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'res', 'ui', 'gravity_model_dockwidget.ui'))

LAYER_CMBOX_NAME = {
    'consumer':'consumer',
    'site':'site',
}

TAB_INDEX = {
    'analysis': 0,
    'diagram': 1,
    'export': 2,
}

SERVICE = {
    'config': 'config',
    'data_manager':'data_manager',
}

class GravityModelWidget(QtWidgets.QDockWidget, FORM_CLASS):
    ready = pyqtSignal(dict)
    export = pyqtSignal(str, str, str)
    diagram_field_selected = pyqtSignal(str)
    
    def __init__(self, injector, parent=None):
        super(GravityModelWidget, self).__init__()
        self.data_manager: GravityModelDataManager = self.injector.get(SERVICE['data_manager'])
        self.log = partial(log_function, title=type(self).__name__, tab_name='Light Models')
        
        self.setupUi(self)
        self.init_ui()

    def init_ui(self):
        # Инициализация cmbox с допустимыми форматами файлов для экспорта
        self.cmbox_file_format.addItems(EXPORT_FILE_FORMAT.values())
        
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
        
        self.tab_widget.currentChanged.connect(self.update_layer_pair_cmbox)
        
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

    def update_layer_pair_cmbox(self, index):   # TODO: Эта функция может быть умнее.
        self.cmbox_layer_pair.clear()           # Например, не очищать cmbox, если не изменился активный слой или содержимое папки data/
        if index == TAB_INDEX['export']:
            for layer1_name, layer2_name in self.data_manager.get_all_layer_pair_names():
                self.cmbox_layer_pair.addItem(' — '.join(layer1_name, layer2_name))

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
            VAR['LAYER_CONSUMER']: layer_consumer,
            VAR['LAYER_SITE']: layer_site,
            VAR['FIELD_CONSUMER']: field_consumer,
            VAR['FIELD_SITE']: field_site,
            VAR['ALPHA']: alpha,
            VAR['BETA']: beta,
            VAR['DISTANCE_LIMIT_METERS']: distance_limit_meters,
        }
        
        self.ready.emit(input_data)

    def export(self):
        desired_extension = self.cmbox_file_format
        if desired_extension in EXPORT_FILE_FORMAT.values():
            save_path = QFileDialog.getSaveFileName(self,
                                            'Выберите директорию для экспорта',
                                            "", 'CSV (*.csv)')
            
            layer_pair = self.cmbox_layer_pair
            [layer1_name, layer2_name] = layer_pair.split(' — ') # TODO: Переписать. Данные item'ов QLayerCombobox можно кастомизировать
            
            data_path = … # TODO: Узазатель на выбранный файл для экспорта
            
            if save_path:
                self.export.emit(data_path, save_path, desired_extension)
                self.log("Экспорт файла...", Qgis.Success)

    # def d(self):
    #     var = 
    #     self.cmbox_uid_field
    #     self.cmbox_field
