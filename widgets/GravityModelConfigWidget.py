import os
from qgis.PyQt import QtGui, QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import QgsWkbTypes, QgsMapLayer, QgsMessageLog, Qgis

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'resources', 'ui', 'gravity_model_config_widget.ui'))

class GravityModelConfigWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closing_widget = pyqtSignal()
    update_config_signal = pyqtSignal(dict)
    start_signal = pyqtSignal()
    cancel_signal = pyqtSignal()

    def __init__(self, parent=None):
        super(GravityModelConfigWidget, self).__init__()
        self.iface = parent.iface
        
        self.setupUi(self)
        self.init_ui()

    def init_ui(self):        
        # Combobox selection.
        self.comboBox_feature_layer.currentIndexChanged.connect(
            lambda index: self.fill_attribute_combobox(
                index,
                self.comboBox_feature_layer,
                self.comboBox_significance_attr
            )
        )
        self.comboBox_feature_layer_2.currentIndexChanged.connect(
            lambda index: self.fill_attribute_combobox(
                index,
                self.comboBox_feature_layer_2,
                self.comboBox_significance_attr_2
            )
        )
        
        # Buttons
        self.ok_button.clicked.connect(
            lambda: self.send_start_signal()
        )
        self.cancel_button.clicked.connect(
            lambda: self.cancel_signal.emit()
        )
        
        # Default combobox QVariant "Выберите слой" at index 0.
        self.clear_comboboxes()
        self.add_default_variant()
       
    def get_layers(self):
        return self.iface.mapCanvas().layers()
    
    def clear_comboboxes(self):
        self.comboBox_feature_layer.clear()
        self.comboBox_feature_layer_2.clear()
    
    def add_default_variant(self):
        self.comboBox_feature_layer.addItem("Выберите слой...")
        self.comboBox_feature_layer.setItemData(0, False)
        self.comboBox_feature_layer.setCurrentIndex(0)
        
        self.comboBox_feature_layer_2.addItem("Выберите слой...")
        self.comboBox_feature_layer_2.setItemData(0, False)
        self.comboBox_feature_layer_2.setCurrentIndex(0)
        
    def fill_layer_comboboxes(self, layer):
        self.comboBox_feature_layer.addItem(layer.name(), layer)
        self.comboBox_feature_layer_2.addItem(layer.name(), layer)
        
    def fill_attribute_combobox(self, index, cmbox_selected_layer, attribute_combobox):
        attribute_combobox.setEnabled(True)
        
        if index == 0: # Default layer "Select layer".
            attribute_combobox.clear()
            attribute_combobox.setEnabled(False)
            return
        
        layer = cmbox_selected_layer.itemData(index)

        if layer:
            attributes = [field.name() for field in layer.fields()]
            attribute_combobox.clear()
            attribute_combobox.addItems(attributes)
    
    def is_layer_valid(self, layer):
        if not layer.isValid() or layer.type() != QgsMapLayer.VectorLayer:
            return False, "Layer is not a valid vector layer."

        if layer.geometryType() != QgsWkbTypes.PointGeometry:
            return False, "Layer does not contain point geometries."

        feature_count = layer.featureCount()
        if feature_count <= 0:
            return False, "Layer does not contain any features."

        return True, _
    
    def show_validation_error(self, message):
        self.label_features_layer.setText(message)
    
    def run(self):
        self.show()
        self.clear_comboboxes()
        self.add_default_variant()
        
        for layer in self.get_layers():
            isLayerValid, whyNotValid = self.is_layer_valid(layer)
            if isLayerValid:
                self.fill_layer_comboboxes(layer)
            
    def update_form_data(self):
        layer = self.comboBox_feature_layer.itemData(self.comboBox_feature_layer.currentIndex())
        layer_centers = self.comboBox_feature_layer_2.itemData(self.comboBox_feature_layer_2.currentIndex())
        layer_field = self.comboBox_significance_attr.currentText()
        layer_centers_field = self.comboBox_significance_attr_2.currentText()
        alpha = self.textEdit_significance_power.text()
        beta = self.textEdit_distance_power.text()
        max_distance = self.textEdit_max_distance.text()
        
        return {
            'layer': layer,
            'layer_centers': layer_centers,
            'layer_field': layer_field,
            'layer_centers_field': layer_centers_field,
            'alpha': alpha,
            'beta': beta,
            'max_distance': max_distance,
        }
            
    def send_start_signal(self):
        form_data = self.update_form_data()
        self.update_config_signal.emit(form_data)
        self.start_signal.emit()

    def log(self, message, *text:str):
        if text:
            for peace in text:
                message += ' '+peace
        QgsMessageLog.logMessage('GravityModelConfigWidget: '+message, 'LightModelsLog', level=Qgis.Info)

    def closeEvent(self, event):
        self.closing_widget.emit()
        event.accept()
