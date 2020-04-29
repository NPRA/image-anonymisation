"""From: https://github.com/vegvesen/vegbilder/blob/master/trinn1_lagmetadata/vegbilder_lesexif.py"""
import os
import re
import uuid
import json
import iso8601
import xmltodict
import xml.dom.minidom
import numpy as np
from PIL import Image
from PIL.ExifTags import TAGS

import config
from src.Logger import LOGGER


#: Tags from Viatech
VIATECH_TAGS = {40055: "ImageProperties", 40056: "ReflinkInfo"}

# Add Viatech tags to dict of EXIF tags.
TAGS.update(VIATECH_TAGS)

#: Lovlige vegstatuser
LOVLIG_VEGSTATUS = ["S", "H", "W", "A", "P", "E", "B", "U", "Q", "V", "X", "M", "T", "G"]

#: Lovlige vegkategorier
LOVLIG_VEGKATEGORI = ["E", "R", "F", "K", "P", "S"]

#: XML tags which should be redacted in the `ImageProperties` XML.
REDACT_XML_TAGS = ["Driver", "CarID", "Comment"]

#: Regex patterns to use when redacting the `ImageProperties` XML. Precompiled for speed.
REDACT_XML_REGEX_PATTERNS = [re.compile(f"<{tag}>.*</{tag}") for tag in REDACT_XML_TAGS]

#: Placeholders for the redacted entries
REDACT_XML_REPLACE_STRINGS = [f"<{tag}>FJERNET</{tag}" for tag in REDACT_XML_TAGS]

#: Timestamp format for the deterministic id
ID_TIMESTAMP_FORMATTER = "%Y-%m-%dT%H.%M.%S.%f"
#: Pattern to remove from the filename when creating the deterministic id
ID_REMOVE_FROM_FILENAME_PATTERN = re.compile(r"_f\d+")


def exif_from_file(image_path):
    """
    Retrieve the EXIF-data from the image located at `image_path`

    :param image_path: Path to input image
    :type image_path: str
    :return: EXIF data
    :rtype: dict
    """
    pil_img = Image.open(image_path)
    exif = get_exif(pil_img)
    return exif


def write_exif(exif, output_filepath):
    with open(output_filepath, "w", encoding="utf-8") as out_file:
        json.dump(exif, out_file, indent=4, ensure_ascii=False)


def get_detected_objects_dict(mask_results):
    objs = mask_results["detection_classes"]
    if objs.size > 0:
        # Find unique objects and count them
        objs, counts = np.unique(objs, return_counts=True)
        # Convert object from id to string
        objs = [config.LABEL_MAP[int(obj_id)] for obj_id in objs]
        # Create dict
        objs = dict(zip(objs, counts.astype(str)))
    else:
        objs = {}
    return objs


def get_exif(img):
    """
    Parse the EXIF data from `img`.

    :param img: Input image
    :type img: PIL.Image
    :return: EXIF data
    :rtype: dict
    """
    exif = img._getexif()
    assert exif is not None, f"No EXIF data found for image."

    # Convert the integer keys in the exif dict to text
    labeled = label_exif(exif)

    # Process the `ImageProperties` XML
    image_properties_xml = labeled.get("ImageProperties", None)
    assert image_properties_xml is not None, "Unable to get key 40055:`ImageProperties` from EXIF."
    exif_data = process_image_properties(image_properties_xml)

    # Process the `ReflinkInfo` XML if it is available
    reflink_info_xml = labeled.get("ReflinkInfo", None)
    reflink_info = process_reflink_info(reflink_info_xml)
    exif_data = dict(exif_data, **reflink_info)

    # Title of image.
    XPTitle = labeled.get("XPTitle", b"").decode("utf16")
    exif_data['exif_xptitle'] = XPTitle

    # Assign a UUID to the image
    # exif_data['bildeuuid'] = str(uuid.uuid4())
    # Get a deterministic ID from the exif data.
    exif_data["bildeuuid"] = get_deterministic_id(exif_data)

    return exif_data


def get_deterministic_id(exif):
    """
    This function will create a unique deterministic ID from the EXIF metadata. The id is created by concatenating the
    timestamp and filename (without extension and "feltkode").

    :param exif: EXIF metadata contents
    :type exif: dict
    :return: Deterministic unique ID computed from the EXIF metadata
    :rtype: str
    """
    timestamp = iso8601.parse_date(exif["exif_tid"]).strftime(ID_TIMESTAMP_FORMATTER)
    filename = os.path.splitext(exif["exif_filnavn"])[0]
    # Remove "feltkode" from filename.
    filename = re.sub(ID_REMOVE_FROM_FILENAME_PATTERN, "", filename)
    # Create the ID
    deterministic_id = timestamp + "_" + filename
    return deterministic_id


