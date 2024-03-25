from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt, QThread
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtWidgets import QAction, QWidget, QHBoxLayout
from .resources import *
from .LightModels_dockwidget import ModelsDockWidget
from .my_plugin_dialog import MyPluginDialog
from .gravity_dialog import GravityDialog
import os.path
from PyQt5.QtCore import Qt
from qgis.core import *
from qgis.core import QgsMapLayer, QgsWkbTypes
from _struct import *
from qgis.utils import iface
from qgis.PyQt.QtCore import Qt
from .model_worker import GravityModelWorker, CentersModelWorker
from qgis.PyQt.QtWidgets import QVBoxLayout, QPushButton
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.core import QgsProject, QgsVectorLayer
from qgis.gui import QgsMapTool
from qgis.core import QgsMapLayerProxyModel, QgsProject
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPixmap, QImage
from qgis.PyQt.QtWidgets import QLabel

class TitleBar(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.initUI()

    def initUI(self):
        layout = QHBoxLayout()

        # Add pin button
        self.pin_button = QPushButton(QIcon('./YandexDisk.png'), '')
        self.pin_button.setCheckable(True)
        self.pin_button.setChecked(False)
        self.pin_button.clicked.connect(self.parent.toggle_pin)
        layout.addWidget(self.pin_button)

        # Add minimize button
        minimize_button = QPushButton(QIcon('./minimize_icon.ico'), '')
        minimize_button.clicked.connect(self.parent.show_minimized)
        layout.addWidget(minimize_button)

        # Add close button
        close_button = QPushButton(QIcon('./close_icon.ico'), '')
        close_button.clicked.connect(self.parent.close)
        layout.addWidget(close_button)

        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)


