import mysql.connector
from mysql.connector import Error
from jtop import jtop, JtopException
import socket
from configparser import ConfigParser
from datetime import datetime
import psutil
import subprocess

def run_command(command):
    """Utility function to run a shell command and return its output."""
    try:
        output = subprocess.check_output(command, shell=True, text=True).strip()
    except subprocess.CalledProcessError:
        output = None
    return output

def gather_device_info():
    """Gather detailed device information."""
    return {
        'hostname': socket.gethostname(),
        'jetpack': run_command('jetson_release -v | grep -i "jetpack" | awk \'{print $2}\''),
        'l4t': run_command('jetson_release -v | grep -i "l4t" | awk \'{print $2}\''),
        'board_model': run_command('cat /proc/device-tree/model'),
        'chip_id': run_command('cat /proc/device-tree/chosen/nvidia,chip-id'),
        'codename': run_command('uname -n'),
        'cuda_arch_bin': run_command('nvcc --version | grep -o "compute_[0-9]*" | sed \'s/compute_//\''),
        'module': run_command('cat /proc/device-tree/chosen/nvidia,module'),
        'serial': run_command('cat /proc/device-tree/chosen/nvidia,serial'),
        'soc': run_command('uname -m'),
        'ip_address': socket.gethostbyname(socket.gethostname())
    }

def read_db_config(filename='config.ini', section='database'):
    parser = ConfigParser()
    parser.read(filename)
    db = {}
    if parser.has_section(section):
        items = parser.items(section)
        for item in items:
            db[item[0]] = item[1]
    else:
        raise Exception(f'Section {section} not found in {filename}')
    return db

def create_connection():
    db_config = read_db_config()
    try:
        connection = mysql.connector.connect(**db_config)
        if connection.is_connected():
            print("Connected to MySQL database")
            return connection
    except Error as e:
        print(f"MySQL Error: {e}")
        return None

def create_table(cursor, table_name):
    create_table_query = f"""
    CREATE TABLE IF NOT EXISTS `{table_name}` (
        id INT AUTO_INCREMENT PRIMARY KEY,
        `time` DATETIME,
        `uptime` VARCHAR(50),
        `CPU1` INT,
        `CPU2` INT,
        `CPU3` INT,
        `CPU4` INT,
        `CPU5` INT,
        `CPU6` INT,
        `RAM` FLOAT,
        `SWAP` INT,
        `EMC` INT,
        `GPU` INT,
        `APE` VARCHAR(10),
        `NVDEC` VARCHAR(10),
        `NVJPG` VARCHAR(10),
        `NVJPG1` VARCHAR(10),
        `OFA` VARCHAR(10),
        `SE` VARCHAR(10),
        `VIC` VARCHAR(10),
        `Fan pwmfan0` FLOAT,
        `Temp CPU` FLOAT,
        `Temp CV0` FLOAT,
        `Temp CV1` FLOAT,
        `Temp CV2` FLOAT,
        `Temp GPU` FLOAT,
        `Temp SOC0` FLOAT,
        `Temp SOC1` FLOAT,
        `Temp SOC2` FLOAT,
        `Temp tj` FLOAT,
        `Power tj` INT,
        `Power TOT` INT,
        `jetson_clocks` VARCHAR(10),
        `nvp model` VARCHAR(50),
        `disk_available_gb` FLOAT,
        `hostname` VARCHAR(255),
        `jetpack` VARCHAR(50),
        `l4t` VARCHAR(50),
        `board_model` VARCHAR(255),
        `chip_id` VARCHAR(50),
        `codename` VARCHAR(255),
        `cuda_arch_bin` VARCHAR(50),
        `module` VARCHAR(255),
        `serial` VARCHAR(255),
        `soc` VARCHAR(50),
        `ip_address` VARCHAR(50)
    )
    """
    cursor.execute(create_table_query)
    print(f"Table `{table_name}` is ready.")

def get_disk_space_gb():
    """Returns the available disk space in GB."""
    disk_usage = psutil.disk_usage('/')
    return disk_usage.free / (1024 ** 3)

def insert_data(cursor, table_name, data):
    columns = ", ".join([f"`{key}`" for key in data.keys()])
    placeholders = ", ".join(["%s"] * len(data))
    insert_query = f"INSERT INTO `{table_name}` ({columns}) VALUES ({placeholders})"
    try:
        cursor.execute(insert_query, list(data.values()))
    except Error as e:
        print(f"MySQL Error: {e}")

def main():
    hostname = socket.gethostname()
    connection = create_connection()
    if not connection:
        return
    
    try:
        cursor = connection.cursor()
        create_table(cursor, hostname)
        
        print("Simple jtop logger")
        print("Logging data to MySQL database")
        
        device_info = gather_device_info()  # Gather device information
        
        with jtop() as jetson:
            while jetson.ok():
                stats = jetson.stats
                disk_space_gb = get_disk_space_gb()
                
                data = {
                    'time': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                    'uptime': stats.get('uptime'),
                    'CPU1': stats.get('CPU1'),
                    'CPU2': stats.get('CPU2'),
                    'CPU3': stats.get('CPU3'),
                    'CPU4': stats.get('CPU4'),
                    'CPU5': stats.get('CPU5'),
                    'CPU6': stats.get('CPU6'),
                    'RAM': stats.get('RAM'),
                    'SWAP': stats.get('SWAP'),
                    'EMC': stats.get('EMC'),
                    'GPU': stats.get('GPU'),
                    'APE': stats.get('APE'),
                    'NVDEC': stats.get('NVDEC'),
                    'NVJPG': stats.get('NVJPG'),
                    'NVJPG1': stats.get('NVJPG1'),
                    'OFA': stats.get('OFA'),
                    'SE': stats.get('SE'),
                    'VIC': stats.get('VIC'),  # Ensure this is a string
                    'Fan pwmfan0': stats.get('Fan pwmfan0'),
                    'Temp CPU': stats.get('Temp CPU'),
                    'Temp CV0': stats.get('Temp CV0'),
                    'Temp CV1': stats.get('Temp CV1'),
                    'Temp CV2': stats.get('Temp CV2'),
                    'Temp GPU': stats.get('Temp GPU'),
                    'Temp SOC0': stats.get('Temp SOC0'),
                    'Temp SOC1': stats.get('Temp SOC1'),
                    'Temp SOC2': stats.get('Temp SOC2'),
                    'Temp tj': stats.get('Temp tj'),
                    'Power tj': stats.get('Power tj'),
                    'Power TOT': stats.get('Power TOT'),
                    'jetson_clocks': stats.get('jetson_clocks'),
                    'nvp model': stats.get('nvp model'),
                    'disk_available_gb': disk_space_gb,
                    **device_info  # Include device info
                }
                insert_data(cursor, hostname, data)
                connection.commit()
                print(f"Log at {data['time']}")
    except Error as e:
        print(f"MySQL Error: {e}")
    except JtopException as e:
        print(e)
    except KeyboardInterrupt:
        print("Closed with CTRL-C")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            print("MySQL connection closed")

if __name__ == "__main__":
    main()
