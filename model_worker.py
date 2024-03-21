from qgis.PyQt.QtCore import QVariant, QThread
from PyQt5.QtCore import pyqtSignal
from qgis.core import QgsField, QgsProject, QgsVectorLayer, QgsLayerTreeLayer
from qgis.core import QgsLayerTreeGroup, QgsGraduatedSymbolRenderer
from qgis.core import QgsGeometry, QgsPoint, QgsFeature
from qgis.core import QgsSymbol, QgsSpatialIndex, QgsRendererCategory, QgsSingleSymbolRenderer
from qgis.core import QgsMarkerSymbol, QgsFeatureRequest, QgsCategorizedSymbolRenderer
import uuid
from concurrent.futures import ThreadPoolExecutor
import time
import re

class GravityModelWorker(QThread):
    finished = pyqtSignal() # pyqtSignal for when task is finished
    progress = pyqtSignal(int) # pyqtSignal to report the progress to progressbar

    def __init__(self, dlg_model):
        super(QThread, self).__init__()
        self.is_running = False
        self.is_calcelation_requested = False

        self.dlg_model = dlg_model
            
    def stop(self):
        self.is_running = False
        self.is_calcelation_requested = False
        self.finished.emit()
        
    def report_progress(self, n: float):
        self.dlg_model.progress_bar.setValue(n) # set the current progress in progress bar
        
    def validate_form_data(self, form_data: tuple) -> tuple:
        is_validation_errors = False
        layer, layer_centers, layer_field, layer_centers_field, alpha, beta, max_distance_thershold = form_data

        num_pattern = re.compile(r'^\-?[1-9][0-9]*\.?[0-9]*$')
        
        if not num_pattern.search(str(alpha)):
            self.show_validation_error("bad alpha")
            is_validation_errors = True
        
        if not num_pattern.search(str(beta)):
            self.show_validation_error("bad beta")
            is_validation_errors = True
        
        if not num_pattern.search(str(max_distance_thershold)):
            self.show_validation_error("bad distance")
            is_validation_errors = True
        
        if is_validation_errors:
            return (False, None)
        
        validated_form_data = (layer, layer_centers, layer_field, layer_centers_field, float(alpha), float(beta), float(max_distance_thershold))
        return (True, validated_form_data)
    
    def show_validation_error(self, e: str):
        print("Gravity model validation error:", e)
        
    def run(self):
        self.is_running = True
        self.progress.emit(0) # reset progressbar
        
        form_data = self.get_form_data()
        
        is_valid, validated_form_data = self.validate_form_data(form_data)
        if not is_valid:
            self.finished.emit()
            return
        
        # main payload
        self.run_gravity_model(*validated_form_data)
        
        self.finished.emit()
        
    def run_gravity_model(self, layer, layer_centers, layer_field, layer_centers_field, alpha, beta, max_distance_thershold):
        
        # Progress bar data. `progress_step` is 100% divided by features count, therefor used `features count` times in code.
        progress_step = 100 / (2 * layer.featureCount() + layer_centers.featureCount())
        current_progress = 0
        
        # создаем точечный слой
        point_layer = QgsVectorLayer("Point?crs=" + layer_centers.crs().authid(), f'{layer_centers.name()}', "memory")
        point_data = point_layer.dataProvider()
        point_data.addAttributes(layer_centers.fields())
        point_data.addFeatures(layer_centers.getFeatures())
        point_layer.updateFields()
        QgsProject.instance().addMapLayer(point_layer, False)
        # Computations modify new layer only. To achive this behaviour we're assigning a new point layer to layers_centers (because it based on layers_centers).
        layer_centers = point_layer
        
        # создаем группу и помещаем туда слой
        group = QgsLayerTreeGroup('Гравитационная модель')
        group.insertChildNode(0, QgsLayerTreeLayer(layer_centers))
        
        # Add field 'weight_...' with UUID to aboid potential conflicts
        weight_field_name = 'weight_' + str(uuid.uuid4()).replace('-', '')
        while not layer_centers.fields().indexFromName(weight_field_name) == -1: # Generate new UUID until unique
            weight_field_name = 'weight_' + str(uuid.uuid4()).replace('-', '')
        
        layer_centers.dataProvider().addAttributes([QgsField(weight_field_name, QVariant.Double)])
        layer_centers.updateFields()
        
        # Precompute distances for center features
        distances_center_to_feature = {}
        for center_feature in layer_centers.getFeatures():
            if self.is_calcelation_requested:
                self.stop()
                return
            
            center_feature_id = center_feature.id()
            center_feature_geometry = center_feature.geometry()
            
            for feature in layer.getFeatures():
                if self.is_calcelation_requested:
                    self.stop()
                    return
                
                distance = feature.geometry().distance(center_feature_geometry)
                if distance <= max_distance_thershold:
                    distances_center_to_feature[center_feature_id] = {feature.id(): distance}
                    
                # Track progress for every feature
                current_progress += progress_step
                self.progress.emit(current_progress)
                
            # Track progress for every center feature
            current_progress += progress_step
            self.progress.emit(current_progress)
        
        layer_centers.startEditing()
        for feature in layer.getFeatures():
            if self.is_calcelation_requested:
                self.stop()
                return
            
            # Track progress for every feature
            current_progress += progress_step
            self.progress.emit(current_progress)
            
            feature_id = feature.id()
            
            interaction_volume_dict = {}
            for center_feature in layer_centers.getFeatures():
                if self.is_calcelation_requested:
                    self.stop()
                    return
                
                center_feature_id = center_feature.id()

                distance = distances_center_to_feature.get(center_feature_id, {}).get(feature_id)
                if distance == None:
                    continue
                
                interaction_volume = float(center_feature[layer_centers_field]) ** alpha / distance ** beta
                interaction_volume_dict[center_feature_id] = interaction_volume

            total_interaction_volume = sum(interaction_volume_dict.values())
            if total_interaction_volume == 0:
                continue

            # Calculate probabilities and weights
            layer_field_value = float(feature[layer_field])
            for center_feature in layer_centers.getFeatures():
                if self.is_calcelation_requested:
                    self.stop()
                    return
                
                interaction_volume = interaction_volume_dict.get(center_feature.id())
                if interaction_volume == None:
                    continue
                
                probability_f_to_center_f = interaction_volume / total_interaction_volume
                weight = round(probability_f_to_center_f * layer_field_value, 2)
                center_feature[weight_field_name] = weight
                
                layer_centers.updateFeature(center_feature)
            
        layer_centers.commitChanges()

        # задание стиля для слоя поставщиков
        graduated_size = QgsGraduatedSymbolRenderer(weight_field_name)
        graduated_size.updateClasses(layer_centers, QgsGraduatedSymbolRenderer.EqualInterval, layer_centers.featureCount())
        graduated_size.setGraduatedMethod(QgsGraduatedSymbolRenderer.GraduatedSize)
        graduated_size.setSymbolSizes(4, 10)
        graduated_size.updateRangeLabels()
        layer_centers.setRenderer(graduated_size)
        layer_centers.triggerRepaint()
        
        if self.is_calcelation_requested:
            self.stop()
            return

        # добавляем созданную группу в проект
        root = QgsProject.instance().layerTreeRoot()
        root.insertChildNode(0, group)

    def get_form_data(self):
        layer = self.dlg_model.comboBox_feature_layer.itemData(self.dlg_model.comboBox_feature_layer.currentIndex())
        layer_centers = self.dlg_model.comboBox_feature_layer_2.itemData(self.dlg_model.comboBox_feature_layer_2.currentIndex())
        layer_field = self.dlg_model.comboBox_significance_attr.currentText()
        layer_centers_field = self.dlg_model.comboBox_significance_attr_2.currentText()
        alpha = self.dlg_model.textEdit_significance_power.text()
        beta = self.dlg_model.textEdit_distance_power.text()
        max_distance_thershold = self.dlg_model.textEdit_max_distance_thershold.text()
        return layer, layer_centers, layer_field, layer_centers_field, alpha, beta, max_distance_thershold


