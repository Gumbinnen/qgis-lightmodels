from PyQt5.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import QFileDialog
from qgis.PyQt import QtWidgets, uic
from qgis.core import QgsMapLayerProxyModel, Qgis, QgsProject
from functools import partial
import os.path

from .data_manager import GravityModelDataManager
from . import log as log_function
from . import GRAVITY_MODEL_VAR_NAME as VAR, EXPORT_FILE_FORMAT, PLUGIN_DIR


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    PLUGIN_DIR, 'resources', 'ui', 'gravity_model_dockwidget.ui'))

LAYER_CMBOX_NAME = CMBOX_NAME = {
    'consumer':'consumer',
    'site':'site',
}

TAB_INDEX = {
    'analysis': 0,
    'diagram': 1,
    'export': 2,
}


class GravityModelWidget(QtWidgets.QDockWidget, FORM_CLASS):
    ready = pyqtSignal(dict)
    export_request = pyqtSignal(str, str, str)
    diagram_field_selected = pyqtSignal(str)
    diagram_uid_field_selected = pyqtSignal(str)
    
    def __init__(self, data_manager: GravityModelDataManager=None):
        super().__init__()
        self.data_manager = data_manager
        self.log = partial(log_function, title=type(self).__name__, tab_name='LightModels')
        
        self.setupUi(self)
        self.init_ui()

    def init_ui(self):
        def connect_visibility_changed(node):
            node.visibilityChanged.connect(self.update_excluded_layers)
            for child in node.children():
                connect_visibility_changed(child)
            
        # Фильтрация слоёв при добавлении в cmbox
        self.cmbox_consumer_layer.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.cmbox_site_layer.setFilters(QgsMapLayerProxyModel.VectorLayer)
        
        # Подключение сигнала visibilityChanged к update_excluded_layers() ко всем слоям дерева слоёв
        root_node = QgsProject.instance().layerTreeRoot()
        connect_visibility_changed(root_node)
        
        # Обновление field_cmbox при выборе слоя
        self.cmbox_consumer_layer.currentIndexChanged.connect(
            lambda: self.update_field_cmbox(CMBOX_NAME['consumer']))
        
        self.cmbox_site_layer.currentIndexChanged.connect(
            lambda: self.update_field_cmbox(CMBOX_NAME['site']))
        
        # Инициализация cmbox с допустимыми форматами файлов для экспорта
        self.cmbox_file_format.addItems(EXPORT_FILE_FORMAT.values())
        
        self.cmbox_field.currentTextChanged.connect(
            lambda field_name: self.diagram_field_selected.emit(field_name))
        
        self.btn_ok.clicked.connect(self.ok)
        
        self.btn_export.clicked.connect(self.export)
        
        # Инициализация field cmbox с выбранными слоями
        self.update_field_cmbox(CMBOX_NAME['consumer'])
        self.update_field_cmbox(CMBOX_NAME['site'])
        
    def update_excluded_layers(self):
        excluded_layers = []
        layers = QgsProject.instance().mapLayers().values()
        root = QgsProject.instance().layerTreeRoot()
        for layer in layers:
            node = root.findLayer(layer.id())
            if node and not node.isVisible():
                excluded_layers.append(layer)

        self.cmbox_consumer_layer.setExceptedLayerList(excluded_layers)
        self.cmbox_site_layer.setExceptedLayerList(excluded_layers)
        
    def update_field_cmbox(self, layer_cmbox_name: str):
        # Get cmbox_layer and cmbox_field by layer_cmbox_name
        cmbox_layer, cmbox_field = {
            layer_cmbox_name == CMBOX_NAME['consumer']: (self.cmbox_consumer_layer, self.cmbox_consumer_attractiveness_field),
            layer_cmbox_name == CMBOX_NAME['site']: (self.cmbox_site_layer, self.cmbox_site_attractiveness_field)
        }[True]
        
        if cmbox_layer is None or cmbox_field is None:
            self.log('Error: One of the combo boxes is None', level=Qgis.Warning)
            return

        # Если cmbox_layer пустой, выключить cmbox_field
        if cmbox_layer.count() <= 0:
            cmbox_field.setEnabled(False)
            cmbox_field.setCurrentIndex(-1)
            return
        
        # Добавить поля слоя в field_cmbox
        layer_fields = cmbox_layer.currentLayer().dataProvider().fields()
        field_names = [field.name() for field in layer_fields]
        
        cmbox_field.clear()
        cmbox_field.addItems(field_names)
        cmbox_field.setEnabled(True)
        cmbox_field.setCurrentIndex(0)

    def update_layer_pair_cmbox(self):   # TODO: Эта функция может быть умнее.
        if self.tab_widget.currentIndex() != TAB_INDEX['export']:
            return
        
        self.cmbox_layer_pair.clear()
        
        layer_pair = self.data_manager.get_all_layer_pairs()
        
        if not layer_pair:
            return
        
        for layer1, layer2 in layer_pair:
            if not layer1 or not layer2:
                continue
            self.cmbox_layer_pair.addItem(f'{layer1.name()} —— {layer2.name()}', (layer1.id(), layer2.id()))
    
    def get_input(self):
        def get_field(layer, field_name):
            fields = layer.fields()
            field_index = fields.indexOf(field_name)
            if field_index == -1:
                return None
            return fields.field(field_index)
        
        layer_consumer = self.cmbox_consumer_layer.currentLayer()
        layer_site = self.cmbox_site_layer.currentLayer()
        
        consumer_field_name = self.cmbox_consumer_attractiveness_field.currentText()
        field_consumer = get_field(layer_consumer, consumer_field_name)
        
        site_field_name = self.cmbox_site_attractiveness_field.currentText()
        field_site = get_field(layer_site, site_field_name)
        
        alpha = float(self.spbox_alpha.value())
        beta = float(self.spbox_beta.value())
        distance_limit_meters = int(self.spbox_distance_limit_meters.value())
        
        return layer_consumer, layer_site, field_consumer, field_site, alpha, beta, distance_limit_meters

    def ok(self):
        (layer_consumer, layer_site,
         field_consumer, field_site,
         alpha, beta, distance_limit_meters) = self.get_input()
        
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
        output_format = self.cmbox_file_format.currentText()
        if output_format not in EXPORT_FILE_FORMAT:
            self.log('Не удалось экспортировать файл. Выбранный формат не является допустимым', Qgis.Critical)
            return
        
        layer1_id, layer2_id = self.cmbox_layer_pair.currentData()
        
        if not layer1_id or not layer2_id:
                self.log('Не удалось экспортировать файл. Выбранный вариант не содержит данных.', Qgis.Critical)
                return
        
        data_path = self.data_manager.get_data_path_if_exists(layer1_id, layer2_id)
        
        if not data_path:
            self.log('Не удалось экспортировать файл. Файла не сущетсвует.', Qgis.Critical)
            return
        
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить файл как...", "",
            f"{output_format} Файл (*.{output_format.lower()});;Все файлы (*)",
            options=options)
        
        if not save_path:
            self.log('Не удалось сохранить файл. Ошибка при выборе директории сохранения.')
            return
        
        self.log("Экспорт файла...", Qgis.Info)
        self.export_request.emit(data_path, save_path, output_format)
