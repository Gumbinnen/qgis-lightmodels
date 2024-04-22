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
import os
import re
import json

class GravityModel(QObject):
    progress_signal = pyqtSignal(int)

    def __init__(self, parent=None):
        super(GravityModel, self).__init__()
        self.iface = parent.iface
        self.task_manager = QgsApplication.taskManager()
        self.gravity_task_id = None
        
        # Main and config widgets.
        self.gravity_widget = GravityModelWidget(self)
        self.config_widget = GravityModelConfigWidget(self)
        
        # Data from config_widget.
        self.config = None
        
        # Progress bar data.
        self.current_progress = 0

        self.init_ui()

    def init_ui(self):
        self.connect_gravity_widget_signals()
        self.connect_config_widget_signals()

    def connect_gravity_widget_signals(self):
        self.gravity_widget.configure_signal.connect(self.configure_model)
        self.gravity_widget.diagram_tool_signal.connect(self.diagram_tool)
        self.gravity_widget.start_signal.connect(self.start)
        self.gravity_widget.cancel_signal.connect(self.cancel_computation)
        self.gravity_widget.closing_widget.connect(self.new_gravity_widget)

    def connect_config_widget_signals(self):
        self.config_widget.update_config_signal.connect(self.update_config)
        self.config_widget.start_signal.connect(self.start)
        self.config_widget.cancel_signal.connect(self.cancel_computation)
        self.config_widget.closing_widget.connect(self.new_config_widget)
   
    def disconnect_gravity_widget_signals(self):
        self.gravity_widget.configure_signal.disconnect(self.configure_model)
        self.gravity_widget.diagram_tool_signal.disconnect(self.diagram_tool)
        self.gravity_widget.start_signal.disconnect(self.start)
        self.gravity_widget.cancel_signal.disconnect(self.cancel_computation)
        self.gravity_widget.closing_widget.disconnect(self.new_gravity_widget)
        
    def disconnect_config_widget_signals(self):
        self.config_widget.update_config_signal.disconnect(self.update_config)
        self.config_widget.start_signal.disconnect(self.start)
        self.config_widget.cancel_signal.disconnect(self.cancel_computation)
        self.config_widget.closing_widget.disconnect(self.new_config_widget)

    def new_config_widget(self):
        self.config_widget = GravityModelConfigWidget(self)

    def new_gravity_widget(self):
        self.gravity_widget = GravityModelWidget(self)
    
    def configure_model(self):
        self.config_widget.run()

    def run(self):
        self.gravity_widget.run()
        # self.config_widget.run() # Start config widget automatically?
        
    def start(self):
        def log(message, *text:str):
            if text:
                for peace in text:
                    message += ' '+peace
            QgsMessageLog.logMessage("GravityModel: "+message, 'LightModelsLog', level=Qgis.Info)

        log("Начало.")

        self.config_widget.close()

        if self.config is None:
            log("Gravity model config is None.")
            return

        isValidConfig, whyNotValid = self.is_current_config_valid()
        if not isValidConfig:
            log('Настройки модели неверны', whyNotValid)
            print("Настройки модели неверны:", whyNotValid)
            return

        # Клонирование слоёв. Теперь работаем только с копиями layer и layer_centers.
        #
        layer_original = self.config['layer']
        layer_centers_original = self.config['layer_centers']

        layer_centers, error_message = self.clone_layer(layer_centers_original.id())
        if layer_centers is None:
            print("Cloning layer error:", error_message)
            return

        layer, error_message = self.clone_layer(layer_original.id())
        if layer is None:
            print("Cloning layer error:", error_message)
            return

        layer.setName(layer.name() + "_LM")
        layer_centers.setName(layer_centers.name() + "_LM")

        # Создать группу и поместить внутрь слои.
        #
        group = QgsLayerTreeGroup("Гравитационная модель")
        group.insertChildNode(0, QgsLayerTreeLayer(layer_centers))
        group.insertChildNode(1, QgsLayerTreeLayer(layer))

        # Добавить атрибуты.
        #
        diagram_field_name = "LM_diagram_data"
        layer.dataProvider().addAttributes([QgsField(diagram_field_name, QVariant.String)])
        layer.updateFields()

        weight_field_name = "LM_weight"
        layer_centers.dataProvider().addAttributes([QgsField(weight_field_name, QVariant.Double)])
        layer_centers.updateFields()

        # Adapt config layers for gravity_model_task. It should work with copies of the layers only.
        # Адаптировать self.config для gravity_model_task. Task должен работать исключительно с КОПИЯМИ слоёв.
        #
        task_config = self.config
        task_config['layer'] = layer
        task_config['layer_centers'] = layer_centers
        task_config['diagram_field_name'] = diagram_field_name
        task_config['weight_field_name'] = weight_field_name

        gravity_model_task = GravityModelTask(task_config)
        # gravity_model_task.progressChanged.connect(self.track_progress)

        self.gravity_task_id = self.task_manager.addTask(gravity_model_task)

        # Установить стили для символов на карте.
        #
        style_config = {}
        style_config["layer"] = layer_centers
        style_config["weight_field_name"] = weight_field_name
        style_config['symbol_sizes'] = (4, 10)
        self.set_style(style_config)

        # Добавить группу со слоями в список слоёв.
        #
        root = QgsProject.instance().layerTreeRoot()
        root.insertChildNode(0, group)

        saved = QgsProject.instance().write()
        if saved:
            log('Проект сохранён.')
        else:
            log('Ошибка при сохранении проекта.')
    
    def clone_layer(self, layer_id):
        if layer_id not in QgsProject.instance().mapLayers():
            return None, "layer id not found"
        
        original_layer = QgsProject.instance().mapLayer(layer_id)
        if original_layer is None:
            return None, "Layer not found."
        
        return original_layer.clone(), None

    def set_style(self, style_config):
        layer = style_config['layer']
        weight_field_name = style_config["weight_field_name"]
        min_value, max_value = style_config['symbol_sizes']
        
        graduated_size = QgsGraduatedSymbolRenderer(weight_field_name)
        
        graduated_size.updateClasses(layer, QgsGraduatedSymbolRenderer.EqualInterval, layer.featureCount())
        graduated_size.setGraduatedMethod(QgsGraduatedSymbolRenderer.GraduatedSize)
        graduated_size.setSymbolSizes(min_value, max_value)
        graduated_size.updateRangeLabels()
        
        layer.setRenderer(graduated_size)
        layer.triggerRepaint()
        
    def update_config(self, config):
        self.config = config

    def update_progress(self, progress):
        self.progress_signal.emit(progress)

    def is_current_config_valid(self):
        config = self.config
        layer = config['layer']
        layer_centers = config['layer_centers']
        layer_field = config['layer_field']
        layer_centers_field = config['layer_centers_field']
        alpha = config['alpha']
        beta = config['beta']
        max_distance = config['max_distance']
        
        #
        # validate data, return (False, errorMessage) if not valid component
        #

        return True, None

    def cancel_computation(self):
        self.log("Task cancelation request.")
        task_id = self.gravity_task_id
        if task_id:
            task = self.task_manager.task(task_id)
            if task:
                task.cancel()
                self.log("Task canceled.")

    def track_progress(self, progress):
        pass

    def diagram_tool(self):
        pass

    def log(self, message, *text:str):
        if text:
            for peace in text:
                message += ' '+peace
        QgsMessageLog.logMessage("GravityModel: "+message, 'LightModelsLog', level=Qgis.Info)

    def closeEvent(self, event):
        self.log('Close.')
        
        self.disconnect_gravity_widget_signals()
        self.disconnect_config_widget_signals()
        event.accept()

    #
    # TEST
    #
    def precompute_distances1(layer_centers, layer, max_distance_thershold, progress_step, current_progress, progress_callback):
        distances_center_to_feature = {}
        futures = []

        def compute_distances(center_feature):
            nonlocal distances_center_to_feature
            if self.is_cancellation_requested:
                self.stop()
                return

            center_feature_id = center_feature.id()
            center_feature_geometry = center_feature.geometry()

            for feature in layer.getFeatures():
                if self.is_cancellation_requested:
                    self.stop()
                    return

                distance = feature.geometry().distance(center_feature_geometry)
                if distance <= max_distance_thershold:
                    distances_center_to_feature[center_feature_id] = {feature.id(): distance}

                current_progress += progress_step
                progress_callback.emit(current_progress)

            current_progress += progress_step
            progress_callback.emit(current_progress)

        with ThreadPoolExecutor() as executor:
            for center_feature in layer_centers.getFeatures():
                future = executor.submit(compute_distances, center_feature)
                futures.append(future)

            for future in as_completed(futures):
                pass  # Wait for all computations to complete

        return distances_center_to_feature

    def calculate_probabilities1(self, layer_centers, layer, distances_center_to_feature, layer_field, alpha, beta, weight_field_name, progress_step, current_progress, progress_callback):
        interaction_volume_dict = {}

        futures = []

        def compute_probabilities(self, feature):
            nonlocal interaction_volume_dict
            if self.is_cancellation_requested:
                self.stop()
                return

            current_progress += progress_step
            progress_callback.emit(current_progress)

            feature_id = feature.id()

            interaction_volume_dict[feature_id] = {}
            for center_feature in layer_centers.getFeatures():
                if self.is_cancellation_requested:
                    self.stop()
                    return

                center_feature_id = center_feature.id()

                distance = distances_center_to_feature.get(center_feature_id, {}).get(feature_id)
                if distance is None:
                    continue
                
                interaction_volume = float(center_feature[layer_field]) ** alpha / distance ** beta
                interaction_volume_dict[feature_id][center_feature_id] = interaction_volume

        with ThreadPoolExecutor() as executor:
            for feature in layer.getFeatures():
                future = executor.submit(compute_probabilities, feature)
                futures.append(future)

            for future in as_completed(futures):
                pass  # Wait for all computations to complete

        return interaction_volume_dict
    #
    # END TEST
    #


