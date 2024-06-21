GRAVITY_MODEL_VAR_NAME = {
    'LAYER_CONSUMER': 0,
    'LAYER_SITE': 1,
    'FIELD_CONSUMER': 2,
    'FIELD_SITE': 3,
    'ALPHA': 4,
    'BETA': 5,
    'DISTANCE_LIMIT_METERS': 6,
}

CONFIG_VALIDATION_ERROR_MESSAGE = {
    'NO_ERROR': 'NO_ERROR',
    'bad layer_consumer': 'bad layer_consumer',
    'bad layer_site': 'bad layer_site',
    'bad field_consumer': 'bad field_consumer',
    'bad field_site': 'bad field_site',
    'bad alpha': 'bad alpha',
    'bad beta': 'bad beta',
    'bad distance_limit_meters': 'bad distance_limit_meters',
}

EXPORT_FILE_FORMAT = {
    'csv': 'csv',
    'xls': 'xls',
    'xlsx': 'xlsx'
}

GM_LAYER_STAMP_FIELD_NAME = 'LightModels_Gravity_Model_Layer'

from qgis.core import QgsMessageLog, Qgis

def log(*messages, prefix:str='', title:str='', tab_name:str=None, level=Qgis.Info, sep:str=' ') -> None:
    """Log function for Qgis. Combine messages into one message.

    Example:
        log(myValue, 'Status:', myStatus, prefix='MyValue:', tab_name='My Values')

        if isGood:
            log(isGood, note='isGood:', title='InspectorClass:', level=Qgis.Success)
        else:
            log(isGood, note='isGood:', title='InspectorClass:', level=Qgis.Info)

    Example output:
        INFO MyValue: 200 Status: OK
        SUCCESS InspectorClass: isGood: True

    Args:
        title (str, optional): title will appear first. Use for global information. Defaults to ''.
        prefix (str, optional): note will appear before letter. Use for variable name when logging values. Defaults to ''.
        tab_name (str, optional): If not None, QGIS will create separate log tab with given name. Defaults to ''.
        level (Qgis.MessageLevel, optional): level of the message. Common levels: Info, Warning, Critical, Success. Defaults to Qgis.Info.
        sep (str, optional): Default separate character. Defaults to ' '.
    """
    message = sep.join(map(str, messages))
    if title:
        title += sep
    if prefix:
        prefix += sep
    QgsMessageLog.logMessage(title + prefix + message, tag=tab_name, level=level)


def connect_once(call, action, *extra_args, **extra_kwargs) -> None: #: TODO: USE LAMBDA ONLY without *extra_args, **extra_kwargs?
    """Гарантирует единственное подключение одного сигнала или вызова функции к другому.
    

    pyqtSignal —> Callable
    
    Callable —> pyqtSignal
    
    etc.
    """
    # Wrapper function that will pass the signal arguments along with extra_args and extra_kwargs
    def wrapper(*args, **kwargs):
        action(*args, *extra_args, **kwargs, **extra_kwargs) #? TODO: What if I don't want action to receive args from call?
    
    try: # TODO: Probably too slow
        call.disconnect(wrapper) #? TODO: Replace wrapper with action?
    except AttributeError:
        # This is expected if the connection does not exist
        pass
    call.connect(wrapper)

def disconnect_safe(call, action) -> None:
    """Гарантирует отключение одного сигнала или вызова функции от другого без возникновения исключений."""
    try:
        call.disconnect(action)
    except AttributeError:
        # This is expected if the connection does not exist
        pass
