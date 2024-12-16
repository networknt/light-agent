import os

def read_file(file_path):
    try:
        with open(file_path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return None

def create_directory(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

