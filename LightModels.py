from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt, QVariant, QThread
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
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
from qgis.utils import iface
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
import time

class GravityModelWorker(QThread):
    finished = pyqtSignal() # pyqtSignal for when task is finished
    progress = pyqtSignal(int) # pyqtSignal to report the progress to progressbar

    def __init__(self, dlg_model):
        super(QThread, self).__init__()
        self.stopworker = False

        self.dlg_model = dlg_model
            
    def stop(self):
        self.stopworker = True
        self.dlg_model.close()
        
    def run(self):
        self.progress.emit(0) # reset progressbar
        print('grav model run')

        #     self.progress.emit(int((i+1)/self.total*100)) # report the current progress via pyqt signal to reportProgress method of TaskTest-Class
        #     if self.stopworker == True: # if cancel button has been pressed the stop method is called and stopworker set to True. If so, break the loop so the thread can be stopped
        #         print('break req')
        #         break

        # получение данных из формы
        layer_attr = self.dlg_model.comboBox_significance_attr.currentText()
        layer_tc_attr = self.dlg_model.comboBox_significance_attr_2.currentText()
        alpha = float(self.dlg_model.textEdit_significance_power.text())
        beta = float(self.dlg_model.textEdit_distance_power.text())
        layer = self.dlg_model.comboBox_feature_layer.itemData(self.dlg_model.comboBox_feature_layer.currentIndex())
        layer_tc = self.dlg_model.comboBox_feature_layer_2.itemData(self.dlg_model.comboBox_feature_layer_2.currentIndex())

        # создаем точечный слой
        point_layer = QgsVectorLayer("Point?crs=" + layer_tc.crs().authid(), f'{layer_tc.name()}', "memory")
        point_data = point_layer.dataProvider()
        point_data.addAttributes(layer_tc.fields())
        point_data.addFeatures(layer_tc.getFeatures())
        point_layer.updateFields()
        QgsProject.instance().addMapLayer(point_layer, False)
        layer_tc = point_layer

        # создаем группу и помещаем туда слой
        group = QgsLayerTreeGroup('Гравитационная модель')
        group.insertChildNode(0, QgsLayerTreeLayer(layer_tc))

        # в слое потребителей создаем поля для записи информации о том, сколько людей пойдет к конкретному поставщику 
        new_attrs = []
        for i in range(layer_tc.featureCount()):
            if layer.fields().indexFromName(f'tc_{i}') == -1: 
                new_attrs.append(QgsField(f'tc_{i}', QVariant.Double))

        if new_attrs:
            layer.dataProvider().addAttributes(new_attrs)
            layer.updateFields()

        # добавляем поле 'weight'
        if layer_tc.fields().indexFromName('weight') == -1: 
            layer_tc.dataProvider().addAttributes([QgsField('weight', QVariant.Double)])
            layer_tc.updateFields()

        # task = GravityModelTask(layer, layer_tc, layer_attr, layer_tc_attr, alpha, beta)
        # QgsApplication.taskManager().addTask(task)
        # task.waitForFinished()

        # для каждой точки делаем рассчет по формуле и записываем результат в слой в соответствующие поля
        layer.startEditing()        
        for f in list(layer.getFeatures()):
            h_list = []
            for tc in layer_tc.getFeatures():
                h = float(tc[layer_tc_attr])**alpha / f.geometry().distance(tc.geometry())**beta
                h_list.append(h)

            total_h = sum(h_list)
            vers = [round(h / total_h, 2) for h in h_list]
            for i in range(len(vers)):
                f[f'tc_{i}'] = round(vers[i] * float(f[layer_attr]), 2)
            layer.updateFeature(f)

        layer.commitChanges()

        # на основе предыдущих рассчетов считаем вес для каждого поставщика
        layer_tc.startEditing()
        for tc in layer_tc.getFeatures():
            result = layer.aggregate(QgsAggregateCalculator.Sum, f'tc_{tc.id() - 1}')[0] # в исходном tc нумерация id от 0, а в новом от 1
            tc['weight'] = int(result)
            layer_tc.updateFeature(tc)

        layer_tc.commitChanges()

        # задание стиля для слоя поставщиков
        graduated_size = QgsGraduatedSymbolRenderer('weight')
        graduated_size.updateClasses(layer_tc, QgsGraduatedSymbolRenderer.EqualInterval, layer_tc.featureCount())
        graduated_size.setGraduatedMethod(QgsGraduatedSymbolRenderer.GraduatedSize)
        graduated_size.setSymbolSizes(4, 10)
        graduated_size.updateRangeLabels()
        layer_tc.setRenderer(graduated_size)
        layer_tc.triggerRepaint()

        # добавляем созданную группу в проект
        root = QgsProject.instance().layerTreeRoot()
        root.insertChildNode(0, group)
        
        self.finished = True
        
       
