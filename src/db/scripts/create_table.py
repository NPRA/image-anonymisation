"""
Create the table specified in `src.db.db_config`, with the columns specified in `src.db.columns`. If the `--drop`
argument is specified, a `DROP TABLE <table name>` will be executed before the table is created.
"""
import sys

from config import db_config
from src.db.columns import COLUMNS, to_string
from src.db.DatabaseClient import DatabaseClient


if __name__ == '__main__':
    # Create the "CREATE TABLE ..." SQL expression
    create_table_sql = f"CREATE TABLE {db_config.table_name}("
    for col in COLUMNS:
        create_table_sql += to_string(col)

    create_table_sql = create_table_sql[:-1] + "\n)"

    with DatabaseClient.connect() as connection:
        cursor = connection.cursor()
        # Drop the table?
        if "--drop" in sys.argv:
            drop_table_sql = f"DROP TABLE {db_config.table_name}"
            cursor.execute(drop_table_sql)
            print(f"Table '{db_config.table_name}' dropped successfully with command:\n{drop_table_sql}\n")

        # Create the table
        cursor.execute(create_table_sql)
        # Commit the changes
        connection.commit()

    print(f"Table '{db_config.table_name}' created successfully with command:\n{create_table_sql}")
