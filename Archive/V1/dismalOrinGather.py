from jtop import jtop, JtopException
import argparse
import mysql.connector
from mysql.connector import Error
import configparser
import socket

# Load database configuration from config file
def load_config(filename='config.ini'):
    config = configparser.ConfigParser()
    config.read(filename)
    return {
        'user': config.get('database', 'username'),
        'password': config.get('database', 'password'),
        'host': config.get('database', 'host'),
        'port': config.get('database', 'port'),
        'database': config.get('database', 'database')
    }

def create_table_if_not_exists(cursor, table_name, fieldnames):
    fields = ', '.join([f"`{field}` VARCHAR(255)" for field in fieldnames])
    create_table_query = f"""
    CREATE TABLE IF NOT EXISTS `{table_name}` (
        `id` INT AUTO_INCREMENT PRIMARY KEY,
        {fields}
    )
    """
    cursor.execute(create_table_query)

def insert_data(cursor, table_name, data):
    placeholders = ', '.join(['%s'] * len(data))
    columns = ', '.join([f"`{col}`" for col in data.keys()])
    insert_query = f"INSERT INTO `{table_name}` ({columns}) VALUES ({placeholders})"
    cursor.execute(insert_query, list(data.values()))

def main():
    parser = argparse.ArgumentParser(description='Simple jtop logger')
    args = parser.parse_args()

    db_config = load_config()

    connection = None
    try:
        # Connect to MySQL database
        connection = mysql.connector.connect(
            user=db_config['user'],
            password=db_config['password'],
            host=db_config['host'],
            port=db_config['port'],
            database=db_config['database']
        )
        cursor = connection.cursor()

        print("Simple jtop logger")
        print("Logging data to MySQL database")

        with jtop() as jetson:
            # Initialize the table name based on the hostname
            hostname = socket.gethostname().replace('.', '_')
            table_name = f"{hostname}"

            # Initialize first stats to get fieldnames
            stats = jetson.stats
            fieldnames = stats.keys()
            create_table_if_not_exists(cursor, table_name, fieldnames)

            # Start loop
            while jetson.ok():
                stats = jetson.stats
                insert_data(cursor, table_name, stats)
                connection.commit()  # Commit the transaction
                print("Logged data at {time}".format(time=stats['time']))

    except JtopException as e:
        print(e)
    except Error as e:
        print(f"MySQL Error: {e}")
    except KeyboardInterrupt:
        print("Closed with CTRL-C")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print("MySQL connection closed")

if __name__ == "__main__":
    main()