class CentersModelWorker(QThread):
    finished = pyqtSignal()
    progress = pyqtSignal(int)

    def __init__(self, dlg_model):
        super(QThread, self).__init__()
        self.stopworker = False

        self.dlg_model = dlg_model
        
    def stop(self):
        self.stopworker = True
        self.dlg_model.close()
        
    def run(self):
        # получаем данные из формы
        start_time = time.time()
        layer = self.dlg_model.comboBox_feature_layer.itemData(self.dlg_model.comboBox_feature_layer.currentIndex())
        attr = self.dlg_model.comboBox_significance_attr.currentText()
        multiplier = float(self.dlg_model.textEdit_significance_power.text())
        stop = float(self.dlg_model.textEdit_distance_power.text())

        # добавляем колонку "to", если ее нет
        if layer.fields().indexFromName('to') == -1: 
            layer.dataProvider().addAttributes([QgsField('to', QVariant.Int)])
            layer.updateFields()

        # возвращает id точки для соединения
        def process_feature(f):
            f_id = f.id()
            population = int(f[attr])
            if population > stop:
                return f_id
            else:
                c = population * multiplier
                ps = list(layer.getFeatures(QgsFeatureRequest().setFilterExpression(f'{attr} > {c}')))
                index = QgsSpatialIndex(layer.getFeatures(QgsFeatureRequest().setFilterExpression(f'{attr} > {c}')))
                if not ps:
                    return f_id
                else:
                    nearest_point_id = index.nearestNeighbor(f.geometry().asPoint(), 1)[0]
                    return nearest_point_id
        
        # выполнение process_feature для каждой точки слоя в режиме многопоточности
        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(process_feature, f) for f in list(layer.getFeatures())]

        # запись в колонку 'to' каждой точки - id точки для соединения
        layer.startEditing()
        features = list(layer.getFeatures())
        for i in range(len(futures)):
            result = futures[i].result()
            features[i]['to'] = result
            layer.updateFeature(features[i])
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

        end_time = time.time()
        execution_time = end_time - start_time
        print(execution_time)

        self.dlg_model.close()
        
        self.finished = True


