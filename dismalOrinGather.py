import mysql.connector
from mysql.connector import Error
from jtop import jtop
import socket
import time
from configparser import ConfigParser
from datetime import datetime
import psutil
import subprocess
import re

def run_command(command):
    try:
        return subprocess.check_output(command, shell=True, text=True).strip()
    except subprocess.CalledProcessError:
        return None

def remove_ansi_escape_sequences(text):
    ansi_escape = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', text)

def parse_jetson_release(output):
    info = {}
    for line in output.split('\n'):
        line = remove_ansi_escape_sequences(line)
        if 'Model:' in line:
            info['model'] = line.split(':', 1)[1].strip()
        elif 'Jetpack' in line:
            info['jetpack'] = line.split('[', 1)[1].split(']')[0].strip()
        elif 'L4T' in line:
            info['l4t'] = line.split('L4T ', 1)[1].strip()
        elif 'NV Power Mode' in line:
            info['nv_power_mode'] = line.split(':', 1)[1].strip()
        elif 'Serial Number' in line:
            info['serial_number'] = line.split(':', 1)[1].strip()
        elif 'P-Number' in line:
            info['p_number'] = line.split(':', 1)[1].strip()
        elif 'Module' in line:
            info['module'] = line.split(':', 1)[1].strip()
        elif 'Distribution' in line:
            info['distribution'] = line.split(':', 1)[1].strip()
        elif 'CUDA' in line:
            info['cuda'] = line.split(':', 1)[1].strip()
        elif 'cuDNN' in line:
            info['cudnn'] = line.split(':', 1)[1].strip()
        elif 'TensorRT' in line:
            info['tensorrt'] = line.split(':', 1)[1].strip()
        elif 'VPI' in line:
            info['vpi'] = line.split(':', 1)[1].strip()
        elif 'Vulkan' in line:
            info['vulkan'] = line.split(':', 1)[1].strip()
        elif 'OpenCV' in line:
            info['opencv'] = line.split(':', 1)[1].strip()
    return info

def gather_device_info():
    jetson_release_output = run_command('jetson_release -s')
    jetson_info = parse_jetson_release(jetson_release_output)
    return {
        'hostname': socket.gethostname(),
        'ip_address': socket.gethostbyname(socket.gethostname()),
        **jetson_info
    }

def read_db_config(filename='backendItems/config.ini', section='database'):
    parser = ConfigParser(interpolation=None)  # disable % interpolation
    parser.read(filename)
    db = {}
    if parser.has_section(section):
        for item in parser.items(section):
            db[item[0]] = item[1]
    else:
        raise Exception(f'Section {section} not found in {filename}')
    return db

def create_connection():
    db_config = read_db_config()
    print(f"Connecting to MySQL host: {db_config['host']} database: {db_config['database']}")
    try:
        connection = mysql.connector.connect(**db_config)
        if connection.is_connected():
            print("Connected to MySQL database")
            return connection
    except Error as e:
        print(f"MySQL Error: {e}")
        return None

def get_disk_space_gb():
    return psutil.disk_usage('/').free / (1024 ** 3)

def create_table_if_missing(cursor, table_name):
    columns = """
        id INT AUTO_INCREMENT PRIMARY KEY,
        time DATETIME,
        uptime VARCHAR(50),
        cpu1 INT, cpu2 INT, cpu3 INT, cpu4 INT, cpu5 INT, cpu6 INT,
        ram FLOAT, swap INT, emc INT, gpu INT,
        ape VARCHAR(10), nvdec VARCHAR(10), nvjpg VARCHAR(10), nvjpg1 VARCHAR(10),
        ofa VARCHAR(10), se VARCHAR(10), vic VARCHAR(10),
        fan_pwmfan0 FLOAT,
        temp_cpu FLOAT, temp_cv0 FLOAT, temp_cv1 FLOAT, temp_cv2 FLOAT, temp_gpu FLOAT,
        temp_soc0 FLOAT, temp_soc1 FLOAT, temp_soc2 FLOAT, temp_tj FLOAT,
        power_vdd_cpu_gpu_cv INT, power_vdd_soc INT, power_tot INT,
        jetson_clocks VARCHAR(10),
        nvp_model VARCHAR(50),
        disk_available_gb FLOAT,
        hostname VARCHAR(255),
        ip_address VARCHAR(50),
        model TEXT, jetpack TEXT, l4t TEXT, nv_power_mode TEXT,
        serial_number TEXT, p_number TEXT, module TEXT,
        distribution TEXT,
        cuda TEXT, cudnn TEXT, tensorrt TEXT,
        vpi TEXT, vulkan TEXT, opencv TEXT
    """
    try:
        cursor.execute(f"CREATE TABLE IF NOT EXISTS `{table_name}` ({columns});")
        print(f"Table `{table_name}` created or already exists.")
    except Error as e:
        print(f"Error creating table `{table_name}`: {e}")

