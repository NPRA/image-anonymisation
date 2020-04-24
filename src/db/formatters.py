import os
import re
import json
import iso8601

from src.db import geometry
from src.Logger import LOGGER
from src.io.exif_util import get_deterministic_id

WKT_GEOMETRY_REGEX = re.compile(r"srid=(\d{4});POINT Z\(\s*(\d+\.?\d*) (\d+\.?\d*) (\d+\.?\d*)\s*\)")


def to_datetime(ts):
    out = iso8601.parse_date(ts)
    return out


def to_number(x):
    if x is None:
        return None
    x = float(x)
    return int(x) if x.is_integer() else x


def to_clob(d):
    return json.dumps(d, ensure_ascii=False)


def BildeID(json_data):
    # Try to get 'bilde_id' from the json_data.
    image_id = json_data.get("bilde_id", None)

    # If 'bilde_id' could not be found in the json_data. Create it from the contents.
    if image_id is None:
        LOGGER.warning(__name__, "Could not find 'bilde_id' in JSON data. The ID will be created from the contents of "
                                 "the JSON data instead.")
        image_id = get_deterministic_id(json_data)

    return image_id


def Tidspunkt(json_data):
    return to_datetime(json_data["exif_tid"])


def Retning(json_data):
    return to_number(json_data["exif_heading"])


def Posisjon(json_data):
    # See https://docs.oracle.com/database/121/SPATL/sdo_geometry-object-type.htm#SPATL489
    # D = 3 (3 dimensions) | L = 0 (Default) | TT = 01 (Geometry type: Point)
    gtype = 3001
    # SDO_STARTING_OFFSET = 1 | SDO_ETYPE, SDO_INTERPRETATION = 1, 1 (Point)
    elem_info = [1, 1, 1]

    try:
        # Parse `exif_gpsposisjon` and create an SDOGeometry object from the results
        matches = WKT_GEOMETRY_REGEX.findall(json_data["exif_gpsposisjon"])
        srid, x, y, z = matches[0]
        sdo_geometry = geometry.SDOGeometry(gtype, int(srid), elem_info, [float(x), float(y), float(z)])
    except Exception as err:
        raise ValueError(f"Could not parse position string: {json_data['exif_gpsposisjon']}") from err

    return sdo_geometry


def FylkeNummer(json_data):
    return to_number(json_data["exif_fylke"])


def Vegkategori(json_data):
    return json_data["exif_vegkat"]


def Vegstatus(json_data):
    return json_data["exif_vegstat"]


def Vegnummer(json_data):
    return to_number(json_data["exif_vegnr"])


def StrekningReferanse(json_data):
    return json_data["exif_strekningreferanse"]


def Meter(json_data):
    return to_number(json_data["exif_meter"])


def Mappenavn(json_data):
    # TODO
    return " "


def Filnavn(json_data):
    return json_data["exif_filnavn"]


def JsonData(json_data):
    return to_clob(json_data)


def ReflinkID(json_data):
    return to_number(json_data["exif_reflinkid"])


def ReflinkPosisjon(json_data):
    return to_number(json_data["exif_reflinkposisjon"])


def DetekterteObjekter(json_data):
    return to_clob(json_data["detekterte_objekter"])


def Aar(json_data):
    datetime_obj = iso8601.parse_date(json_data["exif_tid"])
    return datetime_obj.year


def Feltkode(json_data):
    return json_data["exif_feltkode"]