class DiagramWindow(QWidget):
    def __init__(self, parent=None):
        super(DiagramWindow, self).__init__(parent)
        self.initUI()
        

    def initUI(self):        
        self.setWindowTitle("Diagram")
        self.layout = QVBoxLayout()
        
        # Title bar
        # self.title_bar = TitleBar(self)
        # self.title_bar.setObjectName('TitleBar')
        # self.layout.addWidget(self.title_bar)
        
        # Content
        self.figure = plt.figure()
        self.canvas = FigureCanvas(self.figure)
        self.layout.addWidget(self.canvas)
        
        # Close button
        self.close_button = QPushButton("Закрыть")
        self.close_button.clicked.connect(self.close)
        self.layout.addWidget(self.close_button)

        # Create pin button
        self.pin_button = QPushButton('Всегда наверху')
        self.pin_button.setCheckable(True)
        self.pin_button.setChecked(False)
        self.pin_button.clicked.connect(self.toggle_pin)
        self.layout.addWidget(self.pin_button)
        
        self.setLayout(self.layout)
        # Make default title bar disaper
        # self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)

    def plot_diagram(self, data):
        # Столбчатая диаграмма
        # self.figure.clear()
        # ax = self.figure.add_subplot(111)
        # x = [d[0] for d in data]  # Feature IDs
        # y = [d[1] for d in data]  # Attribute values
        # ax.bar(x, y)
        # ax.set_xlabel('Feature ID')
        # ax.set_ylabel('Attribute Value')
        # ax.set_title('Diagram of Feature Related Data')
        # self.canvas.draw()
        
        # Круговая диаграмма
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        labels = [f'{d[0]}' for d in data]
        sizes = [d[1] for d in data] 
        ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
        ax.axis('equal')
        ax.set_title('Вероятности')
        self.canvas.draw()
        
    def toggle_pin(self):
        if self.pin_button.isChecked():
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.show()
        
    def show_minimized(self):
        print('test: show_minimized')


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

        self.pluginIsActive = False
        self.dockwidget = None
        
        # Active layer for feature selection
        self.active_layer = None
        self.diagram_window = None


    def set_active_layer(self, layer):
        if isinstance(layer, QgsVectorLayer):
            self.active_layer = layer
            self.active_layer.selectionChanged.connect(self.create_diagram)


    def get_feature_data_from_ids(self, ids):
        pass

    def create_diagram(self, data):
        if self.active_layer is None:
            print('Error: self.active_layer is None')
            return

        # selected_features = self.active_layer.selectedFeatures()

        # feature_data = []
        # for feature in selected_features:
            
        #     feature_id = feature.id()
        #     feature_attributes = feature.attributes()
            
        #     attribute_value = feature['POPULATION']
        #     feature_data.append((feature_id, attribute_value))
        
        f_data = [('Цинциннати', 52), ('Кливленд', 37), ('whatever', 11)]

        # Show diagram
        self.show_diagram(f_data)


    def show_diagram(self, data):
        if not self.diagram_window:
            self.diagram_window = DiagramWindow()
        self.diagram_window.plot_diagram(data)
        self.diagram_window.show()


    def close_diagram(self):
        if self.diagram_window:
            self.diagram_window.close()
            self.diagram_window = None


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
        self.disconnect_slots_and_signals()
        self.dockwidget.model_comboBox.clear()
        self.pluginIsActive = False
        print("Plugin close")


    def disconnect_slots_and_signals(self):
        # if self.dockwidget.closingPlugin.isConnected():
        self.dockwidget.closingPlugin.disconnect(self.on_close_plugin)
        # if self.dockwidget.ok_button.clicked.isConnected():
        self.dockwidget.ok_button.clicked.disconnect(self.run_model_dialog)
        # if self.active_layer.selectionChanged.isConnected():
        # self.active_layer.selectionChanged.disconnect(self.process_selected_features_ids)

    # удаление меню плагина и иконки с qgis интерфейса
    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&LightModels'),
                action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar


    def start_model_worker(self, worker_class: type):
        self.thread = QThread()
        self.worker = worker_class # model worker class
        
        self.worker.moveToThread(self.thread) # move Worker-Class to a thread
        # Connect signals and slots:
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.worker.report_progress)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.finished.connect(self.thread.quit)
        self.dlg_model.cancel_button.clicked.connect(self.request_worker_cancelation) # cancel execution
        
        self.dlg_model.ok_button.setEnabled(False) # disable the OK button while thread is running
        self.dlg_model.cancel_button.clicked.connect(lambda: self.dlg_model.ok_button.setEnabled(True)) # enable the OK button when cancel button clicked
        self.thread.start()


    def kill_model_worker(self):
        if self.worker != None:
            self.worker.stop()                   
        
        if self.thread != None:
            if self.thread.isRunning():
                self.thread.quit()
        
            self.thread.started.disconnect(self.worker.run)
            self.worker.progress.disconnect(self.worker.report_progress)
            self.worker.finished.disconnect(self.on_worker_finished)
            self.worker.finished.disconnect(self.thread.quit)
            self.dlg_model.cancel_button.clicked.disconnect(self.request_worker_cancelation)
        
        
    def request_worker_cancelation(self):
        self.worker.is_calcelation_requested = True
        
        
    def on_worker_finished(self):
        self.dlg_model.close()


    def process_selected_features_ids(self, selected_features_ids, result2, result3):
        data = self.get_feature_data_from_ids(selected_features_ids)
        self.create_diagram(data)
    
    
    def run_diagram_tool(self):
        self.active_layer = self.iface.activeLayer() #!!! Change active_layer changing mechanism
        if self.active_layer:
            self.active_layer.selectionChanged.connect(self.process_selected_features_ids)
                
        self.iface.actionSelect().trigger()
        self.iface.mapCanvas().setSelectionColor(QColor("light blue"))
    
    
    def stop_diagram_tool(self):
        self.active_layer.selectionChanged.disconnect(self.process_selected_features_ids)
    
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
            self.dockwidget.diagram_tool_button.clicked.connect(self.run_diagram_tool)
            self.dockwidget.diagram_tool_stop_button.clicked.connect(self.stop_diagram_tool)
            
            
    def on_layer_combobox_changed_do_show_layer_attrs(self, layer_cmb, attrs_cmb):
        layer = layer_cmb.itemData(layer_cmb.currentIndex())
        attributes = [field.name() for field in layer.fields()]
        attrs_cmb.clear()
        attrs_cmb.addItems(attributes)
    

    def on_close_model_dialog(self):
        if self.worker.is_running != None and self.worker.is_running:
            self.kill_model_worker()
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
            worker = GravityModelWorker(dlg_model=self.dlg_model)
        elif model == "Модель центральных мест":
            worker = CentersModelWorker(dlg_model=self.dlg_model)
        
        if worker is not None:
            self.start_model_worker(worker)

