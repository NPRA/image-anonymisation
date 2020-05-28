import argparse

from config import db_config
from src.db.DatabaseClient import DatabaseClient


def parse_args():
    parser = argparse.ArgumentParser(description="Execute an SQL statement in the database")
    parser.add_argument("--sql", dest="sql", default=None, help="SQL statement")
    parser.add_argument("--file", dest="file", default=None, help="Path to a file containing the SQL statement")
    parser.add_argument("-t", "--table_name", dest="table_name", default=db_config.table_name,
                        help="Name of database table. Default is db_config.table_name")
    args = parser.parse_args()

    if args.sql is not None:
        if args.file is not None:
            parser.error("Combining '--sql' and '--file' arguments is not supported.")
        statement = args.sql
    elif args.file is not None:
        with open(args.file, "r") as f:
            statement = "".join(f.readlines())
    else:
        parser.error("No statement provided. Use either '--sql' or '--file'")

    return statement, args.table_name


def execute_statement(sql, table_name):
    cli = DatabaseClient(table_name=table_name, enable_cache=False)
    with cli.connect() as connection:
        cursor = connection.cursor()
        cursor.execute(sql)
        connection.commit()
    print("Successfully executed SQL statement:\n", sql)


if __name__ == '__main__':
    execute_statement(*parse_args())
