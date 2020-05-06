"""
Create the table specified in `src.db.db_config`, with the columns specified in `src.db.columns`. If the `--drop`
argument is specified, a `DROP TABLE <table name>` will be executed before the table is created.
"""
import sys

from config import db_config
from src.db.Table import Table
from src.db.DatabaseClient import DatabaseClient


if __name__ == '__main__':
    # Get the table
    table = Table(db_config.table_name)

    # Create the "CREATE TABLE ..." SQL expression
    create_table_sql = f"CREATE TABLE {table.name}("
    for col in table.columns:
        create_table_sql += f"\n    {str(col)},"

    create_table_sql = create_table_sql[:-1] + "\n)"

    with DatabaseClient.connect() as connection:
        cursor = connection.cursor()
        # Drop the table?
        if "--drop" in sys.argv:
            drop_table_sql = f"DROP TABLE {table.name}"
            cursor.execute(drop_table_sql)
            print(f"Table '{table.name}' dropped successfully with command:\n{drop_table_sql}\n")

        # Create the table
        cursor.execute(create_table_sql)
        # Commit the changes
        connection.commit()

    print(f"Table '{table.name}' created successfully with command:\n{create_table_sql}")