class GravityModelTask(QgsTask):
    def __init__(self, config):
        super().__init__()
        self.exception = None
        
        self.config = config
        
    def run(self):
        def log(message):
            QgsMessageLog.logMessage("GravityModelTask: "+message, 'LightModelsLog', level=Qgis.Info)
        
        def logmedaddy(message):
            QgsMessageLog.logMessage("GravityModelTaskDaddy: "+str(message), 'LightModelsLogDaddy', level=Qgis.Info)
        
        def logmemommy(message):
            QgsMessageLog.logMessage("GravityModelTaskMommy: "+str(message), 'LightModelsLogMommy', level=Qgis.Info)
        
        log("Начало выполнения.")
        
        # Get data.
        #
        config = self.config
        layer = config['layer']        
        layer_field = config['layer_field']
        diagram_field_name = config['diagram_field_name']
        
        layer_centers = config['layer_centers']
        layer_centers_field = config['layer_centers_field']
        weight_field_name = config['weight_field_name']
        
        max_distance = float(config['max_distance'])
        alpha = float(config['alpha'])
        beta = float(config['beta'])
        
        log("Данные получены.")
        
        # Precompute distances.
        #
        distances_center_to_feature = {}
        for center_feature in layer_centers.getFeatures():
            
            center_feature_id = center_feature.id()
            center_feature_geometry = center_feature.geometry()
            
            for feature in layer.getFeatures():                
                distance = feature.geometry().distance(center_feature_geometry)
                if distance <= max_distance:
                    distances_center_to_feature[center_feature_id] = {feature.id(): distance}
        
        log("Расстояния расчитаны.")
        
        # Calculate probabilities.
        #
        layer_centers.startEditing()
        layer.startEditing()
        log("Начало редактирования слоёв.")
        
        diagram_field_index = layer.fields().indexFromName(diagram_field_name)
        weight_field_index = layer_centers.fields().indexFromName(weight_field_name)
        
        for feature in layer.getFeatures():
            transition_and_probabilities = []
            feature_id = feature.id()
            
            interaction_volume_dict = {}
            for center_feature in layer_centers.getFeatures():                
                center_feature_id = center_feature.id()

                distance = distances_center_to_feature.get(center_feature_id, {}).get(feature_id)
                if distance == None:
                    continue
                
                interaction_volume = float(center_feature[layer_centers_field]) ** alpha / distance ** beta
                interaction_volume_dict[center_feature_id] = interaction_volume

            total_interaction_volume = sum(interaction_volume_dict.values())
            if total_interaction_volume == 0:
                continue

            # Calculate probabilities and weights.
            #
            layer_field_value = float(feature[layer_field])
            
            for center_feature in layer_centers.getFeatures():
                
                interaction_volume = interaction_volume_dict.get(center_feature.id())
                if interaction_volume == None:
                    continue
                
                probability_f_to_center_f = interaction_volume / total_interaction_volume
                weight = round(probability_f_to_center_f * layer_field_value, 2)
                
                # EDITING LAYER
                #
                center_feature.setAttribute(weight_field_index, weight)
                layer_centers.updateFeature(center_feature)
                
                # Diagram data
                #
                transition_and_probabilities.append({"feature_id": center_feature.id(), "probability": probability_f_to_center_f})
            
            diagram_data = json.dumps(transition_and_probabilities)
            # feature[diagram_field_name] = diagram_data
            
            feature.setAttribute(diagram_field_index, diagram_data)
            layer.updateFeature(feature)
            layer.commitChanges()
            layer.reload() 
            
        layer.commitChanges()
        layer_centers.commitChanges()
        
        for feature in layer.getFeatures():
            attribute_value = feature.attribute(diagram_field_index)
            logmedaddy(attribute_value)
        
        log("Конец выполнения.")
        return True

    def finished(self, success):
        if not success:
            QgsMessageLog.logMessage('GravityModelTask finished with exceptions.', 'LightModelsLog', level=Qgis.Info)
