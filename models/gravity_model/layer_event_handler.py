from PyQt5.QtCore import pyqtSignal
from qgis.core import Qgis
from helpers.logger import logger as log
from .data_manager import GravityModelDataManager as DataManager

class LayerEventHandler:
    feature_selection = pyqtSignal()
    
    def __init__(self, parent=None):
        self._previous_layer = None
        self.iface = parent.iface
        self.data_manager: DataManager = parent.data_manager
        
        self.iface.currentLayerChanged.connect(self.on_active_layer_changed)
    
    def on_active_layer_changed(self):
        current_layer = self.iface.activeLayer()
        
        # Проверка существования gm_data файла для этого слоя
        is_gmlayer = self.data_manager.is_gmlayer(current_layer)
        if not is_gmlayer:
            log('Unexpected layer type.', title=type(self).__name__, level=Qgis.Error)
            return
        
        # Новый активный слой
        if self._previous_layer:
            self._previous_layer.selectionChanged.disconnect(self.feature_selection)
        self._previous_layer = current_layer
        
        # Вешаем сигнал feature_selection на текущий активный слой
        current_layer.selectionChanged.connect(
            lambda f_ids: self.feature_selection.emit(f_ids)
        )
