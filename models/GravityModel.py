from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QInputDialog, QMessageBox
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from lightmodels.widgets.GravityModelWidget import GravityModelWidget
from lightmodels.widgets.GravityModelConfigWidget import GravityModelConfigWidget


class GravityModel(QObject):
    progress_signal = pyqtSignal(int)

    def __init__(self, parent=None):
        super(GravityModel, self).__init__()
        self.iface = parent.iface
        
        # Main and config widgets
        self.gravity_widget = GravityModelWidget(self)
        self.config_widget = GravityModelConfigWidget(self)
        
        # Data from config_widget.
        self.config = None

        self.init_ui()

    def init_ui(self):
        self.connect_gravity_widget_signals()
        self.connect_config_widget_signals()

    def connect_gravity_widget_signals(self):
        self.gravity_widget.configure_signal.connect(self.configure_model)
        self.gravity_widget.diagram_tool_signal.connect(self.diagram_tool)
        self.gravity_widget.start_signal.connect(self.start)
        self.gravity_widget.cancel_signal.connect(self.cancel_computation)

    def disconnect_gravity_widget_signals(self):
        self.gravity_widget.configure_signal.disconnect(self.configure_model)
        self.gravity_widget.diagram_tool_signal.disconnect(self.diagram_tool)
        self.gravity_widget.start_signal.disconnect(self.start)
        self.gravity_widget.cancel_signal.disconnect(self.cancel_computation)

    def connect_config_widget_signals(self):
        self.config_widget.update_config_signal.connect(self.update_config)
        self.config_widget.start_signal.connect(self.start)
        self.config_widget.cancel_signal.connect(self.cancel_computation)

    def disconnect_config_widget_signals(self):
        self.config_widget.update_config_signal.disconnect(self.update_config)
        self.config_widget.start_signal.disconnect(self.start)
        self.config_widget.cancel_signal.disconnect(self.cancel_computation)

    def configure_model(self):
        self.config_widget.run()

    def run(self):
        self.gravity_widget.run()
        self.config_widget.run()
        
    def start(self):        
        if self.config is None:
            print('bad config')

        isValidConfig, whyNotValid = self.is_current_config_valid()
        if not isValidConfig:
            print("Настройки модели неверны:", whyNotValid)

        
        # create worker1, worker2, etc.
        # if possible, pass workers on different threads
        # all ui/gui on main thread workers
        # run in parallel if possible
        # as soon as all workers finished, last worker updates qgis gui

    def update_config(self, config):
        self.config = config

    def update_progress(self, progress):
        self.progress_signal.emit(progress)

    def validate_current_config(self):
        config = self.config
        layer = config['layer']
        layer_centers = config['layer_centers']
        layer_field = config['layer_field']
        layer_centers_field = config['layer_centers_field']
        alpha = config['alpha']
        beta = config['beta']
        max_distance = config['max_distance']
        
        #
        # validate data, return (False, errorMessage) if not valid component
        #

        return True

    def cancel_computation(self):
        self.computation_thread.terminate()

    def diagram_tool(self):
        pass

    def closeEvent(self, event):
        self.disconnect_gravity_widget_signals()
        self.disconnect_config_widget_signals()
        event.accept()


class ComputationThread(QThread):
    progress_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()

    def run(self):
        # Perform computations
        for i in range(100):
            # Simulate computation progress
            self.progress_signal.emit(i)
            self.msleep(100)  # Simulate delay