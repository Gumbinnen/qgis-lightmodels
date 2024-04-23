import itertools
from sys import dllhandle
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from .resources import *
from .LightModels_dockwidget import ModelsDockWidget
from .my_plugin_dialog import MyPluginDialog
from .gravity_dialog import GravityDialog
import os.path
from PyQt5 import QtCore, QtGui, QtWidgets
from qgis.core import *
from qgis.core import (
    QgsProject, QgsMapLayer, QgsWkbTypes, QgsVectorLayer, QgsField, QgsFeature, QgsPoint,
    QgsLayerTreeGroup, QgsLayerTreeLayer, QgsGeometry, QgsGraduatedSymbolRenderer, QgsMessageLog, Qgis,
    QgsFeatureRequest, QgsSpatialIndex, QgsSymbol, QgsCategorizedSymbolRenderer, QgsCoordinateTransformContext,
    QgsSingleSymbolRenderer, QgsMarkerSymbol, QgsRendererCategory, QgsCoordinateReferenceSystem, QgsCoordinateTransform
)
from helpers.logger import logger as log
import shutil
from qgis.PyQt.QtWidgets import QFileDialog
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
import time 
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import csv
from models.gravity_model.gravity_model import GravityModel
import os
import math


class Models:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        
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
        self.toolbar = self.iface.addToolBar(u'Models')
        self.toolbar.setObjectName(u'Models')
        
        self.gravity_model = None
        
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
        return QCoreApplication.translate('Models', message)
    
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
        gravity_icon_path = os.path.join(self.plugin_dir, 'res', 'icons', 'gravity_model_icon.png')
        regression_icon_path = os.path.join(self.plugin_dir, 'res', 'icons', 'gravity_model_icon.png')
        centers_model_icon_path = os.path.join(self.plugin_dir, 'res', 'icons', 'gravity_model_icon.png')
        self.add_action(
            icon_path=gravity_icon_path,
            text=self.tr(u'Гравитационная модель'),
            callback=self.run_gravity_model,
            parent=self.iface.mainWindow())
        self.add_action(
            icon_path=centers_model_icon_path,
            text=self.tr(u'Модель центральных мест'),
            callback=self.run_centers_model,
            parent=self.iface.mainWindow())
        
    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&LightModels'),
                action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar

    def run_gravity_model(self):
        self.gravity_model = GravityModel(self)
        self.gravity_model.run()
