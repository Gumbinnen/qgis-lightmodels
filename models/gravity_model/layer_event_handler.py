from qgis.PyQt.QtCore import QObject, pyqtSignal
from functools import partial

from ... import ILightModel
from .data_manager import GravityModelDataManager as DataManager
from . import connect_once, disconnect_safe, log as log_function


class LayerEventHandler(QObject):
    feature_selection = pyqtSignal(list)
    
    def __init__(self, parent: ILightModel=None, data_manager: DataManager=None):
        super().__init__()
        self._previous_layer = None
        self.iface = parent.iface
        self.data_manager: DataManager = data_manager
        self.log = partial(log_function, title=type(self).__name__, tab_name='LightModels')
        
        connect_once(
            self.iface.currentLayerChanged,
            lambda new_layer: self.on_active_layer_changed(new_layer)
        )
    
    def on_active_layer_changed(self, new_layer):
        if new_layer is None:
            return
        
        # Проверка, создан ли слой классом GravityModel
        if not self.data_manager.is_gm_layer(new_layer):
            return
        
        # Новый активный слой
        if self._previous_layer:
            disconnect_safe(self._previous_layer.selectionChanged, self.feature_selection)
        self._previous_layer = new_layer
        
        # Вешаем сигнал feature_selection на текущий активный слой
        connect_once(
            new_layer.selectionChanged,
            lambda f_ids: self.feature_selection.emit(f_ids)
        )
