import os, csv

class GravityModelDataManager:
    def __init__(self, parent=None):
        self.plugin_dir = parent.plugin_dir
        
        self._dir = self.create_dir()
        
    @property
    def dir_exists(self) -> bool:
        path = os.path.join(self.plugin_dir, 'temp', 'gravity_model_data')
        return os.path.exists(path), path
        
    def create_dir(self):
        exists, path = self.dir_exists
        if not exists:
            os.makedirs(path)

    def file_exists(self, path) -> bool:
        return os.path.exists(path)

    def create_file(self, layer1, layer2):
        name = f'{layer1.id()}&{layer2.id()}.csv'
        data_path = os.path.join(self._dir, name)
        return data_path

    def write(self, data_path, data, headers=None):
        with open(data_path, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)
            if headers:
                csvwriter.writerow(headers)
            csvwriter.writerows(data)

    def read(self, data_path, contains_headers=False):
        with open(data_path, 'r') as csvfile:
            csvreader = csv.reader(csvfile)
            data = list(csvreader)
        if contains_headers:
            return data[1:], data[0]
        return data

    def delete_file(self, file_path):
        if self.file_exists(file_path):
            os.remove(file_path)

    def delete_all_files(self):
        if not self.dir_exists:
            return
        for file in os.listdir(self._dir):
            file_path = os.path.join(self._dir, file)
            self.delete_file(file_path)
