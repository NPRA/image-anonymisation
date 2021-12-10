import re
import json
import iso8601
import numpy as np

from src.db import geometry
from src.Logger import LOGGER
from src.io.exif_util import get_deterministic_id

WKT_GEOMETRY_REGEX = re.compile(
    r"srid=(\d+);POINT Z\(\s*(-?\d+\.?\d*|NaN|nan) (-?\d+\.?\d*|NaN|nan) (-?\d+\.?\d*|NaN|nan)\s*\)")


def to_datetime(ts):
    out = iso8601.parse_date(ts)
    return out


def to_number(x):
    if x is None:
        return None
    x = float(x)
    if np.isnan(x):
        return None
    return int(x) if x.is_integer() else x


def to_clob(d):
    return json.dumps(d, ensure_ascii=False)


def to_position(wkt_position_string, dim):
    assert dim in [2, 3]

    if wkt_position_string is None:
        return geometry.SDOGeometry(is_null=True)

    # See https://docs.oracle.com/database/121/SPATL/sdo_geometry-object-type.htm#SPATL489
    # D = 2 or 3 (2 or 3 dimensions) | L = 0 (Default) | TT = 01 (Geometry type: Point)
    gtype = int(str(dim) + "001")
    try:
        # Parse the WKT string and create an SDOGeometry object from the results
        matches = WKT_GEOMETRY_REGEX.findall(wkt_position_string)
        srid, x, y, z = matches[0]
        point_list = [float(x), float(y)]
        if dim == 3:
            point_list.append(float(z))
        sdo_geometry = geometry.SDOGeometry(gtype=gtype, srid=int(srid), point=point_list)
    except Exception as err:
        raise ValueError(f"Could not parse position string: {wkt_position_string}") from err
    return sdo_geometry


def to_height(wkt_position_string):
    if wkt_position_string is None:
        return None

    try:
        matches = WKT_GEOMETRY_REGEX.findall(wkt_position_string)
        height = to_number(matches[0][3])
    except Exception as err:
        raise ValueError(f"Could not parse position string: {wkt_position_string}") from err
    return height


def get_value_for_multiple_keys(json_data, keys):
    for key in keys:
        if key in json_data:
            return json_data[key]
    raise KeyError(f"None of the keys {keys} were found in the JSON dict.")


def ID(json_data):
    # Try to get 'bildeuuid' from the json_data.
    image_id = json_data.get("bildeid", None)

    # If 'bilde_id' could not be found in the json_data. Create it from the contents.
    if image_id is None:
        LOGGER.warning(__name__, "Could not find 'bildeid' in JSON data. The ID will be created from the contents of "
                                 "the JSON data instead.")
        image_id = get_deterministic_id(json_data)

    return image_id


def Tidspunkt(json_data):
    return to_datetime(json_data["exif_tid"])


def Dataeier(json_data):
    return json_data["exif_dataeier"]


def Kamera(json_data):
    return json_data["exif_camera"]


def Bildetype(json_data):
    return json_data["exif_imagetype"]


def Bildebredde(json_data):
    return json_data["exif_imagewidth"]


def Bildehoyde(json_data):
    return json_data["exif_imagehigh"]


def Retning(json_data):
    return to_number(json_data["exif_heading"])


def Posisjon(json_data):
    return to_position(json_data["exif_gpsposisjon"], dim=3)


def Posisjon_2d(json_data):
    return to_position(json_data["exif_gpsposisjon"], dim=2)


def Hoyde(json_data):
    return to_height(json_data["exif_gpsposisjon"])


def Moh(json_data):
    return to_number(json_data["exif_moh"])


def Strekningsnavn(json_data):
    return json_data["exif_strekningsnavn"]


def SenterlinjePosisjon(json_data):
    return to_position(json_data["senterlinjeposisjon"], dim=3)


def SenterlinjePosisjon_2d(json_data):
    return to_position(json_data["senterlinjeposisjon"], dim=2)


def SenterlinjeHoyde(json_data):
    return to_height(json_data["senterlinjeposisjon"])


def FylkeNummer(json_data):
    return to_number(json_data["exif_fylke"])


def Vegkategori(json_data):
    return json_data["exif_vegkat"]


def Vegstatus(json_data):
    return json_data["exif_vegstat"]


def Vegnummer(json_data):
    return to_number(json_data["exif_vegnr"])


def Vegtype(json_data):
    return json_data["exif_roadtype"]


def HP(json_data):
    return to_number(json_data["exif_hp"])


def Strekning(json_data):
    return to_number(json_data["exif_strekning"])


def Delstrekning(json_data):
    return to_number(json_data["exif_delstrekning"])


def Ankerpunkt(json_data):
    return to_number(json_data["exif_ankerpunkt"])


def Kryssdel(json_data):
    return to_number(json_data["exif_kryssdel"])


def Sideanleggsdel(json_data):
    return to_number(json_data["exif_sideanleggsdel"])


def StrekningReferanse(json_data):
    return json_data["exif_strekningreferanse"]


def Meter(json_data):
    return to_number(json_data["exif_meter"])


def Mappenavn(json_data):
    return json_data["mappenavn"]


def Filnavn(json_data):
    return json_data["exif_filnavn"]


def PreviwFilnavn(json_data):
    return json_data["exif_preview_filnavn"]


def JsonData(json_data):
    return to_clob(json_data)


def ReflinkID(json_data):
    return to_number(get_value_for_multiple_keys(json_data, keys=["exif_reflinkid", "veglenkeid"]))


def ReflinkPosisjon(json_data):
    return to_number(get_value_for_multiple_keys(json_data, keys=["exif_reflinkposisjon", "veglenkepos"]))


def DetekterteObjekter(json_data):
    return to_clob(json_data["detekterte_objekter"])


def Aar(json_data):
    datetime_obj = iso8601.parse_date(json_data["exif_tid"])
    return datetime_obj.year


def Feltkode(json_data):
    return json_data["exif_feltkode"]


def VegIdentitet(json_data):
    return json_data["exif_roadident"]


def Versjon(json_data):
    return json_data.get("versjon", None)


def XpTitle(json_data):
    return json_data["exif_xptitle"]


def ExifKvalitet(json_data):
    return to_number(json_data.get("exif_kvalitet", None))
