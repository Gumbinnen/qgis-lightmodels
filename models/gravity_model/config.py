from . import GRAVITY_MODEL_VAR_NAME as VAR, CONFIG_VALIDATION_ERROR_MESSAGE as ERR_MSG
from helpers.logger import logger as log
from qgis.core import QgsVectorLayer, QgsField, Qgis

class GravityModelConfig:
    def __init__(self, parent=None):
        self._layer_consumer: QgsVectorLayer = None
        self._layer_site: QgsVectorLayer = None
        self._field_consumer: QgsField = None
        self._field_site: QgsField = None
        self._alpha: float = None
        self._beta: float = None
        self._distance_limit_meters: int = None
        self._errors: list[str] = []

    @property
    def layer_consumer(self):
        return self._layer_consumer
        
    @property
    def layer_site(self):
        return self._layer_site

    @property
    def field_consumer(self):
        return self._field_consumer

    @property
    def field_site(self):
        return self._field_site

    @property
    def alpha(self):
        return self._alpha

    @property
    def beta(self):
        return self._beta

    @property
    def distance_limit_meters(self):
        return self._distance_limit_meters
    
    @property
    def all_layers(self):
        return self._layer_consumer, self._layer_site
    
    @property
    def all_fields(self):
        return self._field_consumer, self._field_site
    
    @property
    def all_numeric_params(self):
        return self._alpha, self._beta, self.distance_limit_meters
    
    @property
    def errors(self):
        return self._errors

    def update_from_input_data(self, input_data):
        self._layer_consumer = input_data[VAR['LAYER_CONSUMER']]
        self._layer_site = input_data[VAR['LAYER_SITE']]
        self._field_consumer = input_data[VAR['FIELD_CONSUMER']]
        self._field_site = input_data[VAR['FIELD_SITE']]
        self._alpha = input_data[VAR['ALPHA']]
        self._beta = input_data[VAR['BETA']]
        self._distance_limit_meters = input_data[VAR['DISTANCE_LIMIT_METERS']]
        return self.is_valid()
    
    def is_valid(self) -> bool:
        def report(message):
            self._errors.append(message)
            log(message, note='VALIDATION ERROR:', title=type(self).__name__, level=Qgis.Error)
        
        # Проверка на валидность данных конфига
        #
        if self._layer_consumer == None:
            report(ERR_MSG['bad layer_consumer'])
            return False
        
        if self._layer_site == None:
            report(ERR_MSG['bad layer_site'])
            return False
        
        if self._field_consumer == None:
            report(ERR_MSG['bad field_consumer'])
            return False
        
        if self._field_site == None:
            report(ERR_MSG['bad field_site'])
            return False
        
        if self._alpha == None:
            report(ERR_MSG['bad alpha'])
            return False
        
        if self._beta == None:
            report(ERR_MSG['bad beta'])
            return False
        
        if self._distance_limit_meters == None:
            report(ERR_MSG['bad distance_limit_meters'])
            return False
        
        self._errors.clear()
        return True
