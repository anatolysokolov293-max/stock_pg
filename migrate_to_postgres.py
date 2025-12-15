#!/usr/bin/env python3
"""
Миграция базы данных stock_db из MySQL в PostgreSQL
"""

import mysql.connector
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_batch
from typing import Dict, List, Tuple, Any
import logging
from datetime import datetime
import sys
import re

# Настройки логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Конфигурация MySQL
MYSQL_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': '',
    'database': 'stock_db',
    'charset': 'utf8mb4'
}

# Конфигурация PostgreSQL
POSTGRES_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'user': 'postgres',
    'password': '123',
    'database': 'stock_db'
}

# Маппинг типов данных MySQL → PostgreSQL
TYPE_MAPPING = {
    'int': 'INTEGER',
    'bigint': 'BIGINT',
    'tinyint': 'SMALLINT',
    'smallint': 'SMALLINT',
    'mediumint': 'INTEGER',
    'float': 'REAL',
    'double': 'DOUBLE PRECISION',
    'decimal': 'NUMERIC',
    'varchar': 'VARCHAR',
    'char': 'CHAR',
    'text': 'TEXT',
    'mediumtext': 'TEXT',
    'longtext': 'TEXT',
    'date': 'DATE',
    'datetime': 'TIMESTAMP',
    'timestamp': 'TIMESTAMP',
    'time': 'TIME',
    'year': 'INTEGER',
    'json': 'JSONB',
    'enum': 'VARCHAR',
}

def convert_mysql_type_to_postgres(mysql_type: str) -> str:
    """Конвертирует тип данных MySQL в PostgreSQL"""
    base_type = mysql_type.split('(')[0].lower().strip()

    if 'int' in base_type and 'unsigned' in mysql_type.lower():
        if 'tinyint' in base_type:
            return 'INTEGER'
        elif 'smallint' in base_type:
            return 'INTEGER'
        elif 'mediumint' in base_type:
            return 'BIGINT'
        elif 'bigint' in base_type:
            return 'NUMERIC(20,0)'
        else:
            return 'BIGINT'

    if '(' in mysql_type:
        params = mysql_type[mysql_type.index('('):]
        pg_base = TYPE_MAPPING.get(base_type, 'TEXT')

        if base_type in ['decimal', 'numeric']:
            return f'NUMERIC{params}'
        elif base_type == 'varchar':
            return f'VARCHAR{params}'
        elif base_type == 'char':
            return f'CHAR{params}'
        else:
            return pg_base

    return TYPE_MAPPING.get(base_type, 'TEXT')

def convert_mysql_default_to_postgres(default_value: str, col_type: str) -> str:
    """Конвертирует DEFAULT значение из MySQL в PostgreSQL"""
    if default_value is None:
        return ''

    if re.match(r'^current_timestamp(\(\))?$', default_value, re.IGNORECASE):
        return 'DEFAULT CURRENT_TIMESTAMP'

    if re.match(r'^now\(\)$', default_value, re.IGNORECASE):
        return 'DEFAULT CURRENT_TIMESTAMP'

    if any(t in col_type.lower() for t in ['int', 'numeric', 'real', 'double', 'float', 'bigint', 'smallint']):
        return f'DEFAULT {default_value}'

    escaped_value = default_value.replace("'", "''")
    return f"DEFAULT '{escaped_value}'"

