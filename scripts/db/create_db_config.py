import os
import argparse
from cryptography.fernet import Fernet

import config


def encrypt_password(pwd):
    f = Fernet(config.get_db_password_encryption_key())
    encrypted = f.encrypt(pwd.encode("utf-8"))
    return encrypted


def write_file(info):
    out_filename = os.path.join(config.PROJECT_ROOT, "config", "db_config.py")
    with open(out_filename, "w") as f:
        for key, value in info.items():
            if isinstance(value, str):
                value = f"\"{value}\""
            f.write(f"{key} = {value}\n")


def get_info_from_args():
    parser = argparse.ArgumentParser(description="Create the db_config.py file, which configures the database "
                                                 "connection.")
    parser.add_argument("--user", dest="user", help="Database username", required=True)
    parser.add_argument("--password", dest="password", help="Database password (will be encrypted)", required=True)
    parser.add_argument("--dsn", dest="dsn", help="Data source name (DSN)", required=True)
    parser.add_argument("--schema", dest="schema", default=None, help="Optional schema. Default is None")
    parser.add_argument("--table_name", dest="table_name", help="Database table name.", required=True)
    args = parser.parse_args()
    return {
        "user": args.user,
        "encrypted_password": encrypt_password(args.password),
        "dsn": args.dsn,
        "schema": args.schema,
        "table_name": args.table_name,
    }


if __name__ == '__main__':
    write_file(get_info_from_args())
