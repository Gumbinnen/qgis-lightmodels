from qgis.core import (QgsMessageLog, Qgis)

class logger:
    def __init__(self, *messages, note:str='', title:str='', tab:str=None, level=Qgis.Info, sep:str=' '):
        """Custom log function for Qgis. Combine messages into letter and log.

            Example:
                log(myValue, 'Status:', myStatus, note='MyValue:', tab='My Values')

                if isGood:
                    log(isGood, note='isGood:', title='InspectorClass:', level=Qgis.Success)
                else:
                    log(isGood, note='isGood:', title='InspectorClass:', level=Qgis.Info)

            Example output:
                INFO MyValue: 200 Status: OK
                SUCCESS InspectorClass: isGood: True

            Args:
                note (str, optional): note will appear before letter. Use for variable name when logging values. Defaults to ''.
                title (str, optional): title will appear first. Use for global information. Defaults to ''.
                tab (str, optional): If not None, QGIS will create separate log tab with given name. Defaults to ''.
                level (Qgis.MessageLevel, optional): level of the message. Common levels: Info, Warning, Critical, Success. Defaults to Qgis.Info.
                sep (str, optional): Default separate character. Defaults to ' '.
            """
        def log(*messages, note:str='', title:str='', tab:str=None, level=Qgis.Info, sep:str=' ') -> None:
            """Custom log function for Qgis. Combine messages into letter and log.

            Example:
                log(myValue, 'Status:', myStatus, note='MyValue:', tab='My Values')

                if isGood:
                    log(isGood, note='isGood:', title='InspectorClass:', level=Qgis.Success)
                else:
                    log(isGood, note='isGood:', title='InspectorClass:', level=Qgis.Info)

            Example output:
                INFO MyValue: 200 Status: OK
                SUCCESS InspectorClass: isGood: True

            Args:
                note (str, optional): note will appear before letter. Use for variable name when logging values. Defaults to ''.
                title (str, optional): title will appear first. Use for global information. Defaults to ''.
                tab (str, optional): If not None, QGIS will create separate log tab with given name. Defaults to ''.
                level (Qgis.MessageLevel, optional): level of the message. Common levels: Info, Warning, Critical, Success. Defaults to Qgis.Info.
                sep (str, optional): Default separate character. Defaults to ' '.
            """
            empty = ''
            letter = empty
            for message in messages:
                letter += sep + str(message)
            if title is not empty and note is not empty:
                title += sep
            QgsMessageLog.logMessage(title + note + letter, tag=tab, level=level)
        
        log(messages=messages,
            note=note,
            title=title,
            tab=tab,
            level=Qgis.Info,
            sep=sep)