# реализация плагина
class Models:
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

        # print "** INITIALIZING Models"

        self.pluginIsActive = False
        self.dockwidget = None


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
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        icon_path = ':/plugins/LightModels/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'LightModels'),
            callback=self.run,
            parent=self.iface.mainWindow())

    # --------------------------------------------------------------------------

    # закрытие плагина
    def on_close_plugin(self):
        self.dockwidget.closingPlugin.disconnect(self.on_close_plugin)
        self.dockwidget.model_comboBox.clear()
        # self.dockwidget.message_label.clear()
        # self.dockwidget.ok_button.setEnabled(True)
        self.pluginIsActive = False
        self.dockwidget.ok_button.clicked.disconnect(self.run_model_dialog)     
        print("plugin close")

    def report_progress(self, n):
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
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.progress.connect(self.report_progress)
        self.thread.start()
        self.dockwidget.ok_button.setEnabled(False) # disable the OK button while thread is running
        self.thread.finished.connect(lambda: self.dockwidget.ok_button.setEnabled(True))


    def start_centers_model_worker(self):
        self.thread = QThread()
        self.worker = CentersModelWorker(dlg_model=self.dlg_model)
        
        self.worker.moveToThread(self.thread) # move Worker-Class to a thread
        # Connect signals and slots:
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()
        # disable / enable buttons
        self.dockwidget.ok_button.setEnabled(False)
        self.thread.finished.connect(lambda: self.dockwidget.ok_button.setEnabled(True))


    def kill_current_model_worker(self):
        self.worker.stop()
        
        try: # to prevent a Python error when the cancel button has been clicked but no thread is running use try/except
            if self.thread.isRunning():
                self.thread.quit()
        except:
            pass
        

    # --------------------------------------------------------------------------


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
            

    def on_layer_combobox_changed_do_show_layer_attrs(self, layer_cmb, attrs_cmb):
        layer = layer_cmb.itemData(layer_cmb.currentIndex())
        attributes = [field.name() for field in layer.fields()]
        attrs_cmb.clear()
        attrs_cmb.addItems(attributes)
    

    def on_close_model_dialog(self):
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


    def run_gravity_model(self):
        # получение данных из формы
        layer_attr = self.dlg_model.comboBox_significance_attr.currentText()
        layer_tc_attr = self.dlg_model.comboBox_significance_attr_2.currentText()
        alpha = float(self.dlg_model.textEdit_significance_power.text())
        beta = float(self.dlg_model.textEdit_distance_power.text())
        layer = self.dlg_model.comboBox_feature_layer.itemData(self.dlg_model.comboBox_feature_layer.currentIndex())
        layer_tc = self.dlg_model.comboBox_feature_layer_2.itemData(self.dlg_model.comboBox_feature_layer_2.currentIndex())

        # создаем точечный слой
        point_layer = QgsVectorLayer("Point?crs=" + layer_tc.crs().authid(), f'{layer_tc.name()}', "memory")
        point_data = point_layer.dataProvider()
        point_data.addAttributes(layer_tc.fields())
        point_data.addFeatures(layer_tc.getFeatures())
        point_layer.updateFields()
        QgsProject.instance().addMapLayer(point_layer, False)
        layer_tc = point_layer

        # создаем группу и помещаем туда слой
        group = QgsLayerTreeGroup('Гравитационная модель')
        group.insertChildNode(0, QgsLayerTreeLayer(layer_tc))

        # в слое потребителей создаем поля для записи информации о том, сколько людей пойдет к конкретному поставщику 
        new_attrs = []
        for i in range(layer_tc.featureCount()):
            if layer.fields().indexFromName(f'tc_{i}') == -1: 
                new_attrs.append(QgsField(f'tc_{i}', QVariant.Double))
                
        if new_attrs:
            layer.dataProvider().addAttributes(new_attrs)
            layer.updateFields()

        # добавляем поле 'weight'
        if layer_tc.fields().indexFromName('weight') == -1: 
            layer_tc.dataProvider().addAttributes([QgsField('weight', QVariant.Double)])
            layer_tc.updateFields()
            
        task = GravityModelTask(layer, layer_tc, layer_attr, layer_tc_attr, alpha, beta)
        QgsApplication.taskManager().addTask(task)
        task.waitForFinished()

        # задание стиля для слоя поставщиков
        graduated_size = QgsGraduatedSymbolRenderer('weight')
        graduated_size.updateClasses(layer_tc, QgsGraduatedSymbolRenderer.EqualInterval, layer_tc.featureCount())
        graduated_size.setGraduatedMethod(QgsGraduatedSymbolRenderer.GraduatedSize)
        graduated_size.setSymbolSizes(4, 10)
        graduated_size.updateRangeLabels()
        layer_tc.setRenderer(graduated_size)
        layer_tc.triggerRepaint()

        # добавляем созданную группу в проект
        root = QgsProject().instance().layerTreeRoot()
        root.insertChildNode(0, group)

        self.dlg_model.close()


    def run_centers_model(self):
        # получаем данные из формы
        start_time = time.time()
        layer = self.dlg_model.comboBox_feature_layer.itemData(self.dlg_model.comboBox_feature_layer.currentIndex())
        attr = self.dlg_model.comboBox_significance_attr.currentText()
        multiplier = float(self.dlg_model.textEdit_significance_power.text())
        stop = float(self.dlg_model.textEdit_distance_power.text())

        # добавляем колонку "to", если ее нет
        if layer.fields().indexFromName('to') == -1: 
            layer.dataProvider().addAttributes([QgsField('to', QVariant.Int)])
            layer.updateFields()

        # возвращает id точки для соединения
        def process_feature(f):
            f_id = f.id()
            population = int(f[attr])
            if population > stop:
                return f_id
            else:
                c = population * multiplier
                ps = list(layer.getFeatures(QgsFeatureRequest().setFilterExpression(f'{attr} > {c}')))
                index = QgsSpatialIndex(layer.getFeatures(QgsFeatureRequest().setFilterExpression(f'{attr} > {c}')))
                if not ps:
                    return f_id
                else:
                    nearest_point_id = index.nearestNeighbor(f.geometry().asPoint(), 1)[0]
                    return nearest_point_id
        
        # выполнение process_feature для каждой точки слоя в режиме многопоточности
        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(process_feature, f) for f in list(layer.getFeatures())]

        # запись в колонку 'to' каждой точки - id точки для соединения
        layer.startEditing()
        features = list(layer.getFeatures())
        for i in range(len(futures)):
            result = futures[i].result()
            features[i]['to'] = result
            layer.updateFeature(features[i])
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
        root = QgsProject().instance().layerTreeRoot()
        root.insertChildNode(0, group)

        end_time = time.time()
        execution_time = end_time - start_time
        print(execution_time)

        self.dlg_model.close()
 
        
