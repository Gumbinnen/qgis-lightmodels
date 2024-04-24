from PyQt5.QtCore import pyqtSignal
from qgis.core import QgsFeature

class LayerEventHandler:
    feature_selection = pyqtSignal()
    
    def __init__(self, parent=None):
        self._previous_layer = None
        self.iface = parent.iface
        self.data_manager = parent.data_manager
        
        self.iface.currentLayerChanged.connect(self.on_active_layer_changed)
    
    def on_active_layer_changed(self):
        current_layer = self.iface.activeLayer()
        
        # Проверка существования gm_data файла для этого слоя
        is_gmlayer = self.data_manager.is_gmlayer(current_layer)
        if not is_gmlayer:
            return
        
        # Новый активный слой
        if self._previous_layer:
            self._previous_layer.selectionChanged.disconnect(self.feature_selection)
        self._previous_layer = current_layer
        
        # Вешаем сигнал feature_selection на текущий активный слой
        current_layer.selectionChanged.connect(
            lambda f_ids: self.feature_selection.emit(f_ids)
        )
    
    def connect_to_active_layer(self, layer):
        if self.previous_layer:
            self.disconnect_signals(self.previous_layer)
        self.previous_layer = layer
        self.connect_signals(layer)

    def connect_signals(self, layer):
        layer.selectionChanged.connect(self.on_feature_clicked)

    def disconnect_signals(self, layer):
        layer.selectionChanged.disconnect(self.on_feature_clicked)

    def on_feature_clicked(self):
        # Get the clicked feature ID or attributes
        selected_features = self.previous_layer.selectedFeatures()
        if selected_features:
            feature_id = selected_features[0].id()  # assume single selection
            self.gravity_model.featureClicked.emit(feature_id)  # emit the signa
