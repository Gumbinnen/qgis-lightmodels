from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import numpy as np
import os, time, math, csv, itertools, shutil

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QFileDialog
from qgis.core import *
from qgis.utils import iface
from gui import QgisInterface
from concurrent.futures import ThreadPoolExecutor

from .resources import *
from .models.gravity_model.gravity_model import GravityModel
from .my_plugin_dialog import MyPluginDialog
from .gravity_dialog import GravityDialog


class LightModel:
    def __init__(self, iface: QgisInterface):
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
        self.toolbar = self.iface.addToolBar(u'LightModels')
        self.toolbar.setObjectName(u'LightModels')

        # print "** INITIALIZING Models"

        self.pluginIsActive = False
        self.dockwidget = None
        self.diagram_layer = None

        QgsProject.instance().layerRemoved.connect(self.on_layer_removed)


    def on_layer_removed(self, removed_layer_id):
        files = os.listdir(self.plugin_dir + '/gm_data')
        for file in files:
            if removed_layer_id in file:
                if removed_layer_id == file[:-4].split('&')[1]:
                    layer = QgsProject.instance().mapLayer(file.split('&')[0])
                    layer.selectionChanged.disconnect(self.on_selection_changed)
                os.remove(self.plugin_dir + '/gm_data/' + file)


    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('LightModels', message)


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
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """
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
        icons_dir = os.path.join(self.plugin_dir, 'res', 'icons')
        self.add_action(
            icon_path=os.path.join(icons_dir, 'gravity_model_icon.png'),
            text=self.tr(u'Гравитационная модель'),
            callback=self.run_gravity_dialog,
            parent=self.iface.mainWindow())
        self.add_action(
            icon_path=os.path.join(icons_dir, 'center_places_model_icon.png'),
            text=self.tr(u'Модель центральных мест'),
            callback=self.run_centers_dialog,
            parent=self.iface.mainWindow())
        self.add_action(
            icon_path=os.path.join(icons_dir, 'regression_model_icon.png'),
            text=self.tr(u'Регрессионная модель'),
            callback=self.run_centers_dialog,
            parent=self.iface.mainWindow())

    # --------------------------------------------------------------------------

    # закрытие плагина
    def onClosePlugin(self):
        self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)
        self.dockwidget.model_comboBox.clear()
        self.pluginIsActive = False
        self.dockwidget.ok_button.clicked.disconnect(self.run_model_dialog)     
        print("plugin close")


    # удаление меню плагина и иконки с qgis интерфейса
    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&LightModels'),
                action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar

    # --------------------------------------------------------------------------
    """Гравитационная модель"""

    def onCloseGravityDialog(self):
        self.stop_diagrams()


    def on_export_click(self):
        self.show_export_dialog()


    def show_export_dialog(self):
        folder = self.get_export_folder()
        if folder:
            self.export_file(folder)


    def get_export_folder(self):
        folder = QFileDialog.getExistingDirectory(iface.mainWindow(), "Выберите папку экспорта", "", QFileDialog.ShowDirsOnly)
        return folder
    
    
    def export_file(self, folder):
        layer = self.diagram_layer
        files = os.listdir(self.plugin_dir + '/gm_data')
        if layer:
            for file in files:
                if layer.id() == file.split('&')[0]:
                    layer_tc = QgsProject.instance().mapLayer(file.split('&')[1][:-4])
                    break

        file_name = f'{layer.id()}&{layer_tc.id()}.csv'
        
        source_file_path = os.path.join(self.plugin_dir, 'gm_data', file_name)

        destination_file_path = os.path.join(folder, file_name)

        try:
            shutil.copy(source_file_path, destination_file_path)
            print("File copied successfully.")
        except Exception as e:
            print("Error occurred while copying file:", str(e))
    
    
    def run_gravity_dialog(self):
        self.dlg_model = GravityDialog()
        for layer in iface.mapCanvas().layers():
            if (layer.type() == QgsMapLayer.VectorLayer and layer.geometryType() == QgsWkbTypes.PointGeometry):
                self.dlg_model.comboBox_feature_layer.addItem(layer.name(), layer)
                self.dlg_model.comboBox_feature_layer_2.addItem(layer.name(), layer)
        self.dlg_model.comboBox_feature_layer.setCurrentIndex(-1)
        self.dlg_model.comboBox_feature_layer_2.setCurrentIndex(-1)
        
        self.dlg_model.comboBox_feature_layer.currentIndexChanged.connect(lambda: self.on_layer_combobox_changed(self.dlg_model.comboBox_feature_layer, self.dlg_model.comboBox_significance_attr))
        self.dlg_model.comboBox_feature_layer_2.currentIndexChanged.connect(lambda: self.on_layer_combobox_changed(self.dlg_model.comboBox_feature_layer_2, self.dlg_model.comboBox_significance_attr_2))
        
        self.dlg_model.tabWidget.currentChanged.connect(self.on_change_tab)
        self.dlg_model.closingDialog.connect(self.onCloseGravityDialog)
        self.dlg_model.ok_button.clicked.connect(self.run_gravity_model)
        self.dlg_model.export_button.clicked.connect(self.on_export_click)
        
        self.dlg_model.show()


    def run_gravity_model(self):
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

        # получение данных из формы
        layer_attr = self.dlg_model.comboBox_significance_attr.currentText()
        layer_tc_attr = self.dlg_model.comboBox_significance_attr_2.currentText()
        # alpha = float(self.dlg_model.textEdit_significance_power.text())
        # beta = float(self.dlg_model.textEdit_distance_power.text())
        alpha = float(self.dlg_model.doubleSpinBox.value())
        beta = float(self.dlg_model.doubleSpinBox_2.value())
        layer = self.dlg_model.comboBox_feature_layer.itemData(self.dlg_model.comboBox_feature_layer.currentIndex())
        layer_tc = self.dlg_model.comboBox_feature_layer_2.itemData(self.dlg_model.comboBox_feature_layer_2.currentIndex())
        # max_distance = float(self.dlg_model.textEdit_max_distance.text())
        max_distance = int(self.dlg_model.spinBox.value())

        # создаем точечный слой поставщиков
        point_layer = QgsVectorLayer("Point?crs=" + layer_tc.crs().authid(), f'{layer_tc.name()} [g. m.]', "memory")
        point_data = point_layer.dataProvider()
        point_data.addAttributes(layer_tc.fields())
        point_data.addFeatures(layer_tc.getFeatures())
        point_layer.updateFields()
        QgsProject.instance().addMapLayer(point_layer, False)
        layer_tc = point_layer

        # создаем точечный слой потребителей
        point_layer = QgsVectorLayer("Point?crs=" + layer.crs().authid(), f'{layer.name()} [g. m.]', "memory")
        point_data = point_layer.dataProvider()
        point_data.addAttributes(layer.fields())
        point_data.addFeatures(layer.getFeatures())
        point_layer.updateFields()
        QgsProject.instance().addMapLayer(point_layer, False)
        layer = point_layer

        # создаем линейный слой зоны влияния центра
        line_layer = QgsVectorLayer('LineString?crs=' + layer.crs().authid(), 'линии [g. m.]', 'memory')
        line_data = line_layer.dataProvider()
        line_data.addAttributes([QgsField('f_id', QVariant.Int), QgsField('tc_id', QVariant.Int)])
        line_layer.updateFields()

        # создаем группу и помещаем туда слои
        group = QgsLayerTreeGroup('Гравитационная модель')
        group.insertChildNode(0, QgsLayerTreeLayer(layer))
        group.insertChildNode(0, QgsLayerTreeLayer(layer_tc))

        # добавляем поле 'weight'
        if layer_tc.fields().indexFromName('weight [g. m.]') == -1: 
            layer_tc.dataProvider().addAttributes([QgsField('weight [g. m.]', QVariant.Double)])
            layer_tc.updateFields()
        
        # для каждой точки делаем рассчет по формуле и записываем результат в слой в соответствующие поля
        headers = ['f']
        for tc in layer_tc.getFeatures():
            headers.append(tc.id())
        
        data = []
        for f in list(layer.getFeatures()):
            h_dict = {}
            
            f_geometry = f.geometry()
            f_lat = None
            f_long = None
            
            if f_geometry is not None:
                if f_geometry.type() == QgsWkbTypes.PointGeometry:
                    point = f_geometry.asPoint()
                    f_lat = point.y()
                    f_long = point.x()
            
            if f_lat == None or f_long == None:
                print('Не вышло получить координаты точки.')
                break
            
            f1 = (f_lat, f_long)
            
            for tc in layer_tc.getFeatures():
                tc_geometry = tc.geometry()
                tc_lat = None
                tc_long = None
                
                if tc_geometry is not None:
                    if tc_geometry.type() == QgsWkbTypes.PointGeometry:
                        point = tc_geometry.asPoint()
                        tc_lat = point.y()
                        tc_long = point.x()
                
                f2 = (tc_lat, tc_long)
                
                distance_degrees = f_geometry.distance(tc_geometry)
                distance_meters = calculate_distance_in_meters(f1, f2)

                if distance_meters > max_distance:
                    h_dict[tc.id()] = 0
                else:
                    h_dict[tc.id()] = tc[layer_tc_attr]**alpha / distance_meters**beta
                    
                    line_geom = QgsGeometry.fromPolyline([QgsPoint(f.geometry().asPoint()), QgsPoint(tc.geometry().asPoint())])
                    line_feature = QgsFeature()
                    line_feature.setGeometry(line_geom)
                    line_feature.setAttributes([f.id(), tc.id()])
                    line_data.addFeatures([line_feature])
            total_h = sum(h_dict.values())
            row = [f.id()]
            for tc_id, h in h_dict.items():
                if total_h != 0:
                    row.append(round(h / total_h, 4))
                else:
                    row.append(0)
            data.append(row)

        # добавялем линейный слой в группу
        line_layer.setOpacity(0.5)
        QgsProject.instance().addMapLayer(line_layer, False)
        group.insertChildNode(group.children().__len__(), QgsLayerTreeLayer(line_layer))

        gm_data_path = f'{self.plugin_dir}/gm_data/{layer.id()}&{layer_tc.id()}.csv'
        with open(gm_data_path, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(headers)
            csvwriter.writerows(data)
            
        with open(gm_data_path, 'r') as csvfile:
            csvreader = csv.reader(csvfile)
            data = list(csvreader)

        # Получаем заголовки
        headers = data[0]

        # Проходим по всем столбцам начиная со второго
        layer_tc.startEditing()
        for col_index in range(1, len(headers)):
            tc_id = int(headers[col_index])
            column_sum = sum(float(row[col_index]) for row in data[1:])
            tc = layer_tc.getFeature(tc_id)
            tc['weight [g. m.]'] = int(column_sum)
            layer_tc.updateFeature(tc)
        layer_tc.commitChanges()

        # задание стиля для слоя поставщиков
        graduated_size = QgsGraduatedSymbolRenderer('weight [g. m.]')
        graduated_size.updateClasses(layer_tc, QgsGraduatedSymbolRenderer.EqualInterval, 5)
        graduated_size.setGraduatedMethod(QgsGraduatedSymbolRenderer.GraduatedSize)
        graduated_size.setSymbolSizes(4, 10)
        graduated_size.updateRangeLabels()
        layer_tc.setRenderer(graduated_size)
        layer_tc.triggerRepaint()

        # добавляем созданную группу в проект
        root = QgsProject().instance().layerTreeRoot()
        root.insertChildNode(0, group)

        iface.setActiveLayer(layer)


    def on_layer_combobox_changed(self, layer_cmb, attrs_cmb):
        layer = layer_cmb.itemData(layer_cmb.currentIndex())
        attributes = [field.name() for field in layer.fields()]
        attrs_cmb.clear()
        attrs_cmb.addItems(attributes)
    
    
    def on_change_tab(self):
            if self.dlg_model.tabWidget.currentIndex() == 1:
                self.run_diagrams()
            else:
                self.stop_diagrams()


    def run_diagrams(self):
        self.iface.actionSelect().trigger() # Click on select tool
        self.diagram_label_field = None
        
        self.on_active_layer_changed()
        iface.currentLayerChanged.connect(self.on_active_layer_changed)
        self.dlg_model.comboBox.currentIndexChanged.connect(self.on_diagram_combobox_change)


    def on_diagram_combobox_change(self):
        self.diagram_label_field = self.dlg_model.comboBox.currentText()

    
    def on_active_layer_changed(self):
        if self.diagram_layer != None:
            try:
                self.diagram_layer.selectionChanged.disconnect(self.on_selection_changed)
                self.diagram_layer = None
            except:
                pass

        layer = self.iface.activeLayer()
        found = False
        if layer != None:
            files = os.listdir(self.plugin_dir + '/gm_data')
            for file in files:
                if layer.id() == file.split('&')[0]:
                    found = True
                    layer_tc = QgsProject.instance().mapLayer(file.split('&')[1][:-4])
                    break
        if found:
            self.diagram_layer = layer
            layer.selectionChanged.connect(self.on_selection_changed)
            
            attributes = ['id']
            attributes += [field.name() for field in layer_tc.fields()]
            self.dlg_model.comboBox.clear()
            self.dlg_model.comboBox.addItems(attributes)


    def stop_diagrams(self):
        try:
            self.diagram_layer.selectionChanged.disconnect(self.on_selection_changed)
            self.diagram_layer = None
        except:
            pass
        try:
            iface.currentLayerChanged.disconnect(self.on_active_layer_changed)
        except:
            pass
        try:
            self.dlg_model.comboBox.currentIndexChanged.disconnect(self.on_diagram_combobox_change)
        except:
            pass


    def on_selection_changed(self):
        def log(*messages, note:str='', title:str='', tab:str=None, level=Qgis.Info, sep:str=' ') -> None:
            """Custom log function for Qgis. Combine messages into letter and log.
            
            Example:
                log(myValue, 'Status:', myStatus, note='MyValue:', tab='My Values')
                
                if isGood:
                    log(isGood, note='isGood:', title='InspectorClass:', level=Qgis.Success)
                else:
                    log(isGood, note='isGood:', title='InspectorClass:', level=Qgis.Info)
                    
            Example output:
                INFO MyValue: 200 Status: OK
                SUCCESS InspectorClass: isGood: True

            Args:
                note (str, optional): note will appear before letter. Use for variable name when logging values. Defaults to ''.
                title (str, optional): title will appear first. Use for global information. Defaults to ''.
                tab (str, optional): If not None, QGIS will create separate log tab with given name. Defaults to ''.
                level (Qgis.MessageLevel, optional): level of the message. Common levels: Info, Warning, Critical, Success. Defaults to Qgis.Info.
                sep (str, optional): Default separate character. Defaults to ' '.
            """
            empty = ''
            letter = empty
            for message in messages:
                letter += sep + str(message)
            if title is not empty and note is not empty:
                title += sep
            QgsMessageLog.logMessage(title + note + letter, tag=tab, level=level)

        layer = self.diagram_layer
        files = os.listdir(self.plugin_dir + '/gm_data')
        for file in files:
            if layer.id() == file.split('&')[0]:
                layer_tc = QgsProject.instance().mapLayer(file.split('&')[1][:-4])
                break
            
        if len(list(layer.selectedFeatures())) == 0:
            return            
            
        f_id = list(layer.selectedFeatures())[0].id()
        
        diagram_field = self.diagram_label_field
        gm_data_path = f'{self.plugin_dir}/gm_data/{layer.id()}&{layer_tc.id()}.csv'
        with open(gm_data_path, 'r') as csvfile:
            csvreader = csv.reader(csvfile)
            
            if diagram_field != None and str(diagram_field) != 'id':
                diagram_field = str(diagram_field)
                labels = []
                for tc_id in next(csvreader)[1:]:
                    feature = layer_tc.getFeature(int(tc_id))
                    labels.append(feature[diagram_field])
            else:
                labels = next(csvreader)[1:]
                     
            for row in csvreader:
                if row[0] == str(f_id):
                    values = list(map(float, row[1:]))
                    break
            # label: 
            # label => feature[field] == value
            # example:
            # 1,2,3,4 (ids)
            # 200, 4000, 8000 (sizes)
        my_dict = {}
        for label, value in zip(labels, values):
            
            # Здесь вероятности складываются, если ключи `labels` повторяются!
            #
            # TODO: словарь должен быть относитеьно id точки, а не лейбла
            if label in my_dict:
                my_dict[label] += float(value)
                continue
            
            my_dict[label] = value
        
        my_dict = {key: value for key, value in my_dict.items() if float(value) != 0}

        if len(my_dict) > 10:
            sorted_dict = dict(sorted(my_dict.items(), key=lambda x: x[1], reverse=True))
            top_n = dict(itertools.islice(sorted_dict.items(), 9))
            other_sum = sum(my_dict.values()) - sum(top_n.values())
            top_n['др.'] = other_sum
            my_dict = top_n
        
        if len(my_dict) == 0:
            return

        colors = plt.cm.tab10(np.arange(len(my_dict)))
        
        fig, ax = plt.subplots()
        ax.set_title('Распределение потребителей среди поставщиков', fontsize=10, pad=40)
        
        pie = ax.pie(my_dict.values(), startangle=90)
        
        centre_circle = plt.Circle((0, 0), 0.50, color='white', fc='white', linewidth=0)
        ax.add_artist(centre_circle)
        
        annotations = []
        wedges = pie[0]
        for i, (category, value) in enumerate(my_dict.items()):
            angle = pie[0][i].theta1  # Start angle of the slice
            angle += (pie[0][i].theta2 - pie[0][i].theta1) / 2 # Mid-angle of the slice
            angle_rad = np.deg2rad(angle)
            radius = 1.1  # Adjust this value to control the length of the lines
        
            x = radius * np.cos(angle_rad)
            y = radius * np.sin(angle_rad)
            
            # Adjust percentage labels
            label_x = 1.5 * np.cos(angle_rad)  # Adjust the position of the label along x-axis
            label_y = 1.5 * np.sin(angle_rad)  # Adjust the position of the label along y-axis
            percent = my_dict[category]*100
            value = str(list(my_dict.keys())[i])
            if len(value) > 19:
                value = value[:18]+'…'
            
            annotation = ax.annotate('{:.1f}%\n{}'.format(percent, value),
                        xy=(x, y), xytext=(label_x, label_y),
                        ha='center', va='center', fontsize=10, color='white',
                        arrowprops=dict(arrowstyle='-', color=colors[i]),
                        bbox=dict(boxstyle="round,pad=0.2", fc=colors[i], alpha=1.0, edgecolor='none'))
            
            annotations.append(annotation)
        for wedge in wedges:
            wedge.set_edgecolor('white')
            wedge.set_linewidth(1)
            
        def onclick(event):
            edge_highlighed = False
            if event.inaxes == ax:
                center = (0, 0)  # Center of the pie chart
                x, y = event.xdata, event.ydata  # Coordinates of the click event
                # # Calculate the angle of the click event relative to the center of the pie chart
                angle = np.arctan2(y - center[1], x - center[0])
                # Calculate the angle of the click relative to the starting angle
                angle %= 2*np.pi  # Ensure angle is within [0, 360] degrees
                if (0 <= angle <= np.pi/2):
                    angle += 2*np.pi
                # Calculate the distance between the click event and the center of the pie chart
                distance = np.sqrt((x - center[0])**2 + (y - center[1])**2)
                # Iterate over the wedges and check if the click event falls within the boundaries of each wedge
                for i, wedge in enumerate(wedges):
                    theta1, theta2 = np.deg2rad(wedge.theta1), np.deg2rad(wedge.theta2)
                    
                    if (theta1 <= angle <= theta2) and (distance <= wedge.r + 1):
                        edge_highlighed = True
                        # Reduce alpha for all annotations and wedges
                        for annotation in annotations:
                            annotation.set_alpha(0.35)
                            # Retrieve the bounding box patch object
                            bbox_patch = annotation.get_bbox_patch()
                            r, g, b, _ = bbox_patch.get_facecolor()
                            bbox=dict(boxstyle="round,pad=0.2", fc=(r,g,b,0.35), edgecolor='none')
                            annotation.set_bbox(bbox)
                        for wedge in wedges:
                            wedge.set_alpha(0.35)
                            wedge.set_linewidth(1)
                        current_annotation = annotations[i]
                        current_wedge = wedges[i]
                        # Set alpha to 1 for the clicked annotation and wedge
                        current_annotation.set_alpha(1)
                        current_annotation.set_zorder(12)
                        bbox_patch = current_annotation.get_bbox_patch()
                        r, g, b, _ = bbox_patch.get_facecolor()
                        bbox=dict(boxstyle="round,pad=0.2", fc=(r,g,b,1), edgecolor='none')
                        current_annotation.set_bbox(bbox)
                        current_wedge.set_alpha(1)
                        # Add white border to the clicked wedge
                        current_wedge.set_linewidth(2)
                        plt.draw()
                        break  # Exit loop once a wedge is found
                        
            if not edge_highlighed:
                for annotation in annotations:
                    annotation.set_alpha(1)
                    # Retrieve the bounding box patch object
                    bbox_patch = annotation.get_bbox_patch()
                    r, g, b, _ = bbox_patch.get_facecolor()
                    bbox=dict(boxstyle="round,pad=0.2", fc=(r,g,b,1), edgecolor='none')
                    annotation.set_bbox(bbox)
                for wedge in wedges:
                    wedge.set_alpha(1)
                    wedge.set_linewidth(1)
                plt.draw()
        
        fig.canvas.mpl_connect('button_press_event', onclick)
        
        fig.subplots_adjust(top=0.77, bottom=0.15, left=0.0, right=1)
            
        self.dlg_model.layout.takeAt(0).widget().deleteLater()
        canvas = FigureCanvas(fig)
        self.dlg_model.layout.addWidget(canvas)
        # выделение линий от потребителя к поставщикам
        line_layer = QgsProject.instance().mapLayersByName('линии [g. m.]')[0]
        request = QgsFeatureRequest().setFilterExpression(f'{"f_id"} = {f_id}')
        need_line_ids = [line.id() for line in line_layer.getFeatures(request)]
        line_layer.selectByIds(need_line_ids)

    # --------------------------------------------------------------------------
    """Модель центральных мест"""

    def run_centers_dialog(self):
        self.dlg_model = MyPluginDialog()
        for layer in iface.mapCanvas().layers():
            if (layer.type() == QgsMapLayer.VectorLayer and layer.geometryType() == QgsWkbTypes.PointGeometry):
                self.dlg_model.comboBox_feature_layer.addItem(layer.name(), layer)
        self.dlg_model.comboBox_feature_layer.setCurrentIndex(-1)
        self.dlg_model.comboBox_feature_layer.currentIndexChanged.connect(lambda: self.on_layer_combobox_changed(self.dlg_model.comboBox_feature_layer, self.dlg_model.comboBox_significance_attr))

        self.dlg_model.ok_button.clicked.connect(self.run_centers_model)
        self.dlg_model.show()


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
        print(f"Время выполнения: {execution_time}")

        self.dlg_model.close()

