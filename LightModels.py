from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt, QVariant, QThread
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtWidgets import QAction, QApplication
from .resources import *
from .LightModels_dockwidget import ModelsDockWidget
from .my_plugin_dialog import MyPluginDialog
from .gravity_dialog import GravityDialog
import os.path
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal
from qgis.core import *
from qgis.core import QgsField, QgsMapLayer, QgsWkbTypes, QgsProject, QgsVectorLayer, QgsLayerTreeLayer, QgsGeometry, QgsPoint, QgsFeature
from qgis.core import QgsAggregateCalculator, QgsSymbol, QgsSpatialIndex, QgsRendererCategory, QgsSingleSymbolRenderer
from qgis.core import QgsLayerTreeGroup, QgsGraduatedSymbolRenderer, QgsMarkerSymbol, QgsFeatureRequest, QgsCategorizedSymbolRenderer
from qgis.core import QgsTask, QgsApplication
from qgis.gui import QgsMapToolIdentifyFeature, QgsMapToolIdentify
from qgis.gui import QgsMapToolEmitPoint
from qgis.utils import iface
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
import time
import uuid
from _struct import *
from qgis.utils import iface
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QWidget, QHBoxLayout
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QCursor
from qgis.gui import QgsMapTool, QgsMapMouseEvent
from multiprocessing import Pool


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

    def run(self):
        self.is_running = True
        self.progress.emit(0) # reset progressbar

        layer, layer_centers, layer_field, layer_centers_field, alpha, beta, max_distance_thershold = self.get_form_data()
        # main payload
        self.run_gravity_model(layer, layer_centers, layer_field, layer_centers_field, alpha, beta, max_distance_thershold)
        #!!! Break down run_gravity_model into small steps and loops. Better calcelation.

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
        alpha = float(self.dlg_model.textEdit_significance_power.text())
        beta = float(self.dlg_model.textEdit_distance_power.text())
        max_distance_thershold = float(self.dlg_model.textEdit_max_distance_thershold.text())
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
        
    def request_cancelation(self):
        self.requestInterruption()

    def run(self):
        self.is_running = True
        # получаем данные из формы
        layer, attr, multiplier, stop = self.get_form_data()
        
        start_time = time.time()
        print('jj')
        
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
        print('b')
        group = QgsLayerTreeGroup('Модель центральных мест')

        centers = list(layer.getFeatures(QgsFeatureRequest().setFilterExpression('@id = "to"')))
        print('b2')
        
        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(process_center, center) for center in centers]
        print('b3')
        
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
        print('b4')
        
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
        print('aaa')
        # добавляем слои в проект
        QgsProject.instance().addMapLayer(point_layer, False)
        QgsProject.instance().addMapLayer(line_layer, False)

        # создаем слой центров
        centers_layer = QgsVectorLayer("Point?crs=" + layer.crs().authid(), "центры", "memory")
        prov = centers_layer.dataProvider()
        prov.addAttributes(layer.fields())
        centers_layer.updateFields()
        prov.addFeatures(centers)
        print('aaa2')
        # задание стиля слою центров
        symbol = QgsMarkerSymbol.createSimple({'name': 'circle', 'color': 'orange'})
        symbol.setSize(5)
        renderer = QgsSingleSymbolRenderer(symbol)
        centers_layer.setRenderer(renderer)
        centers_layer.triggerRepaint()

        QgsProject.instance().addMapLayer(centers_layer, False)
        print('aaa3')
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
        print('aaa4')
        # создание стиля на основе уникальных значений атрибута для линий
        renderer = QgsCategorizedSymbolRenderer('center')
        unique_values = line_layer.uniqueValues(line_layer.fields().indexOf('center'))
        for value in unique_values:
            symbol = QgsSymbol.defaultSymbol(line_layer.geometryType())
            category = QgsRendererCategory(value, symbol, str(value))
            renderer.addCategory(category)
        print('aaa5')
        # срименение стиля к слою линий
        line_layer.setRenderer(renderer)
        line_layer.triggerRepaint()
        
        # добавлям слои в группу
        group.insertChildNode(0, QgsLayerTreeLayer(centers_layer))
        group.insertChildNode(group.children().__len__(), QgsLayerTreeLayer(point_layer))
        group.insertChildNode(group.children().__len__(), QgsLayerTreeLayer(line_layer))
        print('aaaa')
        # добавляем созданную группу в проект
        root = QgsProject.instance().layerTreeRoot()
        root.insertChildNode(0, group)

    def get_form_data(self):
        layer = self.dlg_model.comboBox_feature_layer.itemData(self.dlg_model.comboBox_feature_layer.currentIndex())
        field = self.dlg_model.comboBox_significance_attr.currentText()
        multiplier = float(self.dlg_model.textEdit_significance_power.text())
        stop = float(self.dlg_model.textEdit_distance_power.text())
        return layer, field, multiplier, stop

