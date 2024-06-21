from qgis.core import QgsProject, QgsVectorLayer
from typing import Generator, Tuple
import os, csv

from ... import ILightModel
from . import GM_LAYER_STAMP_FIELD_NAME


class GravityModelDataManager:
    def __init__(self, parent: ILightModel=None):
        self.plugin_dir = parent.plugin_dir
        
        self._dir = self.create_dir()
        
    @property
    def dir_exists(self) -> bool:
        path = os.path.join(self.plugin_dir, 'data', 'gravity_model_data')
        return os.path.exists(path), path
        
    def create_dir(self):
        exists, path = self.dir_exists
        if not exists:
            os.makedirs(path)
    
    def create_file(self, layer1, layer2):
        name = f'{layer1.id()}&{layer2.id()}.csv'
        data_path = os.path.join(self._dir, name)
        return data_path
    
    def delete_all_files(self):
        if not self.dir_exists:
            return
        for file in os.listdir(self._dir):
            file_path = os.path.join(self._dir, file)
            self.delete_file(file_path)
    
    def delete_file(self, file_path):
        if self.file_exists(file_path):
            os.remove(file_path)

    def file_exists(self, path) -> bool:
        return os.path.exists(path)

    def get_all_layer_pairs(self) -> Generator[Tuple[QgsVectorLayer, QgsVectorLayer], None, None]:
        files = self._dir
        for file in files:
            layer1, layer2 = self.get_layer_pair_if_exists(file)
            if layer1 and layer2:
                yield layer1, layer2
            
    def get_data_path_if_exists(self, layer1: QgsVectorLayer | str, layer2: QgsVectorLayer | str) -> str | None:
        """layer1 and layer2 must be both type of QgsVectorLayer or QgsVectorLayer id (str)"""
        if isinstance(layer1, QgsVectorLayer) and isinstance(layer2, QgsVectorLayer):
            file_name = f"{layer1.id()}&{layer2.id()}.csv"
        elif isinstance(layer1, str) and isinstance(layer2, str):
            file_name = f"{layer1}&{layer2}.csv"
        if file_name:
            data_path = os.path.join(self._dir, file_name)
            if self.file_exists(data_path):
                return data_path
        return None

    def get_gravity_values(self, data_path):
        with open(data_path, 'r') as csvfile:
            csvreader = csv.reader(csvfile)
            
            center_ids = next(csvreader)[1:]
            feature_ids = [row[0] for row in csvreader]
            csvfile.seek(0) # В начало файла
            next(csvreader)  # Пропустить строку заголовков
            # Структура gravity_model_values:
            # [[f1_value1, f1_value2, …], [f2_value1, f2_value2, …], ...]
            # Во внутренних массивах: center_ids.count() элементов
            # Кол-во внутренних массивов: feature_ids.count() штук
            # Итого gravity_model_values: матрица center_ids.count() X feature_ids.count()
            gravity_model_values = [[float(value) for value in row[1:]] for row in csvreader]
        return center_ids, feature_ids, gravity_model_values

    def get_gravity_values_by_feature_id(self, data_path, feature_id):
        with open(data_path, 'r') as csvfile:
            csvreader = csv.reader(csvfile)
            # Первая строка — id центров
            center_ids = next(csvreader)[1:]
            for row in csvreader:
                if row[0] == feature_id:
                    feature_values = list(map(float, row[1:]))
                    break
        return center_ids, feature_values

    def get_layer_pair_ids(self, data_path):
        file_name = os.path.basename(data_path)
        layer1_id, layer2_id = tuple(file_name.split('&'))
        return layer1_id, layer2_id
    
    def get_layer_pair_if_exists(self, data_path):
        if not self.file_exists(data_path):
            return None
        
        layer1_id, layer2_id = self.get_layer_pair_ids(data_path)
        layer1 = QgsProject.instance().mapLayer(layer1_id)
        layer2 = QgsProject.instance().mapLayer(layer2_id)
        return layer1, layer2
    
    def get_second_layer(self, first_layer_id: QgsVectorLayer | str) -> QgsVectorLayer | None:
        if isinstance(first_layer_id, QgsVectorLayer):
            first_layer_id = first_layer_id.id()
        if isinstance(first_layer_id, str):
            layer_id = self.get_second_layer_id(first_layer_id)
            layer = QgsProject.instance().mapLayer(layer_id)
            return layer
    
    def get_second_layer_id(self, first_layer_id: str) -> str | None:
        files = self._dir
        for file in files:
            file_name = os.path.basename(file)
            layer_ids = file_name.split('&')
            layer_ids[1] = layer_ids[1].replace('.csv', '')
            
            if str(first_layer_id) in layer_ids[0]:
                return layer_ids[1]
            elif str(first_layer_id) in layer_ids[1]:
                return layer_ids[0]
        return None

    def is_gm_layer(self, layer):
        return GM_LAYER_STAMP_FIELD_NAME in [field.name() for field in layer.fields()]

    def read(self, data_path, contains_headers=False):
        if not self.dir_exists:
            return None
        with open(data_path, 'r') as csvfile:
            csvreader = csv.reader(csvfile)
            data = list(csvreader)
        if contains_headers:
            return data[1:], data[0]
        return data

    def write(self, data_path, data, headers=None):
        self.create_dir()
        with open(data_path, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)
            if headers:
                csvwriter.writerow(headers)
            csvwriter.writerows(data)
