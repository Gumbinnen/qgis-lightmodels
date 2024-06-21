from qgis.PyQt.QtCore import pyqtSignal
from functools import partial

from ... import ILightModel
from .data_manager import GravityModelDataManager as DataManager
from . import connect_once, disconnect_safe, log as log_function


class LayerEventHandler:
    feature_selection = pyqtSignal(list)
    
    def __init__(self, parent: ILightModel=None, data_manager: DataManager=None):
        self._previous_layer = None
        self.iface = parent.iface
        self.data_manager: DataManager = data_manager
        self.log = partial(log_function, title=type(self).__name__, tab_name='LightModels')
        
        connect_once(self.iface.currentLayerChanged, self.on_active_layer_changed)
    
    def on_active_layer_changed(self):
        current_layer = self.iface.activeLayer()
        
        # Проверка, создан ли слой классом GravityModel
        if not self.data_manager.is_gm_layer(current_layer):
            return
        
        # Новый активный слой
        if self._previous_layer:
            disconnect_safe(self._previous_layer.selectionChanged, self.feature_selection)
        self._previous_layer = current_layer
        
        # Вешаем сигнал feature_selection на текущий активный слой
        current_layer.selectionChanged.connect(
            lambda f_ids: self.feature_selection.emit(f_ids)
        )
        # TODO: Replace connect() with connect_once():
        # connect_once(current_layer.selectionChanged, self.feature_selection.emit)
