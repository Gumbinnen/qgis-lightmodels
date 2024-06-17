from PyQt5.QtCore import Qt, QObject, QVariant
# from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsField, QgsProject, QgsVectorLayer, QgsLayerTreeLayer, QgsVectorFileWriter
from qgis.core import QgsLayerTreeGroup, QgsGraduatedSymbolRenderer
from qgis.core import QgsGeometry, QgsPoint, QgsFeature, QgsWkbTypes, QgsCoordinateTransformContext
from qgis.core import QgsSymbol, QgsSpatialIndex, QgsRendererCategory, QgsSingleSymbolRenderer
from qgis.core import QgsProject, QgsTask, QgsApplication, QgsRendererRange
from qgis.core import QgsMarkerSymbol, QgsFeatureRequest, QgsCategorizedSymbolRenderer
from qgis.core import QgsApplication, QgsTask, Qgis, QgsMessageLog

from concurrent.futures import ThreadPoolExecutor
from helpers.logger import logger as log
from .data_manager import GravityModelDataManager as DataManager
from .diagram_manager import GravityModelDiagramManager as DiagramManager
from .config import GravityModelConfig as Config
from .layer_event_handler import LayerEventHandler
from .widget import GravityModelWidget
import os
import math
import shutil

from . import EXPORT_FILE_FORMAT
LINE_LAYER_NAME = 'линии [g. m.]'

