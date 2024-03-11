from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt, QThread
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtWidgets import QAction
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
        
        def print_population(feature_id):
            for feature in self.active_layer.getFeatures():
                if feature.id() == feature_id:
                    print("Feature population:", feature['POPULATION'])
                    
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
            self.active_layer = self.iface.activeLayer() #!!! Change active_layer changing mechanism
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