def label_exif(exif):
    """
    Convert the standard integer EXIF-keys in `exif` to text keys.

    :param exif: EXIF dict from `PIL.Image._getexif`.
    :type exif: dict
    :return: EXIF dict with text keys.
    :rtype: dict
    """
    return {TAGS.get(key): value for key, value in exif.items()}


def process_image_properties(contents):
    """
    Process the `ImageProperties` XML from the EXIF header

    :param contents: XML-contents
    :type contents: bytes
    :return: Relevant information extracted from `contents`
    :rtype: dict
    """
    contents = to_pretty_xml(contents)
    contents = redact_image_properties(contents)
    image_properties = xmltodict.parse(contents)["ImageProperties"]

    # Position
    geo_tag = image_properties["GeoTag"]
    ewkt = f"srid=4326;POINT Z( {geo_tag['dLongitude']} {geo_tag['dLatitude']} {geo_tag['dAltitude']} )"

    # Speed and heading
    heading = image_properties.get("Heading", None)
    if heading == "NaN":
        heading = None
    speed = image_properties.get("Speed", None)
    if speed == "NaN":
        speed = None

    # Pent formatterte mappenavn
    mappenavn = re.sub(r"\\", "/", image_properties["ImageName"])
    mapper = mappenavn.split("/")

    timestamp = image_properties["@Date"]
    date = timestamp.split("T")[0]
    exif_veg = image_properties["VegComValues"]["VCRoad"]

    if len(exif_veg) >= 3:
        exif_vegnr = exif_veg[2:]
        exif_vegstat = exif_veg[1]
        exif_vegkat = exif_veg[0]
    else:
        exif_vegnr = exif_veg
        exif_vegstat = None
        exif_vegkat = None

    if exif_vegstat not in LOVLIG_VEGSTATUS or exif_vegkat not in LOVLIG_VEGKATEGORI:
        LOGGER.info(__name__, f"VCRoad={exif_veg} følger ikke KAT+STAT+vegnr syntaks: {mappenavn}")

    out = {
        "exif_tid": timestamp,
        "exif_dato": date,
        "exif_speed": speed,
        "exif_heading": heading,
        "exif_gpsposisjon": ewkt,
        "exif_strekningsnavn": image_properties["VegComValues"]["VCArea"],
        "exif_fylke": image_properties["VegComValues"]["VCCountyNo"],
        "exif_vegkat": exif_vegkat,
        "exif_vegstat": exif_vegstat,
        "exif_vegnr": exif_vegnr,
        "exif_hp": image_properties["VegComValues"]["VCHP"],
        "exif_meter": image_properties["VegComValues"]["VCMeter"],
        "exif_feltkode": image_properties["VegComValues"]["VCLane"],
        "exif_mappenavn": "/".join(mapper[0:-1]),
        "exif_filnavn": mapper[-1],
        "exif_strekningreferanse": "/".join(mapper[-4:-2]),
        "exif_imageproperties": contents
    }
    return out


def to_pretty_xml(contents_bytes):
    """
    Convert bytes-encoded XML to a prettified string.

    :param contents_bytes: Bytes-encoded XML contents
    :type contents_bytes: bytes
    :return: Prettified contents
    :rtype: str
    """
    xmlstr = contents_bytes.decode("utf-8")[1:]
    plain_xml = xml.dom.minidom.parseString(xmlstr)
    pretty_xml = plain_xml.toprettyxml()
    return pretty_xml


def redact_image_properties(contents):
    """
    Redact entries in `contents`. See `REDACT_XML_TAGS` for the list of tags to be redacted.

    :param contents: XML containing tags to be redacted.
    :type contents: str
    :return: Redacted contents
    :rtype: str
    """
    for pattern, replace_str in zip(REDACT_XML_REGEX_PATTERNS, REDACT_XML_REPLACE_STRINGS):
        contents = re.sub(pattern, replace_str, contents)
    return contents


def process_reflink_info(contents):
    """
    Process the `ReflinkInfo` XML from the EXIF header.

    :param contents: XML-contents. If `contents` is `None`, a dict with the required keys and None values, will be
                     returned.
    :type contents: bytes | None
    :return: Relevant information extracted from `contents`
    :rtype: dict
    """
    if contents is None:
        # If we got None, it means that the EXIF header did not contain  the `ReflinkInfo` XML.
        # So just return a dict with the required keys with None values.
        out = {"exif_reflinkid": None, "exif_reflinkposisjon": None, "exif_reflinkinfo": None}
        return out

    contents = to_pretty_xml(contents)
    info = xmltodict.parse(contents)["ReflinkInfo"]
    out = {
        "exif_reflinkid": info["ReflinkId"],
        "exif_reflinkposisjon": info["ReflinkPosition"],
        "exif_reflinkinfo": contents
    }
    return out