def get_mysql_table_structure(table_name: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Получает структуру таблицы из MySQL"""
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)

    cursor.execute(f"DESCRIBE `{table_name}`")
    columns = cursor.fetchall()

    cursor.execute(f"SHOW INDEXES FROM `{table_name}`")
    indexes = cursor.fetchall()

    cursor.close()
    conn.close()

    return columns, indexes

def create_postgres_table(table_name: str, columns: List[Dict[str, Any]], indexes: List[Dict[str, Any]]):
    """Создает таблицу в PostgreSQL"""
    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor()

    try:
        col_definitions = []
        primary_keys = []

        for col in columns:
            col_name = col['Field']
            mysql_type = col['Type']
            col_type = convert_mysql_type_to_postgres(mysql_type)

            if col['Extra'] == 'auto_increment':
                if 'bigint' in mysql_type.lower():
                    col_type = 'BIGSERIAL'
                else:
                    col_type = 'SERIAL'

            nullable = '' if col['Null'] == 'YES' else 'NOT NULL'

            default = ''
            if col['Extra'] != 'auto_increment' and col['Default'] is not None:
                default = convert_mysql_default_to_postgres(col['Default'], col_type)

            if col['Key'] == 'PRI':
                primary_keys.append(col_name)

            col_def = f'"{col_name}" {col_type} {nullable} {default}'.strip()
            col_definitions.append(col_def)

        if primary_keys:
            pk_cols = ', '.join([f'"{pk}"' for pk in primary_keys])
            pk_constraint = f'PRIMARY KEY ({pk_cols})'
            col_definitions.append(pk_constraint)

        create_table_sql = f'''
        CREATE TABLE IF NOT EXISTS "{table_name}" (
            {",\n            ".join(col_definitions)}
        );
        '''

        logger.info(f"Creating table {table_name}...")
        cursor.execute(create_table_sql)

        index_names = set()
        for idx in indexes:
            if idx['Key_name'] != 'PRIMARY' and idx['Key_name'] not in index_names:
                index_names.add(idx['Key_name'])

                idx_columns = [i['Column_name'] for i in indexes if i['Key_name'] == idx['Key_name']]

                unique = 'UNIQUE' if idx['Non_unique'] == 0 else ''
                idx_cols_str = ', '.join([f'"{col}"' for col in idx_columns])
                index_sql = f'CREATE {unique} INDEX IF NOT EXISTS "{idx["Key_name"]}" ON "{table_name}" ({idx_cols_str});'

                try:
                    cursor.execute(index_sql)
                except Exception as e:
                    logger.warning(f"Could not create index {idx['Key_name']}: {e}")

        conn.commit()
        logger.info(f"✓ Table {table_name} created successfully")

    except Exception as e:
        logger.error(f"✗ Error creating table {table_name}: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

def migrate_table_data(table_name: str, batch_size: int = 1000):
    """Переносит данные таблицы из MySQL в PostgreSQL"""
    mysql_conn = mysql.connector.connect(**MYSQL_CONFIG)
    mysql_cursor = mysql_conn.cursor(dictionary=True)

    pg_conn = psycopg2.connect(**POSTGRES_CONFIG)
    pg_cursor = pg_conn.cursor()

    try:
        mysql_cursor.execute(f"SELECT COUNT(*) as cnt FROM `{table_name}`")
        total_rows = mysql_cursor.fetchone()['cnt']

        if total_rows == 0:
            logger.info(f"Table {table_name} is empty, skipping data migration")
            return

        logger.info(f"Migrating {total_rows} rows from {table_name}...")

        mysql_cursor.execute(f"SELECT * FROM `{table_name}` LIMIT 1")
        row = mysql_cursor.fetchone()
        if not row:
            return

        columns = list(row.keys())

        offset = 0
        migrated = 0

        while offset < total_rows:
            mysql_cursor.execute(f"SELECT * FROM `{table_name}` LIMIT {batch_size} OFFSET {offset}")
            rows = mysql_cursor.fetchall()

            if not rows:
                break

            placeholders = ', '.join(['%s'] * len(columns))
            col_names = ', '.join([f'"{col}"' for col in columns])
            insert_sql = f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders})'

            values = []
            for row in rows:
                row_values = tuple(row[col] for col in columns)
                values.append(row_values)

            execute_batch(pg_cursor, insert_sql, values, page_size=batch_size)
            pg_conn.commit()

            migrated += len(rows)
            offset += batch_size

            if total_rows > 10000:
                progress = (migrated / total_rows) * 100
                if migrated % 10000 == 0 or migrated == total_rows:
                    logger.info(f"  Progress: {migrated}/{total_rows} ({progress:.1f}%)")

        logger.info(f"✓ Table {table_name}: {migrated} rows migrated successfully")

    except Exception as e:
        logger.error(f"✗ Error migrating data for {table_name}: {e}")
        pg_conn.rollback()
        raise
    finally:
        mysql_cursor.close()
        mysql_conn.close()
        pg_cursor.close()
        pg_conn.close()

def get_all_tables() -> List[str]:
    """Получает список всех таблиц из MySQL"""
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES")
    tables = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return tables

def create_postgres_database():
    """Создает базу данных в PostgreSQL"""
    conn = psycopg2.connect(
        host=POSTGRES_CONFIG['host'],
        port=POSTGRES_CONFIG['port'],
        user=POSTGRES_CONFIG['user'],
        password=POSTGRES_CONFIG['password'],
        database='postgres'
    )
    conn.autocommit = True
    cursor = conn.cursor()

    try:
        cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{POSTGRES_CONFIG['database']}'")
        exists = cursor.fetchone()

        if not exists:
            logger.info(f"Creating database {POSTGRES_CONFIG['database']}...")
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(
                sql.Identifier(POSTGRES_CONFIG['database'])
            ))
            logger.info(f"✓ Database {POSTGRES_CONFIG['database']} created")
        else:
            logger.info(f"Database {POSTGRES_CONFIG['database']} already exists")

    except Exception as e:
        logger.error(f"Error creating database: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

def main():
    """Основная функция миграции"""
    logger.info("=" * 80)
    logger.info("Starting MySQL to PostgreSQL migration")
    logger.info("=" * 80)

    try:
        logger.info("\nStep 1: Creating PostgreSQL database...")
        create_postgres_database()

        logger.info("\nStep 2: Getting list of tables...")
        tables = get_all_tables()
        logger.info(f"Found {len(tables)} tables: {', '.join(tables)}")

        logger.info("\nStep 3: Creating table structures...")
        for table in tables:
            columns, indexes = get_mysql_table_structure(table)
            create_postgres_table(table, columns, indexes)

        logger.info("\nStep 4: Migrating data...")
        for table in tables:
            migrate_table_data(table, batch_size=5000)

        logger.info("\n" + "=" * 80)
        logger.info("✓ Migration completed successfully!")
        logger.info("=" * 80)

    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error(f"✗ Migration failed: {e}")
        logger.error("=" * 80)
        sys.exit(1)

if __name__ == '__main__':
    main()