def add_missing_columns(cursor, table_name, columns_dict):
    cursor.execute(f"SHOW COLUMNS FROM `{table_name}`;")
    existing_columns = [row[0] for row in cursor.fetchall()]
    for col_name, col_type in columns_dict.items():
        if col_name not in existing_columns:
            cursor.execute(f"ALTER TABLE `{table_name}` ADD COLUMN `{col_name}` {col_type};")
            print(f"Added missing column `{col_name}` to `{table_name}`.")

def insert_data(cursor, table_name, data):
    columns = ", ".join([f"`{key}`" for key in data.keys()])
    placeholders = ", ".join(["%s"] * len(data))
    query = f"INSERT INTO `{table_name}` ({columns}) VALUES ({placeholders})"
    try:
        cursor.execute(query, list(data.values()))
    except Error as e:
        print(f"MySQL Error inserting into {table_name}: {e}")

def trim_table(cursor, table_name, row_limit=50):
    query = f"""
        DELETE FROM `{table_name}`
        WHERE id NOT IN (
            SELECT id FROM (
                SELECT id FROM `{table_name}`
                ORDER BY time DESC
                LIMIT {row_limit}
            ) temp_table
        );
    """
    cursor.execute(query)

def main():
    hostname = socket.gethostname()
    storage_table_name = f"{hostname}_storage"

    connection = create_connection()
    if not connection:
        return

    try:
        cursor = connection.cursor()
        create_table_if_missing(cursor, hostname)
        create_table_if_missing(cursor, storage_table_name)
        connection.commit()

        device_info = gather_device_info()
        column_types = {'vpi': 'TEXT', 'vulkan': 'TEXT', 'opencv': 'TEXT'}

        with jtop() as jetson:
            while jetson.ok():
                stats = jetson.stats
                disk_space_gb = get_disk_space_gb()

                data = {
                    'time': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                    'uptime': stats.get('uptime'),
                    'cpu1': stats.get('CPU1', 0), 'cpu2': stats.get('CPU2', 0),
                    'cpu3': stats.get('CPU3', 0), 'cpu4': stats.get('CPU4', 0),
                    'cpu5': stats.get('CPU5', 0), 'cpu6': stats.get('CPU6', 0),
                    'ram': stats.get('RAM', 0.0), 'swap': stats.get('SWAP', 0),
                    'emc': stats.get('EMC', 0), 'gpu': stats.get('GPU', 0),
                    'ape': stats.get('APE', 'OFF'), 'nvdec': stats.get('NVDEC', 'OFF'),
                    'nvjpg': stats.get('NVJPG', 'OFF'), 'nvjpg1': stats.get('NVJPG1', 'OFF'),
                    'ofa': stats.get('OFA', 'OFF'), 'se': stats.get('SE', 'OFF'),
                    'vic': stats.get('VIC', 'OFF'),
                    'fan_pwmfan0': stats.get('Fan pwmfan0', 0.0),
                    'temp_cpu': stats.get('Temp CPU', 0.0),
                    'temp_cv0': stats.get('Temp CV0', 0.0),
                    'temp_cv1': stats.get('Temp CV1', 0.0),
                    'temp_cv2': stats.get('Temp CV2', 0.0),
                    'temp_gpu': stats.get('Temp GPU', 0.0),
                    'temp_soc0': stats.get('Temp SOC0', 0.0),
                    'temp_soc1': stats.get('Temp SOC1', 0.0),
                    'temp_soc2': stats.get('Temp SOC2', 0.0),
                    'temp_tj': stats.get('Temp tj', 0.0),
                    'power_vdd_cpu_gpu_cv': stats.get('Power VDD_CPU_GPU_CV', 0),
                    'power_vdd_soc': stats.get('Power VDD_SOC', 0),
                    'power_tot': stats.get('Power TOT', 0),
                    'jetson_clocks': stats.get('jetson_clocks', 'OFF'),
                    'nvp_model': stats.get('nvp model', 'UNKNOWN'),
                    'disk_available_gb': disk_space_gb,
                    'hostname': device_info.get('hostname'),
                    'ip_address': device_info.get('ip_address'),
                    'model': device_info.get('model'),
                    'jetpack': device_info.get('jetpack'),
                    'l4t': device_info.get('l4t'),
                    'nv_power_mode': device_info.get('nv_power_mode'),
                    'serial_number': device_info.get('serial_number'),
                    'p_number': device_info.get('p_number'),
                    'module': device_info.get('module'),
                    'distribution': device_info.get('distribution'),
                    'cuda': device_info.get('cuda'),
                    'cudnn': device_info.get('cudnn'),
                    'tensorrt': stats.get('tensorrt', ''),
                    'vpi': stats.get('vpi', ''),
                    'vulkan': stats.get('vulkan', ''),
                    'opencv': stats.get('opencv', '')
                }

                add_missing_columns(cursor, hostname, column_types)
                add_missing_columns(cursor, storage_table_name, column_types)

                insert_data(cursor, hostname, data)
                insert_data(cursor, storage_table_name, data)
                trim_table(cursor, hostname)
                connection.commit()
                time.sleep(5)

    except Error as e:
        print(f"MySQL Error: {e}")

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            print("MySQL connection is closed")

if __name__ == '__main__':
    main()
