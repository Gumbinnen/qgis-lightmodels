from PyQt5.QtCore import Qt, QObject, QVariant
from QtGui import QColor
from qgis.core import *
from functools import partial
import math, shutil

from light_models import LightModels
from .data_manager import GravityModelDataManager as DataManager
from .diagram_manager import GravityModelDiagramManager as DiagramManager
from .config import GravityModelConfig as Config
from .layer_event_handler import LayerEventHandler
from .widget import GravityModelWidget
from . import connect_once, log as log_function
from . import EXPORT_FILE_FORMAT


LINE_LAYER_NAME = 'линии [g. m.]'


class GravityModel(QObject):
    def __init__(self, parent: LightModels=None):
        super(GravityModel, self).__init__()
        self.iface = parent.iface
        self.plugin_dir = parent.plugin_dir
        
        # Переопределение функции log()
        self.log = partial(log_function, title=type(self).__name__, tab_name='LightModels')

        # Инициализация полей сервисов
        self.ui_widget: GravityModelWidget = None
        self.config: Config = None
        self.data_manager: DataManager = None
        self.diagram_manager: DiagramManager = None
        self.layer_event_handler: LayerEventHandler = None
        self.init_services()
        self.connect_signals()
        
    def init_services(self):
        #! Порядок инициализации важен!
        self.config = Config()
        self.data_manager = DataManager(parent=self)
        self.ui_widget = GravityModelWidget(data_manager=self.data_manager)
        self.diagram_manager = DiagramManager(ui_widget=self.ui_widget)
        self.layer_event_handler = LayerEventHandler(parent=self, data_manager=self.data_manager)
        
    def connect_signals(self):
        connect_once(self.ui_widget.ready, self.go)
        connect_once(self.ui_widget.export, self.export)
        
        connect_once(self.layer_event_handler.feature_selection, self.feature_selection)

    def export(self, data_path: str, save_path: str, desired_extension: str):
        if desired_extension not in EXPORT_FILE_FORMAT:
            self.log('Export failed. Unexpected file format.', level=Qgis.Critical)
            return
        
        # TODO:
        # source = #??? source test ???
        # destination = save_path #??? desired_extension ???
        
        try:
            # Копируем data_path —> save_path.  # (source) —> (destination)
            shutil.copy(data_path, save_path)
        except Exception as e:
            self.log('File export failed with exception: ', str(e), level=Qgis.Critical)

    def run(self):
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.ui_widget)
        self.ui_widget.show()
    
    def feature_selection(self): # TODO: LayerEventHandler could return selection_ids, so code could be optimized
        layer = self.iface.activeLayer()
        selection_ids = layer.selectedFeatureIds()
        
        if len(selection_ids) <= 0:
            return
        
        # Берём id первой точки из выбранных
        f_id = selection_ids[0]
        
        layer_centers = self.data_manager.get_second_layer(layer)
        if not layer_centers:
            return
        
        data_path = self.data_manager.get_data_path_if_exists(layer, layer_centers)
        if not data_path:
            return
        
        def is_id_field(field):
            return field == 'id'
        
        # # #       f_probability_values
        center_ids, f_prob_values = self.data_manager.get_gravity_values_by_feature_id(data_path, f_id)
        
        center_values = []
        diagram_field = self.diagram_manager.selected_field
        if diagram_field and not is_id_field(diagram_field):    # TODO: Установка пользователем кастомного id для center_ids 
            for center in layer_centers.getFeatures():          # (др. словами, добавление пользователем списка кастомных полей идентификации)
                center_values.append(center[diagram_field])

        center_values = map(str, center_values)

        # Diagram data is a list where each value is a tuple of 3:
        # center_id — ID центральной точки
        # c_value — Значение атрибута центральной точки. Атрибут выбран в diagram_field
        # f_prob_value — Значение вероятности, полученное в результате работы гравитационной модели
        diagram_data = []
        for c_id, c_value, f_prob_value in zip(center_ids, center_values, f_prob_values):
            if float(f_prob_value) != 0:
                diagram_data.append((c_id, c_value, f_prob_value))
        
        # TODO: Список выбранных полей, вместо простого self.diagram_field
        # TODO: 1. Выбор поля для универсальной идентификации? 2. Центры, обладающие одинаковым полем идентификации,
        #       считаются как один, и их данные по вероятностям складываются?
        #       1) Под вопросом.
        #       2) НЕТ! Не очевидное поведение.
        #
        pie_diagram = self.diagram_manager.construct_pie(diagram_data)
        
        # TODO: self.ui_widget.update(pie_diagram)?
        self.diagram_manager.update(pie_diagram)
        
        # Выделение линий от потребителей к поставщикам.
        line_layer: QgsVectorLayer = QgsProject.instance().mapLayersByName(LINE_LAYER_NAME)[0]
        line_layer.selectByExpression(f'"f_id"={f_id}', QgsVectorLayer.SetSelection)
        
        # Выделение линий от потребителей к поставщикам OLD VERSION:
        # line_layer: QgsVectorLayer = QgsProject.instance().mapLayersByName(LINE_LAYER_NAME)[0]
        # request: QgsFeatureRequest = QgsFeatureRequest().setFilterExpression(f'"f_id"={f_id}')
        # line_ids: list[str] = [line.id() for line in line_layer.getFeatures(request)]
        # line_layer.selectByIds(line_ids)
        
    def go(self, input_data):        
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
            point_layer = QgsVectorLayer("Point?crs=" + layer.crs().authid(), f'{layer.name()} [g. m.]', 'memory')
            
            point_layer_provider = point_layer.dataProvider()
            point_layer_provider.addAttributes(layer.fields())
            point_layer_provider.addFeatures(layer.getFeatures())
            point_layer.updateFields()
            return point_layer
        
        def create_line_layer(layer):
            line_layer = QgsVectorLayer('LineString?crs=' + layer.crs().authid(), LINE_LAYER_NAME, 'memory')
            line_layer.setOpacity(0.5)
            
            line_layer_provider = line_layer.dataProvider()
            line_layer_provider.addAttributes([QgsField('f_id', QVariant.Int), QgsField('tc_id', QVariant.Int)])
            line_layer.updateFields()
            return line_layer
        
        def get_feature_coords(feature):
            point = feature.geometry().asPoint()
            lat, long = point.y(), point.x()
            if lat == None or long == None:
                self.log('Не вышло получить координаты точки.', level=Qgis.Critical)
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

        def create_line_feature(f1, f2):
            line_geom = QgsGeometry.fromPolyline([QgsPoint(f1.geometry().asPoint()), QgsPoint(f2.geometry().asPoint())])
            line_feature = QgsFeature().setGeometry(line_geom)
            line_feature.setAttributes([f1.id(), f2.id()])
            return line_feature

        # Импорт данных из формы в self.config
        ok = self.config.update_from_input_data(input_data)
        if not ok:
            self.log(self.config.errors, level=Qgis.Critical)
            return

        # Получение переменных из self.config
        (layer, layer_tc,
        layer_attr, layer_attr_tc,
        alpha, beta, max_distance) = self.config.all_params()

        # Создаем точечный слой поставщиков
        layer_tc = create_point_layer(layer_tc)

        # Создаем точечный слой потребителей
        layer = create_point_layer(layer)

        # Создаем линейный слой зоны влияния центра
        line_layer = create_line_layer(layer)
        line_layer_provider = line_layer.dataProvider()
        
        # Добавляем слои в проект
        project = QgsProject.instance()
        project.addMapLayers([layer_tc, layer, line_layer], False)

        # Добавляем поле 'weight'
        if layer_tc.fields().indexFromName(WEIGHT_FIELD_NAME) == -1: 
            layer_tc.dataProvider().addAttributes([QgsField(WEIGHT_FIELD_NAME, QVariant.Double)])
            layer_tc.updateFields()
        
        # Для каждой точки делаем рассчет по формуле и записываем результат в слой в соответствующие поля
        # https://en.wikipedia.org/wiki/Huff_model
        data = []
        for f in list(layer.getFeatures()):
            # final value will be: h / total_h
            # h is the numerator of Huff_model formula
            # tc_h_dict is dict[tc_id] = h
            tc_h_dict = {}
            
            f_coords = get_feature_coords(f)
            if f_coords is None:
                self.log('Гравитационная модель остановлена.', level=Qgis.Critical)
                return
            
            for tc in layer_tc.getFeatures():                
                tc_coords = get_feature_coords(tc)
                if tc_coords is None:
                    self.log('Гравитционная модель остановлена.', level=Qgis.Critical)
                    return
                
                # distance_degrees = f.geometry().distance(tc.geometry())
                distance_meters = calculate_distance_in_meters(f_coords, tc_coords)

                if distance_meters > max_distance:
                    tc_h_dict[tc.id()] = 0
                    continue
                
                h = tc[layer_attr_tc]**alpha / distance_meters**beta
                tc_h_dict[tc.id()] = h
                
                # Добавить линии в line_layer
                line_feature = create_line_feature(f, tc)
                line_layer_provider.addFeatures([line_feature])

            # Для каждой точки f записываем row в data
            total_h = sum(tc_h_dict.values())
            row = [f.id()]
            for tc_id, h in tc_h_dict.items():
                if total_h == 0:
                    row.append(0)
                    continue
                
                probability = round(h / total_h, 4)
                row.append(probability)
            data.append(row)

        # Заголовок headers для данных выглядит так:
        # f, tc1_id, tc2_id, tc3_id, ...
        headers = ['f']
        for tc in layer_tc.getFeatures():
            headers.append(tc.id())
        
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

        # Задание стиля для слоя поставщиков
        graduated_symbol = create_graduated_symbol(WEIGHT_FIELD_NAME, n_classes=5, min_size=4, max_size=10)
        layer_tc.setRenderer(graduated_symbol)
        layer_tc.triggerRepaint()

        # Создаем группу и помещаем туда слои
        # may use group.children().__len__() for index
        group = QgsLayerTreeGroup(LAYER_GROUP_NAME)
        group.insertChildNode(0, QgsLayerTreeLayer(layer_tc))
        group.insertChildNode(1, QgsLayerTreeLayer(layer))
        group.insertChildNode(2, QgsLayerTreeLayer(line_layer))

        # Добавляем созданную группу в проект
        root = project.layerTreeRoot()
        root.insertChildNode(0, group)

        # Выбираем слой потребителей активным
        self.iface.setActiveLayer(layer)
