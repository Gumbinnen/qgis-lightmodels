# from . import GRAVITY_MODEL_VAR_NAME, CONFIG_VALIDATION_ERROR

GRAVITY_MODEL_VAR_NAME = {
    'LAYER_CONSUMER': 0,
    'LAYER_SITE': 1,
    'FIELD_CONSUMER': 2,
    'FIELD_SITE': 3,
    'ALPHA': 4,
    'BETA': 5,
    'DISTANCE_LIMIT_METERS': 6,
}

class GravityModelConfig:
    def __init__(self, parent=None):
        self._layer_consumer = None
        self._layer_site = None
        self._field_consumer = None
        self._field_site = None
        self._alpha = None
        self._beta = None
        self._distance_limit_meters = None
        self._errors = []

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
        self._layer_consumer = input_data[GRAVITY_MODEL_VAR_NAME['LAYER_CONSUMER']]
        self._layer_site = input_data[GRAVITY_MODEL_VAR_NAME['LAYER_SITE']]
        self._field_consumer = input_data[GRAVITY_MODEL_VAR_NAME['FIELD_CONSUMER']]
        self._field_site = input_data[GRAVITY_MODEL_VAR_NAME['FIELD_SITE']]
        self._alpha = input_data[GRAVITY_MODEL_VAR_NAME['ALPHA']]
        self._beta = input_data[GRAVITY_MODEL_VAR_NAME['BETA']]
        self._distance_limit_meters = input_data[GRAVITY_MODEL_VAR_NAME['DISTANCE_LIMIT_METERS']]
        return self.is_valid()
    
    def is_valid(self) -> bool:
        def error(message):
            self._errors.append(message)
        
        # Проверка валидности данных в конфиге
        #
        if self._layer_consumer == None:
            error('bad layer_consumer')
            return False
        
        if self._layer_site == None:
            error('bad layer_site')
            return False
        
        if self._field_consumer == None:
            error('bad field_consumer')
            return False
        
        if self._field_site == None:
            error('bad field_site')
            return False
        
        if self._alpha == None:
            error('bad alpha')
            return False
        
        if self._beta == None:
            error('bad beta')
            return False
        
        if self._distance_limit_meters == None:
            error('bad distance_limit_meters')
            return False
        
        return True