# реализация плагина
class Models:                 #!!! stop() —> finished.emit() —> on_thread_finished() —> close() —> on_close_dialog() —> kill() —> stop(😑)
    def __init__(self, iface):
        self.iface = iface

        self.plugin_dir = os.path.dirname(__file__)

        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'Models_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&LightModels')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'Models')
        self.toolbar.setObjectName(u'Models')
        
        # QThread attributes
        self.thread = None
        self.worker = None

        self.pluginIsActive = False
        self.dockwidget = None
        
        self.active_layer = None


    def tr(self, message):
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('Models', message)


    def add_action(
            self,
            icon_path,
            text,
            callback,
            enabled_flag=True,
            add_to_menu=True,
            add_to_toolbar=True,
            status_tip=None,
            whats_this=None,
            parent=None):
        
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)
        if status_tip is not None:
            action.setStatusTip(status_tip)
        if whats_this is not None:
            action.setWhatsThis(whats_this)
        if add_to_toolbar:
            self.toolbar.addAction(action)
        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)
        self.actions.append(action)
        return action


    def initGui(self):
        icon_path = ':/plugins/LightModels/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'LightModels'),
            callback=self.run,
            parent=self.iface.mainWindow())
    
    # ______________________________________________________________________________________________
        
    # закрытие плагина
    def on_close_plugin(self):
        self.dockwidget.closingPlugin.disconnect(self.on_close_plugin)
        self.dockwidget.model_comboBox.clear()
        self.dockwidget.ok_button.clicked.disconnect(self.run_model_dialog)
        self.active_layer.selectionChanged.disconnect(self.process_selected_features_ids)
        self.pluginIsActive = False
        print("Plugin close")


    def report_progress(self, n): #? Move to worker class?
        self.dlg_model.progress_bar.setValue(n) # set the current progress in progress bar
        
    # удаление меню плагина и иконки с qgis интерфейса
    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&LightModels'),
                action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar


    def start_gravity_model_worker(self):
        self.thread = QThread()
        self.worker = GravityModelWorker(dlg_model=self.dlg_model)
        
        self.worker.moveToThread(self.thread) # move Worker-Class to a thread
        # Connect signals and slots:
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.report_progress)
        self.worker.finished.connect(self.on_thread_finished)
        self.worker.finished.connect(self.thread.quit)
        self.dlg_model.cancel_button.clicked.connect(self.request_worker_cancelation) # cancel execution
        
        self.dlg_model.ok_button.setEnabled(False) # disable the OK button while thread is running
        self.dlg_model.cancel_button.clicked.connect(lambda: self.dlg_model.ok_button.setEnabled(True)) # enable the OK button when cancel button clicked
        self.thread.start()


    def start_centers_model_worker(self):
        self.thread = QThread()
        self.worker = CentersModelWorker(dlg_model=self.dlg_model)
        
        self.worker.moveToThread(self.thread) # move Worker-Class to a thread
        # Connect signals and slots:
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.report_progress)
        self.worker.finished.connect(self.on_thread_finished)
        self.worker.finished.connect(self.thread.quit)
        self.dlg_model.cancel_button.clicked.connect(self.worker.request_cancelation) # cancel execution

        self.dlg_model.ok_button.setEnabled(False)
        self.dlg_model.cancel_button.clicked.connect(lambda: self.dlg_model.ok_button.setEnabled(True)) # enable the OK button when cancel button clicked
        self.thread.start()


    def kill_current_model_worker(self):
        if self.worker != None:
            self.worker.stop()                   
        
        if self.thread != None:
            if self.thread.isRunning():
                self.thread.quit()
        
            self.thread.started.disconnect(self.worker.run)
            self.worker.progress.disconnect(self.report_progress)
            self.worker.finished.disconnect(self.on_thread_finished)
            self.worker.finished.disconnect(self.thread.quit)
            self.dlg_model.cancel_button.clicked.disconnect(self.request_worker_cancelation)
        
        
    def request_worker_cancelation(self):
        self.worker.is_calcelation_requested = True
        
        
    def on_thread_finished(self):
        self.dlg_model.close()


    def process_selected_features_ids(self, selected_features_ids, result2, result3):
        
        def print_population(feature_id):
            for feature in self.active_layer.getFeatures():
                if feature.id() == feature_id:
                    print("Feature population:", feature['POPULATION'])
                    
        self.active_layer = self.iface.activeLayer() #? Is in place? active_layer.selectionChanged referes to feature selection or layer selection?
        if len(selected_features_ids) == 1:
            print_population(selected_features_ids[0])
    
    # ______________________________________________________________________________________________
            
    # работа плагина
    def run(self):
        # инициализация базового окна
        if not self.pluginIsActive:
            self.pluginIsActive = True
            if self.dockwidget == None:
                self.dockwidget = ModelsDockWidget()
            self.dockwidget.closingPlugin.connect(self.on_close_plugin)
            self.dockwidget.dockWidgetContents.setEnabled(True)
            self.iface.addDockWidget(Qt.TopDockWidgetArea, self.dockwidget)
            self.dockwidget.show()
            
            for model_name in ['Гравитационная модель', 'Модель центральных мест', 'Модель 3']:
                self.dockwidget.model_comboBox.addItem(model_name)
                
            self.dockwidget.ok_button.clicked.connect(self.run_model_dialog)
            
            # Feature selection
            self.active_layer = self.iface.activeLayer()
            if self.active_layer:
                self.active_layer.selectionChanged.connect(self.process_selected_features_ids)
            
            self.iface.actionSelect().trigger()
            self.iface.mapCanvas().setSelectionColor(QColor("light blue"))
        

    def on_layer_combobox_changed_do_show_layer_attrs(self, layer_cmb, attrs_cmb):
        layer = layer_cmb.itemData(layer_cmb.currentIndex())
        attributes = [field.name() for field in layer.fields()]
        attrs_cmb.clear()
        attrs_cmb.addItems(attributes)
    

    def on_close_model_dialog(self):
        if self.worker.is_running != None and self.worker.is_running:
            self.kill_current_model_worker()
        self.dockwidget.close()


    def run_model_dialog(self):
        model = self.dockwidget.model_comboBox.currentText()
        self.dockwidget.hide()
        self.dlg_model = None

        if model == "Модель центральных мест":
            self.dlg_model = MyPluginDialog()
            for layer in iface.mapCanvas().layers():
                isLayerValid = (layer.type() == QgsMapLayer.VectorLayer and layer.geometryType() == QgsWkbTypes.PointGeometry)
                if (isLayerValid):
                    self.dlg_model.comboBox_feature_layer.addItem(layer.name(), layer)
            self.dlg_model.comboBox_feature_layer.setCurrentIndex(-1)
            self.dlg_model.comboBox_feature_layer.currentIndexChanged.connect(lambda: self.on_layer_combobox_changed_do_show_layer_attrs(self.dlg_model.comboBox_feature_layer, self.dlg_model.comboBox_significance_attr))
        
        elif model == "Гравитационная модель":
            self.dlg_model = GravityDialog()
            for layer in iface.mapCanvas().layers():
                isLayerValid = (layer.type() == QgsMapLayer.VectorLayer and layer.geometryType() == QgsWkbTypes.PointGeometry)
                if (isLayerValid):
                    self.dlg_model.comboBox_feature_layer.addItem(layer.name(), layer)
                    self.dlg_model.comboBox_feature_layer_2.addItem(layer.name(), layer)
            self.dlg_model.comboBox_feature_layer.setCurrentIndex(-1)
            self.dlg_model.comboBox_feature_layer_2.setCurrentIndex(-1)
            self.dlg_model.comboBox_feature_layer.currentIndexChanged.connect(lambda: self.on_layer_combobox_changed_do_show_layer_attrs(self.dlg_model.comboBox_feature_layer, self.dlg_model.comboBox_significance_attr))
            self.dlg_model.comboBox_feature_layer_2.currentIndexChanged.connect(lambda: self.on_layer_combobox_changed_do_show_layer_attrs(self.dlg_model.comboBox_feature_layer_2, self.dlg_model.comboBox_significance_attr_2))

        if not self.dlg_model is None:
            self.dlg_model.closingDialog.connect(self.on_close_model_dialog)
            self.dlg_model.ok_button.clicked.connect(self.run_model)
            self.dlg_model.show()
        else:
            self.dockwidget.close()


    def run_model(self):
        model = self.dockwidget.model_comboBox.currentText()
        if model == "Гравитационная модель":
            self.start_gravity_model_worker()
        elif model == "Модель центральных мест":
            self.start_centers_model_worker()

