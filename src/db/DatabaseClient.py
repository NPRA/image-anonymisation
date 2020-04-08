import json
import iso8601
import cx_Oracle as cxo

from src.db import db_config


INSERT_STRING = f"""
    insert into {db_config.TABLE_NAME}(
        exif_tid,
        exif_gpsposisjon,
        exif_reflinkid,
        exif_reflinkposisjon,
        exif_data
    ) values (
        :exif_tid,
        :exif_gpsposisjon,
        :exif_reflinkid,
        :exif_reflinkposisjon,
        :exif_data
    )
    """


class DatabaseClient:
    def __init__(self, max_n_accumulated_rows=8):
        self.max_n_accumulated_rows = max_n_accumulated_rows
        self.accumulated_rows = []

    @staticmethod
    def connect():
        connection = cxo.connect(db_config.user, db_config.pwd, db_config.host)
        return connection

    def add_row(self, row_dict):
        row = _format_row(row_dict)
        self.accumulated_rows.append(row)

        if len(self.accumulated_rows) >= self.max_n_accumulated_rows:
            self.insert_accumulated_rows()
            self.accumulated_rows = []

    def insert_accumulated_rows(self):
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.executemany(INSERT_STRING, self.accumulated_rows)
            # pprint(self.accumulated_rows)
            connection.commit()

    def close(self):
        if self.accumulated_rows:
            self.insert_accumulated_rows()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def _format_timestamp(ts):
    out = iso8601.parse_date(ts)
    return out


def _format_number(x):
    if x is None:
        return None
    x = float(x)
    return int(x) if x.is_integer() else x


def _format_row(row_dict):
    return {
        "exif_tid": _format_timestamp(row_dict["exif_tid"]),
        "exif_gpsposisjon": str(row_dict["exif_gpsposisjon"]),
        "exif_reflinkid": _format_number(row_dict["exif_reflinkid"]),
        "exif_reflinkposisjon": _format_number(row_dict["exif_reflinkposisjon"]),
        "exif_data": json.dumps(row_dict)
        # "exif_tid": None,
        # "exif_gpsposisjon": None,
        # "exif_reflinkid": None,
        # "exif_reflinkposisjon": None,
        # "exif_data": None,
    }