class CentersModelWorker(QThread):
    finished = pyqtSignal()
    progress = pyqtSignal(int)

    def __init__(self, dlg_model):
        super(QThread, self).__init__()
        self.is_running = False

        self.dlg_model = dlg_model

    def stop(self):
        self.is_running = False
        self.finished.emit()
        
    def report_progress(self, n): #? Move to worker class?
        self.dlg_model.progress_bar.setValue(n) # set the current progress in progress bar

    def run(self):
        self.is_running = True
        # получаем данные из формы
        layer, attr, multiplier, stop = self.get_form_data()
        
        start_time = time.time()
        
        # main payload
        self.run_centers_model(layer, attr, multiplier, stop)
        
        end_time = time.time()
        execution_time = end_time - start_time
        print("Execution time:", execution_time)
        
        self.finished.emit()

    def run_centers_model(self, layer, attr, multiplier, critical_size):
        # Progress bar data. `progress_step` is 100% divided by features count, therefor used `features count` times in code.
        progress_step = 100 / (2*layer.featureCount())
        current_progress = 0
        
        # добавляем колонку "to", если ее нет
        if layer.fields().indexFromName('to') == -1: 
            layer.dataProvider().addAttributes([QgsField('to', QVariant.Int)])
            layer.updateFields()

        # возвращает id точки для соединения
        def find_center_feature_id(f):
            f_id = f.id()
            population = int(f[attr])
            
            if population > critical_size:
                return f_id
                
            new_critical_size = population * multiplier
            certified_centers = layer.getFeatures(QgsFeatureRequest().setFilterExpression(f'{attr} > {new_critical_size}'))
            
            if not list(certified_centers):
                return f_id
            
            features_index = QgsSpatialIndex(certified_centers)
            nearest_point_id = features_index.nearestNeighbor(f.geometry().asPoint(), neighbors=1, maxDistance=0)[0]
            return nearest_point_id
        
        # f id —> f_center id
        f_goto_center_id_dict = {}
        
        # выполнение process_feature для каждой точки слоя в режиме многопоточности
        with ThreadPoolExecutor() as executor:
            centers_id = []
            for f in layer.getFeatures():
                centers_id.append(executor.submit(find_center_feature_id, f))
            
                # Track progress for every feature
                current_progress += progress_step
                self.progress.emit(current_progress)
                
        # запись в колонку 'to' каждой точки - id точки для соединения
        layer.startEditing()        #!!! Might just stop somewhere here
        features = list(layer.getFeatures())
        count = len(centers_id)
        for i in range(count):
            center_id = centers_id[i].result()
            features[i]['to'] = center_id
            layer.updateFeature(features[i])
            
            # Track progress for every feature
            current_progress += progress_step
            self.progress.emit(current_progress)
        layer.commitChanges()

        # ищет связанные точки для данной точки
        def get_connected_features(feature, layer):
            features = []  
            stack = [feature]  
            while stack:
                current_feature = stack.pop() 
                features.append(current_feature)  
                connect_features = list(layer.getFeatures(QgsFeatureRequest().setFilterExpression(f'"to" = {current_feature.id()} AND @id != {current_feature.id()}')))
                stack.extend(connect_features)
            return features

        # возвращает список точек и линий, относящихся к данному центру
        def process_center(center):
            result = {'f' : [], 'l': []}
            features_of_center = get_connected_features(center, layer)
            # добавляем в слои точки и линии
            for f in features_of_center:
                result['f'].append(f)
                p = list(layer.getFeatures(QgsFeatureRequest().setFilterExpression(f'@id = {f["to"]}')))[0]
                line_geom = QgsGeometry.fromPolyline([QgsPoint(f.geometry().asPoint()), QgsPoint(p.geometry().asPoint())])
                line_feature = QgsFeature()
                line_feature.setGeometry(line_geom)
                result['l'].append(line_feature)
            return result
        
        group = QgsLayerTreeGroup('Модель центральных мест')

        centers = list(layer.getFeatures(QgsFeatureRequest().setFilterExpression('@id = "to"')))
        
        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(process_center, center) for center in centers]
        
        # создаем точечный слой зоны влияния центра
        point_layer = QgsVectorLayer("Point?crs=" + layer.crs().authid(), 'пункты', "memory")
        point_data = point_layer.dataProvider()
        point_data.addAttributes(layer.fields())
        point_data.addAttributes([QgsField('center', QVariant.Int)])
        point_layer.updateFields()
        
        # создаем линейный слой зоны влияния центра
        line_layer = QgsVectorLayer('LineString?crs=' + layer.crs().authid(), 'линии', 'memory')
        line_data = line_layer.dataProvider()
        line_data.addAttributes([QgsField('center', QVariant.Int)])
        line_layer.updateFields()
        
        # заполняем слой пунктов и линий объектами
        for i in range(len(futures)):
            result = futures[i].result()
            for f in result['f']:
                fd = f.fields()
                a = f.attributes()
                fd.append(QgsField('center', QVariant.Int))
                f.setFields(fd)
                f.setAttributes(a + [centers[i].id()])
                point_data.addFeatures([f])
            for f in result['l']:
                fd = f.fields()
                a = f.attributes()
                fd.append(QgsField('center', QVariant.Int))
                f.setFields(fd)
                f.setAttributes(a + [centers[i].id()])
                line_data.addFeatures([f])

        # добавляем слои в проект
        QgsProject.instance().addMapLayer(point_layer, False)
        QgsProject.instance().addMapLayer(line_layer, False)

        # создаем слой центров
        centers_layer = QgsVectorLayer("Point?crs=" + layer.crs().authid(), "центры", "memory")
        prov = centers_layer.dataProvider()
        prov.addAttributes(layer.fields())
        centers_layer.updateFields()
        prov.addFeatures(centers)

        # задание стиля слою центров
        symbol = QgsMarkerSymbol.createSimple({'name': 'circle', 'color': 'orange'})
        symbol.setSize(5)
        renderer = QgsSingleSymbolRenderer(symbol)
        centers_layer.setRenderer(renderer)
        centers_layer.triggerRepaint()

        QgsProject.instance().addMapLayer(centers_layer, False)

        # создание стиля на основе уникальных значений атрибута для пунктов
        renderer = QgsCategorizedSymbolRenderer('center') 
        unique_values = point_layer.uniqueValues(point_layer.fields().indexOf('center'))
        for value in unique_values:
            symbol = QgsSymbol.defaultSymbol(point_layer.geometryType())
            category = QgsRendererCategory(value, symbol, str(value))
            renderer.addCategory(category)

        # применение стиля к слою пунктов
        point_layer.setRenderer(renderer)
        point_layer.triggerRepaint()

        # создание стиля на основе уникальных значений атрибута для линий
        renderer = QgsCategorizedSymbolRenderer('center')
        unique_values = line_layer.uniqueValues(line_layer.fields().indexOf('center'))
        for value in unique_values:
            symbol = QgsSymbol.defaultSymbol(line_layer.geometryType())
            category = QgsRendererCategory(value, symbol, str(value))
            renderer.addCategory(category)

        # срименение стиля к слою линий
        line_layer.setRenderer(renderer)
        line_layer.triggerRepaint()
        
        # добавлям слои в группу
        group.insertChildNode(0, QgsLayerTreeLayer(centers_layer))
        group.insertChildNode(group.children().__len__(), QgsLayerTreeLayer(point_layer))
        group.insertChildNode(group.children().__len__(), QgsLayerTreeLayer(line_layer))

        # добавляем созданную группу в проект
        root = QgsProject.instance().layerTreeRoot()
        root.insertChildNode(0, group)

    def get_form_data(self):
        layer = self.dlg_model.comboBox_feature_layer.itemData(self.dlg_model.comboBox_feature_layer.currentIndex())
        field = self.dlg_model.comboBox_significance_attr.currentText()
        multiplier = float(self.dlg_model.textEdit_significance_power.text())
        stop = float(self.dlg_model.textEdit_distance_power.text())
        return layer, field, multiplier, stop

