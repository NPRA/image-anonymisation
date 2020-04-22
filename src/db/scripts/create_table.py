"""
Create the table specified in `src.db.db_config`, with the columns specified in `src.db.columns`. If the `--drop`
argument is specified, a `DROP TABLE <table name>` will be executed before the table is created.
"""
import sys

from src.db import db_config
from src.db.columns import COLUMNS
from src.db.DatabaseClient import DatabaseClient


if __name__ == '__main__':
    # Create the "CREATE TABLE ..." SQL expression
    create_table_sql = f"CREATE TABLE {db_config.table_name}("
    for col in COLUMNS:
        create_table_sql += "\n    {:20s} {:12}".format(col.col_name, col.col_dtype)
        if col.not_null:
            create_table_sql += " {:8s}".format("NOT NULL")
        create_table_sql += ","
    create_table_sql = create_table_sql[:-1] + "\n)"

    with DatabaseClient.connect() as connection:
        cursor = connection.cursor()
        # Drop the table?
        if "--drop" in sys.argv:
            cursor.execute(f"DROP TABLE {db_config.table_name}")
            print(f"Deleted table {db_config.table_name}")

        # Create the table
        cursor.execute(create_table_sql)
        # Commit the changes
        connection.commit()

    print(f"Table {db_config.table_name} created successfully with command:\n{create_table_sql}")