class GravityModel(QObject):
    def __init__(self, parent=None):
        super(GravityModel, self).__init__()
        log('__init__() entered.', title=type(self).__name__)
        
        self.iface = parent.iface
        self.plugin_dir = parent.plugin_dir

        self.ui_widget: GravityModelWidget = None
        self.config = Config()
        self.data_manager = DataManager(self)
        self.diagram_manager = DiagramManager(self)
        self.layer_event_handler: LayerEventHandler = None
        
        self.init_ui()
        
    def init_ui(self):
        log('init_ui() entered.', title=type(self).__name__)
    
        self.ui_widget = GravityModelWidget(self)
        self.ui_widget.ready.connect(self.go)
        self.ui_widget.export.connect(self.export)
        
        self.layer_event_handler = LayerEventHandler(self)
        self.layer_event_handler.feature_selection.connect(self.feature_selection)

    def export(self, dir_path: str, file_name: str, file_format: str):
        if file_format not in EXPORT_FILE_FORMAT:
            log('Export failed. Unexpected file format.', title=type(self).__name__, level=Qgis.Error)
            return
        
        # TODO: Как определять source? Из cmb на виджете, но по умолчанию текущая группа
        source = self.data_manager.get…
        destination = os.path.join(dir_path, file_name)
        
        try:
            shutil.copy(source, destination)
        except Exception as e:
            log('File export failed with exception: ', str(e), title=type(self).__name__, level=Qgis.Error)

    def run(self):
        log('run() entered.', title=type(self).__name__)
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.ui_widget)
        self.ui_widget.show()
    
    def feature_selection(self):
        layer = self.iface.activeLayer()
        selection_ids = layer.selectedFeatureIds()
        
        if len(selection_ids) <= 0:
            return
        
        # Берём id первой точки из выбранных
        f_id = selection_ids[0]
        
        layer_centers = self.data_manager.get_second_layer(layer)
        if layer_centers == None:
            return
        
        data_path = self.data_manager.get_data_path_if_exists(layer, layer_centers)
        if data_path == None:
            return
        
        #           f_probability_values
        center_ids, f_prob_values = self.data_manager.get_gravity_values_by_feature_id(data_path, f_id)
        
        center_values = []
        diagram_field = self.diagram_manager.selected_field
        if diagram_field != None and not is_id_field(diagram_field): # TODO: is_id_field() for `id object`???
            for center in layer_centers.getFeatures():
                center_values.append(center[diagram_field])

        center_values = map(str, center_values)

        # Diagram data is dict where each value is dict:
        # center_id — ID центральной точки
        # c_value — Значение атрибута центральной точки. Атрибут выбран в diagram_field
        # f_prob_value — Значение вероятности, полученное в результате работы гравитационной модели
        diagram_data = {}
        for c_id, c_value, f_prob_value in zip(center_ids, center_values, f_prob_values):
            if float(f_prob_value) != 0:
                diagram_data[c_id] = {c_value: f_prob_value}
        
        # TODO: Список выбранных полей, вместо простого self.diagram_field
        # TODO: Выбор поля для универсальной идентификации? Если да, то центры, обладающие одинаковым полем идентификации,
        # считаются как один, и их данные по вероятностям складываются?
        #
        pie_diagram = self.diagram_manager.construct_pie(diagram_data)
        
        self.diagram_manager.update(pie_diagram)
        
        # выделение линий от потребителя к поставщикам
        line_layer: QgsVectorLayer = QgsProject.instance().mapLayersByName(LINE_LAYER_NAME)[0]
        line_layer.selectByExpression(f'"f_id"={f_id}', QgsVectorLayer.SetSelection)
        
        # OLD VERSION:
        # line_layer: QgsVectorLayer = QgsProject.instance().mapLayersByName(LINE_LAYER_NAME)[0]
        # request: QgsFeatureRequest = QgsFeatureRequest().setFilterExpression(f'"f_id"={f_id}')
        # line_ids: list[str] = [line.id() for line in line_layer.getFeatures(request)]
        # line_layer.selectByIds(line_ids)
        
    def go(self, input_data):
        log('go() entered.', title=type(self).__name__)
        
        WEIGHT_FIELD_NAME = 'weight_[g.m.]'
        LAYER_GROUP_NAME = 'Гравитационная модель'
        
        def calculate_distance_in_meters(f1, f2):
            EARTH_RADIUS = 6371
            
            lat1, lon1 = f1
            lat2, lon2 = f2
            lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
            
            # Haversine formula
            # https://en.wikipedia.org/wiki/Haversine_formula
            dlon = lon2 - lon1
            dlat = lat2 - lat1
            a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
            c = 2 * math.asin(math.sqrt(a))

            distance = EARTH_RADIUS * c
            
            # Конвертация в метры
            distance_meters = distance * 1000

            return distance_meters
        
        def create_point_layer(layer):
            point_layer = QgsVectorLayer("Point?crs=" + layer.crs().authid(), f'{layer.name()} [g. m.]', "memory")
            point_data = point_layer.dataProvider()
            point_data.addAttributes(layer.fields())
            point_data.addFeatures(layer.getFeatures())
            point_layer.updateFields()
            QgsProject.instance().addMapLayer(point_layer, False)
            return point_layer
        
        def create_line_layer(layer):
            line_layer = QgsVectorLayer('LineString?crs=' + layer.crs().authid(), LINE_LAYER_NAME, 'memory')
            line_data = line_layer.dataProvider()
            line_data.addAttributes([QgsField('f_id', QVariant.Int), QgsField('tc_id', QVariant.Int)])
            line_layer.updateFields()
            return line_layer
        
        def get_feature_coords(feature):
            point = feature.geometry().asPoint()
            lat, long = point.y(), point.x()
            if lat == None or long == None:
                log('Не вышло получить координаты точки.')
                return None
            return lat, long

        def create_graduated_symbol(field, n_classes, min_size, max_size):
            graduated_symbol = QgsGraduatedSymbolRenderer(field)
            graduated_symbol.updateClasses(layer_tc, QgsGraduatedSymbolRenderer.EqualInterval, n_classes)
            graduated_symbol.setGraduatedMethod(QgsGraduatedSymbolRenderer.GraduatedSize)
            graduated_symbol.setSymbolSizes(min_size, max_size)
            graduated_symbol.updateRangeLabels()
            ranges = []
            for lower, upper in graduated_symbol.ranges():
                symbol = QgsSymbol.defaultSymbol(layer_tc.geometryType())
                symbol.setColor(QColor("red"))  # Set the color for this range
                ranges.append(QgsRendererRange(lower, upper, symbol, f'{lower} - {upper}'))

            graduated_symbol.updateRanges(ranges)
            return graduated_symbol

        # Импорт данных из формы в self.config
        ok = self.config.update_from_input_data(input_data)
        if not ok:
            log(self.config.errors, level=Qgis.Error, title=type(self).__name__)
            return

        # Получение переменных из self.config
        layer, layer_tc = self.config.all_layers
        layer_attr, layer_tc_attr = self.config.all_fields
        alpha, beta, max_distance = self.config.all_numeric_params

        # создаем точечный слой поставщиков
        layer_tc = create_point_layer(layer_tc)

        # создаем точечный слой потребителей
        layer = create_point_layer(layer)

        # создаем линейный слой зоны влияния центра
        line_layer = create_line_layer(layer)

        # создаем группу и помещаем туда слои
        group = QgsLayerTreeGroup(LAYER_GROUP_NAME)
        group.insertChildNode(0, QgsLayerTreeLayer(layer))
        group.insertChildNode(0, QgsLayerTreeLayer(layer_tc))

        # добавляем поле 'weight'
        if layer_tc.fields().indexFromName(WEIGHT_FIELD_NAME) == -1: 
            layer_tc.dataProvider().addAttributes([QgsField(WEIGHT_FIELD_NAME, QVariant.Double)])
            layer_tc.updateFields()
        
        # для каждой точки делаем рассчет по формуле и записываем результат в слой в соответствующие поля
        data = []
        for f in list(layer.getFeatures()):
            tc_to_h_dict = {}

            f_coords = get_feature_coords(f)
            if f_coords is None:
                log('Гравитационная модель остановлена.', level=Qgis.Error, title=type(self).__name__)
                return
            
            for tc in layer_tc.getFeatures():                
                tc_coords = get_feature_coords(tc)
                if tc_coords is None:
                    log('Гравитционная модель остановлена.', level=Qgis.Error, title=type(self).__name__)
                    return
                
                # distance_degrees = f.geometry().distance(tc.geometry())
                distance_meters = calculate_distance_in_meters(f_coords, tc_coords)

                if distance_meters > max_distance:
                    tc_to_h_dict[tc.id()] = 0
                    continue
                
                tc_to_h_dict[tc.id()] = tc[layer_tc_attr]**alpha / distance_meters**beta
                
                # Добавить линии в line_layer
                line_geom = QgsGeometry.fromPolyline([QgsPoint(f.geometry().asPoint()), QgsPoint(tc.geometry().asPoint())])
                line_feature = QgsFeature()
                line_feature.setGeometry(line_geom)
                line_feature.setAttributes([f.id(), tc.id()])
                line_layer.dataProvider().addFeatures([line_feature])

            # Для каждой точки f записываем row в data
            total_h = sum(tc_to_h_dict.values())
            row = [f.id()]
            for tc_id, h in tc_to_h_dict.items():
                if total_h == 0:
                    row.append(0)
                    continue
                
                probability = round(h / total_h, 4)
                row.append(probability)
            data.append(row)

        headers = ['f']
        for tc in layer_tc.getFeatures():
            headers.append(tc.id())

        # добавялем линейный слой в группу
        line_layer.setOpacity(0.5)
        QgsProject.instance().addMapLayer(line_layer, False)
        group.insertChildNode(group.children().__len__(), QgsLayerTreeLayer(line_layer))
        
        # Записываем данные в .csv файл
        gm_data_path = self.data_manager.create_file(layer, layer_tc)
        self.data_manager.write(gm_data_path, data=data, headers=headers)

        # Получаем данные и заголовки из файла
        data, headers = self.data_manager.read(gm_data_path, contains_headers=True)

        # Проходим по всем столбцам начиная со второго
        layer_tc.startEditing()
        for col_index in range(1, len(headers)):
            tc_id = int(headers[col_index])
            column_sum = sum(float(row[col_index]) for row in data)
            
            tc = layer_tc.getFeature(tc_id)
            tc[WEIGHT_FIELD_NAME] = int(column_sum)
            layer_tc.updateFeature(tc)
        layer_tc.commitChanges()

        # задание стиля для слоя поставщиков
        graduated_symbol = create_graduated_symbol(WEIGHT_FIELD_NAME, n_classes=5, min_size=4, max_size=10)
        layer_tc.setRenderer(graduated_symbol)
        layer_tc.triggerRepaint()

        # добавляем созданную группу в проект
        root = QgsProject().instance().layerTreeRoot()
        root.insertChildNode(0, group)

        self.iface.setActiveLayer(layer)
