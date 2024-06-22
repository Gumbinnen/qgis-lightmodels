from qgis.PyQt.QtCore import Qt, QObject, QVariant
from qgis.PyQt.QtGui import QColor
from qgis.core import *
from functools import partial
import math, shutil

from ... import ILightModel
from .data_manager import GravityModelDataManager as DataManager
from .diagram_manager import GravityModelDiagramManager as DiagramManager
from .config import GravityModelConfig as Config
from .layer_event_handler import LayerEventHandler
from .widget import GravityModelWidget
from . import connect_once, log as log_function
from . import EXPORT_FILE_FORMAT, GM_LAYER_STAMP_FIELD_NAME


LINE_LAYER_NAME = 'линии [g. m.]'


class GravityModel(QObject):
    def __init__(self, parent: ILightModel=None):
        super().__init__()
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
        connect_once(self.ui_widget.export_request, self.export)
        connect_once(self.layer_event_handler.feature_selection, self.feature_selection)

    def export(self, data_path: str, save_path: str, output_format: str):
        if output_format not in EXPORT_FILE_FORMAT:
            self.log('Export failed. Unexpected file format.', level=Qgis.Critical)
            return
        
        try:
            # Копируем файл из data_path в save_path.
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
            point_layer_provider.addAttributes([QgsField(GM_LAYER_STAMP_FIELD_NAME, QVariant.Bool)])
            point_layer_provider.addFeatures(layer.getFeatures())
            point_layer.updateFields()
            return point_layer
        
        def create_line_layer(layer):
            line_layer = QgsVectorLayer('LineString?crs=' + layer.crs().authid(), LINE_LAYER_NAME, 'memory')
            line_layer.setOpacity(0.5)
            
            line_layer_provider = line_layer.dataProvider()
            line_layer_provider.addAttributes([
                QgsField(GM_LAYER_STAMP_FIELD_NAME, QVariant.Bool),
                QgsField('f_id', QVariant.Int),
                QgsField('tc_id', QVariant.Int)])
            line_layer.updateFields()
            return line_layer
        
        def get_point_coords(point):
            return point.y(), point.x()

        def create_graduated_symbol(field_name: str, n_classes: int, min_size: int, max_size: int, color: QColor):
            graduated_symbol = QgsGraduatedSymbolRenderer(field_name)
            graduated_symbol.updateClasses(layer_tc, QgsGraduatedSymbolRenderer.EqualInterval, n_classes)
            graduated_symbol.setGraduatedMethod(QgsGraduatedSymbolRenderer.GraduatedSize)
            graduated_symbol.setSymbolSizes(min_size, max_size)
            graduated_symbol.updateRangeLabels()
            ranges = []
            for lower, upper in graduated_symbol.ranges():
                symbol = QgsSymbol.defaultSymbol(layer_tc.geometryType())
                symbol.setColor(color)
                ranges.append(QgsRendererRange(lower, upper, symbol, f'{lower} - {upper}'))

            graduated_symbol.updateRanges(ranges)
            return graduated_symbol

        def create_line_feature(point1, point2, associated_ids):
            line_geom = QgsGeometry.fromPolyline([point1, point2])
            line_feature = QgsFeature().setGeometry(line_geom)
            line_feature.setAttributes(associated_ids)
            return line_feature

        # Импорт данных из формы в self.config
        ok = self.config.update_from_input_data(input_data)
        if not ok:
            for error in self.config.errors:
                self.log('Config Validation Error: ', error, level=Qgis.Critical)
            return

        # Инстанс проекта
        project = QgsProject.instance()

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

        # Добавляем поле 'weight'
        if layer_tc.fields().indexFromName(WEIGHT_FIELD_NAME) == -1: 
            layer_tc.dataProvider().addAttributes([QgsField(WEIGHT_FIELD_NAME, QVariant.Double)])
            layer_tc.updateFields()
        
        # Добавляем слои в проект
        project.addMapLayers([layer_tc, layer, line_layer], False)
        
        # Получаем фичи, координаты фич и фичи как точки QgsPoint.
        # Размер массивов координат и точек должен совпадать с соответствующим массивом фич
        # len(features) == len(feature_coords) == len(features_as_points)
        # len(tc_features) == len(tc_coords) == len(tcs_as_points)
        features = list(layer.getFeatures())
        features_as_points = [QgsPoint(f.geometry().asPoint()) for f in features]
        f_coords = [get_point_coords(point) for point in features_as_points]
        
        tc_features = list(layer_tc.getFeatures())
        tcs_as_points = [QgsPoint(tc.geometry().asPoint()) for tc in tc_features]
        tc_coords = [get_point_coords(tc_point) for tc_point in tcs_as_points]
        
        if (None, None) in f_coords or (None, None) in tc_coords:
            self.log('Гравитационная модель остановлена. Не удалось получить координаты точки.', level=Qgis.Critical)
            return
        
        # Заголовок headers для данных выглядит так:
        # f, tc1_id, tc2_id, tc3_id, ...
        headers = ['f'] + [tc.id() for tc in tc_features]

        # Массив данных модели. Размер массива len(features) x len(tc_features)
        gm_data = []
        
        # Для каждой пары точек делаем рассчет по формуле и записываем результат в массив gm_data
        # https://en.wikipedia.org/wiki/Huff_model
        def huff_numerator(attractiveness, distance, α, β):
            return attractiveness**α / distance**β

        for f, f_coord, f_point in zip(features, f_coords, features_as_points):
            # list where each element is a numerator of Huff_model formula
            huff_numerators = []

            for tc, tc_coord, tc_point in zip(tc_features, tc_coords, tcs_as_points):
                # distance_degrees = f.geometry().distance(tc.geometry())
                distance_meters = calculate_distance_in_meters(f_coord, tc_coord)
                
                if distance_meters > max_distance:
                    huff_numerators.append(0)
                    continue
                
                huff_numerators.append(huff_numerator(tc[layer_attr_tc], distance_meters, alpha, beta))

                # Добавляем линии в line_layer
                line_feature = create_line_feature(f_point, tc_point, [f.id(), tc.id()])
                line_layer_provider.addFeatures([line_feature])
            
            total_h = sum(huff_numerators)
            row = [f.id()] + [
                round(h / total_h, 4)
                if total_h > 0
                else 0
                for h in huff_numerators
            ]
            gm_data.append(row)
        
        # Записываем данные в .csv файл
        gm_data_path = self.data_manager.create_file(layer, layer_tc)
        self.data_manager.write(gm_data_path, data=gm_data, headers=headers)

        # С этого момента используем только данные из .csv
        # Получаем данные и заголовки из файла
        data, headers = self.data_manager.read(gm_data_path, contains_headers=True)

        # Проходим по всем столбцам начиная со второго
        layer_tc.startEditing()
        for i_column in range(1, len(headers)):
            tc_id = int(headers[i_column])
            data_column_sum = sum(float(data_row[i_column]) for data_row in data)
            
            tc = layer_tc.getFeature(tc_id)
            if tc:
                tc[WEIGHT_FIELD_NAME] = int(data_column_sum)
                layer_tc.updateFeature(tc)
            
        layer_tc.commitChanges()

        # Задание стиля для слоя поставщиков
        graduated_symbol = create_graduated_symbol(
            WEIGHT_FIELD_NAME,
            n_classes=5, min_size=4, max_size=10,
            color=QColor("red"))
        layer_tc.setRenderer(graduated_symbol)
        layer_tc.triggerRepaint()

        # Создаем группу и помещаем туда слои
        # may use group.children().__len__() for node index
        group = QgsLayerTreeGroup(LAYER_GROUP_NAME)
        group.insertChildNode(0, QgsLayerTreeLayer(layer_tc))
        group.insertChildNode(1, QgsLayerTreeLayer(layer))
        group.insertChildNode(2, QgsLayerTreeLayer(line_layer))

        # Добавляем созданную группу в проект
        root = project.layerTreeRoot()
        root.insertChildNode(0, group)

        # Делаем слой потребителей активным
        self.iface.setActiveLayer(layer)