class GravityModelTask(QgsTask):
    def __init__(self, layer, layer_tc, layer_attr, layer_tc_attr, alpha, beta, parent=None):
        super().__init__("Gravity Model Task")
        self.parent = parent
        self.layer = layer
        self.layer_tc = layer_tc
        self.layer_attr = layer_attr
        self.layer_tc_attr = layer_tc_attr
        self.alpha = alpha
        self.beta = beta
        
    def run(self):
        # для каждой точки делаем рассчет по формуле и записываем результат в слой в соответствующие поля
        self.layer.startEditing()        
        for f in list(self.layer.getFeatures()):
            h_list = []
            for tc in self.layer_tc.getFeatures():
                h = float(tc[self.layer_tc_attr])**self.alpha / f.geometry().distance(tc.geometry())**self.beta
                h_list.append(h)
                
            total_h = sum(h_list)
            vers = [round(h / total_h, 2) for h in h_list]
            for i in range(len(vers)):
                f[f'tc_{i}'] = round(vers[i] * float(f[self.layer_attr]), 2)
            self.layer.updateFeature(f)
            
        self.layer.commitChanges()
        
        # на основе предыдущих рассчетов считаем вес для каждого поставщика
        self.layer_tc.startEditing()
        for tc in self.layer_tc.getFeatures():
            result = self.layer.aggregate(QgsAggregateCalculator.Sum, f'tc_{tc.id() - 1}')[0] # в исходном tc нумерация id от 0, а в новом от 1
            tc['weight'] = int(result)
            self.layer_tc.updateFeature(tc)
            
        self.layer_tc.commitChanges()


class CentersModelTask(QgsTask):
    def __init__(self, parent=None):
        super().__init__("Centers Model Task")
        self.parent = parent

    def run(self):
        # Perform heavy work for the centers model here
        # Example heavy work:
        for i in range(100):
            # Simulate heavy work progress
            QgsApplication.processEvents()
            if self.isCanceled():
                return False
            # Your heavy work code goes here
        return True