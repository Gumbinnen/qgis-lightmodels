from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import *
from qgis.gui import QgisInterface
import os.path

from . import ILightModel
from .resources import *
from .models.gravity_model.gravity_model import GravityModel


class LightModels(ILightModel):
    def __init__(self, iface: QgisInterface):
        self._iface = iface
        self._plugin_dir = os.path.dirname(__file__)
        
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
        self.toolbar = self.iface.addToolBar(u'LightModels')
        self.toolbar.setObjectName(u'LightModels')
        
        # Model fields
        self.gravity_model = None
        self.center_places_model = None
        self.regression_model = None
        
    @property
    def iface(self):
        return self._iface
    
    @property
    def plugin_dir(self):
        return self._plugin_dir
        
    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('LightModels', message)
    
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
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """
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
            self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)
        return action
    
    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        icons_dir = os.path.join(self.plugin_dir, 'resources', 'icons')
        self.add_action(
            icon_path=os.path.join(icons_dir, 'gravity_model_icon.png'),
            text=self.tr(u'Гравитационная модель'),
            callback=self.run_gravity_model,
            parent=self.iface.mainWindow())
        self.add_action(
            icon_path=os.path.join(icons_dir, 'center_places_model_icon.png'),
            text=self.tr(u'Модель центральных мест'),
            callback=self.run_center_places_model,
            parent=self.iface.mainWindow())
        self.add_action(
            icon_path=os.path.join(icons_dir, 'regression_model_icon.png'),
            text=self.tr(u'Регрессионная модель'),
            callback=self.run_cregression_model,
            parent=self.iface.mainWindow())
        
    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&LightModels'),
                action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar

    def run_gravity_model(self):
        self.gravity_model = GravityModel(parent=self)
        self.gravity_model.run()

    def run_center_places_model(self):
        ...
        
    def run_regression_model(self):
        ...
