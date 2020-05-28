"""From: https://github.com/vegvesen/vegbilder/blob/master/trinn1_lagmetadata/vegbilder_lesexif.py"""
import os
import re
import json
import iso8601
import xmltodict
import xml.dom.minidom
import numpy as np
from PIL import Image
from PIL.ExifTags import TAGS
from datetime import datetime

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

#: Pattern for extracting strekning/delstrekning from strings on the form `SxDy`
STREKNING_PATTERN = re.compile(r"S(\d+)D(\d+)\b")

#: Pattern for extracting kryss-info from filename
KRYSS_PATTERN = re.compile(r"_S(\d+)D(\d+)_m(\d+)_([KSA])D(\d+)")

EXIF_QUALITIES = {
    "good": "2",
    "missing_values": "1",
    "nonexistent": "0",
}

#: Template dictionary for the EXIF contents.
EXIF_TEMPLATE = {
    "exif_tid": None,
    "exif_dato": None,
    "exif_speed": None,
    "exif_heading": None,
    "exif_gpsposisjon": None,
    "exif_strekningsnavn": None,
    "exif_fylke": None,
    "exif_vegkat": None,
    "exif_vegstat": None,
    "exif_vegnr": None,
    "exif_hp": None,
    "exif_strekning": None,
    "exif_delstrekning": None,
    "exif_ankerpunkt": None,
    "exif_kryssdel": None,
    "exif_sideanleggsdel": None,
    "exif_meter": None,
    "exif_feltkode": None,
    "exif_mappenavn": None,
    "exif_filnavn": None,
    "exif_strekningreferanse": None,
    "exif_imageproperties": None,
    "exif_reflinkinfo": None,
    "exif_reflinkid": None,
    "exif_reflinkposisjon": None,
    "exif_roadident": None,
    "exif_roll": None,
    "exif_pitch": None,
    "exif_geoidalseparation": None,
    "exif_northrmserror": None,
    "exif_eastrmserror": None,
    "exif_downrmserror": None,
    "exif_rollrmserror": None,
    "exif_pitchrmserror": None,
    "exif_headingrmserror": None,
    "exif_xptitle": None,
    "exif_kvalitet": None,
    "bildeid": None,
    "senterlinjeposisjon": None,
    "detekterte_objekter": None,
    "versjon": None,
    "mappenavn": None,
}


def exif_from_file(image_path):
    """
    Retrieve the EXIF-data from the image located at `image_path`

    :param image_path: Path to input image
    :type image_path: str
    :return: EXIF data
    :rtype: dict
    """
    pil_img = Image.open(image_path)
    exif = get_exif(pil_img, image_path=image_path)
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


def get_exif(img, image_path):
    """
    Parse the EXIF data from `img`.

    :param img: Input image
    :type img: PIL.Image
    :param image_path: Path to input image. Used to recreate metadata when EXIF-header is missing
    :type image_path: str
    :return: EXIF data
    :rtype: dict
    """
    # Make a copy of the template dictionary. Values from the EXIF header will be inserted into this dict.
    parsed_exif = EXIF_TEMPLATE.copy()

    # Get the EXIF data
    exif = img._getexif()

    if exif is not None:
        # Convert the integer keys in the exif dict to text
        labeled = label_exif(exif)
        # Process the `ImageProperties` XML
        image_properties_xml = labeled.get("ImageProperties", None)
        assert image_properties_xml is not None, "Unable to get key 40055:`ImageProperties` from EXIF."
        process_image_properties(image_properties_xml, parsed_exif)
        # Process the `ReflinkInfo` XML if it is available
        reflink_info_xml = labeled.get("ReflinkInfo", None)
        process_reflink_info(reflink_info_xml, parsed_exif)
        # Title of image.
        XPTitle = labeled.get("XPTitle", b"").decode("utf16")
        parsed_exif["exif_xptitle"] = XPTitle
    else:
        LOGGER.warning(__name__, "No EXIF data found for image. Attempting to reconstruct data from image path.")
        if image_path is not None:
            get_metadata_from_path(image_path, parsed_exif)

    # Get a deterministic ID from the exif data.
    parsed_exif["bildeid"] = get_deterministic_id(parsed_exif)
    # Insert the folder name
    parsed_exif["mappenavn"] = get_mappenavn(image_path, parsed_exif)
    return parsed_exif


def get_deterministic_id(exif):
    """
    This function will create a unique deterministic ID from the EXIF metadata. The id is created by concatenating the
    timestamp and filename (without extension and "feltkode").

    :param exif: EXIF metadata contents
    :type exif: dict
    :return: Deterministic unique ID computed from the EXIF metadata
    :rtype: str
    """
    if exif["exif_tid"] is None or exif["exif_filnavn"] is None:
        return None

    timestamp = iso8601.parse_date(exif["exif_tid"]).strftime(ID_TIMESTAMP_FORMATTER)
    filename = os.path.splitext(exif["exif_filnavn"])[0]
    # Remove "feltkode" from filename.
    filename = re.sub(ID_REMOVE_FROM_FILENAME_PATTERN, "", filename)
    # Create the ID
    deterministic_id = timestamp + "_" + filename
    return deterministic_id


def get_mappenavn(image_path, exif):
    dirs = image_path.split(os.sep)[:-1]
    if config.exif_top_dir in dirs:
        rel_path = os.sep.join(dirs[(dirs.index(config.exif_top_dir) + 1):])
    else:
        LOGGER.warning(__name__, f"Top directory '{config.exif_top_dir}' not found in image path '{image_path}'. "
                                 f"'rel_path' will be empty")
        rel_path = ""

    timestamp = iso8601.parse_date(exif["exif_tid"])
    format_values = dict(
        aar=timestamp.year,
        maaned=timestamp.month,
        dag=timestamp.day,
        fylke=str(exif["exif_fylke"]).zfill(2),
        vegkat=exif["exif_vegkat"],
        vegstat=exif["exif_vegstat"],
        vegnr=exif["exif_vegnr"],
        hp=exif["exif_hp"],
        meter=exif["exif_meter"],
        feltkode=exif["exif_feltkode"],
        strekningreferanse=exif["exif_strekningreferanse"],
        relative_input_dir=rel_path
    )
    folder_name = config.exif_mappenavn.format(**format_values)
    assert "{" not in folder_name and "}" not in folder_name, f"Invalid `Mappenavn`: {config.db_folder_name} -> " \
                                                              f"{folder_name}."
    return folder_name
    

def label_exif(exif):
    """
    Convert the standard integer EXIF-keys in `exif` to text keys.

    :param exif: EXIF dict from `PIL.Image._getexif`.
    :type exif: dict
    :return: EXIF dict with text keys.
    :rtype: dict
    """
    return {TAGS.get(key): value for key, value in exif.items()}


def process_image_properties(contents, parsed_exif):
    """
    Process the `ImageProperties` XML from the EXIF header

    :param contents: XML-contents
    :type contents: bytes
    :param parsed_exif: Dictionary to hold the extracted values
    :type parsed_exif: dict
    :return: Relevant information extracted from `contents`
    :rtype: dict
    """
    contents = to_pretty_xml(contents)
    contents = redact_image_properties(contents)
    image_properties = xmltodict.parse(contents)["ImageProperties"]

    # Set a "default" quality. This will be adjusted if we encounter missing values
    quality = EXIF_QUALITIES["good"]

    # Position
    geo_tag = image_properties.get("GeoTag", None)
    if geo_tag is not None:
        ewkt = f"srid=4326;POINT Z( {geo_tag['dLongitude']} {geo_tag['dLatitude']} {geo_tag['dAltitude']} )"
    else:
        ewkt = None
        quality = EXIF_QUALITIES["missing_values"]

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
        exif_vegnr = exif_veg[2:].lstrip("0")
        exif_vegstat = exif_veg[1]
        exif_vegkat = exif_veg[0]
    else:
        exif_vegnr = exif_veg.lstrip("0")
        exif_vegstat = None
        exif_vegkat = None

    if exif_vegstat not in LOVLIG_VEGSTATUS or exif_vegkat not in LOVLIG_VEGKATEGORI:
        LOGGER.info(__name__, f"VCRoad={exif_veg} følger ikke KAT+STAT+vegnr syntaks: {mappenavn}")

    hp, strekning, delstrekning, ankerpunkt, kryssdel, sideanleggsdel = process_strekning_and_kryss(
        vchp=image_properties["VegComValues"]["VCHP"], filename=mapper[-1]
    )

    # Set values
    parsed_exif["exif_tid"] = timestamp
    parsed_exif["exif_dato"] = date
    parsed_exif["exif_speed"] = speed
    parsed_exif["exif_heading"] = heading
    parsed_exif["exif_gpsposisjon"] = ewkt
    parsed_exif["exif_strekningsnavn"] = image_properties["VegComValues"]["VCArea"]
    parsed_exif["exif_fylke"] = image_properties["VegComValues"]["VCCountyNo"]
    parsed_exif["exif_vegkat"] = exif_vegkat
    parsed_exif["exif_vegstat"] = exif_vegstat
    parsed_exif["exif_vegnr"] = exif_vegnr
    parsed_exif["exif_hp"] = hp
    parsed_exif["exif_strekning"] = strekning
    parsed_exif["exif_delstrekning"] = delstrekning
    parsed_exif["exif_ankerpunkt"] = ankerpunkt
    parsed_exif["exif_kryssdel"] = kryssdel
    parsed_exif["exif_sideanleggsdel"] = sideanleggsdel
    parsed_exif["exif_meter"] = image_properties["VegComValues"]["VCMeter"]
    parsed_exif["exif_feltkode"] = image_properties["VegComValues"]["VCLane"]
    parsed_exif["exif_mappenavn"] = "/".join(mapper[0:-1])
    parsed_exif["exif_filnavn"] = mapper[-1]
    parsed_exif["exif_strekningreferanse"] = "/".join(mapper[-4:-2])
    parsed_exif["exif_imageproperties"] = contents
    parsed_exif["exif_kvalitet"] = quality


def process_strekning_and_kryss(vchp, filename):
    # Look for kryss-info in filename
    kryss_matches = KRYSS_PATTERN.findall(filename)
    if kryss_matches:
        return _kryss(kryss_matches[0])

    # Look for SxDy pattern
    strekning_delstrekning_matches = STREKNING_PATTERN.findall(vchp)
    if strekning_delstrekning_matches:
        return _strekning_delstrekning(strekning_delstrekning_matches[0])

    # Fallback to old HP-standard
    return _hp(vchp)


def _kryss(matches):
    # Get metadata for a "kryss"
    strekning = matches[0]
    delstrekning = matches[1]
    ankerpunkt = matches[2]
    if matches[3] == "K":
        kryssdel = matches[4]
        sideanleggsdel = None
    else:
        sideanleggsdel = matches[4]
        kryssdel = None
    return None, strekning, delstrekning, ankerpunkt, kryssdel, sideanleggsdel


def _strekning_delstrekning(matches):
    # Get strekning/delstrekning metadata
    strekning = matches[0]
    delstrekning = matches[1]
    return None, strekning, delstrekning, None, None, None


def _hp(vchp):
    # HP metadata.
    return vchp.lstrip("0"), None, None, None, None, None


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


def process_reflink_info(contents, parsed_exif):
    """
    Process the `ReflinkInfo` XML from the EXIF header.

    :param contents: XML-contents. If `contents` is `None`, a dict with the required keys and None values, will be
                     returned.
    :type contents: bytes | None
    :param parsed_exif: Dictionary to hold the extracted values
    :type parsed_exif: dict
    :return: Relevant information extracted from `contents`
    :rtype: dict
    """
    if contents is None:
        # If we got None, it means that the EXIF header did not contain  the `ReflinkInfo` XML.
        # So just return a dict with the required keys with None values.
        return

    # Prettify XML
    contents = to_pretty_xml(contents)
    # Set raw contents
    parsed_exif["exif_reflinkinfo"] = contents
    # Parse XML
    parsed_contents = xmltodict.parse(contents)

    # Format of March 2020 update
    if "ReflinkInfo" in parsed_contents:
        reflink_info = parsed_contents["ReflinkInfo"]
        parsed_exif["exif_reflinkid"] = reflink_info["ReflinkId"]
        parsed_exif["exif_reflinkposisjon"] = reflink_info["ReflinkPosition"]

    # Format of May 2020 update
    elif "AdditionalInfoNorway2" in parsed_contents:
        # From RoadInfo
        road_info = parsed_contents["AdditionalInfoNorway2"]["RoadInfo"]
        parsed_exif["exif_reflinkid"] = road_info["ReflinkId"]
        parsed_exif["exif_reflinkposisjon"] = road_info["ReflinkPosition"]
        parsed_exif["exif_roadident"] = road_info["RoadIdent"]

        # From GnssInfo
        gnss_info = parsed_contents["AdditionalInfoNorway2"]["GnssInfo"]
        parsed_exif["exif_roll"] = gnss_info["Roll"]
        parsed_exif["exif_pitch"] = gnss_info["Pitch"]
        parsed_exif["exif_geoidalseparation"] = gnss_info["GeoidalSeparation"]
        parsed_exif["exif_northrmserror"] = gnss_info["NorthRmsError"]
        parsed_exif["exif_eastrmserror"] = gnss_info["EastRmsError"]
        parsed_exif["exif_downrmserror"] = gnss_info["DownRmsError"]
        parsed_exif["exif_rollrmserror"] = gnss_info["RollRmsError"]
        parsed_exif["exif_pitchrmserror"] = gnss_info["PitchRmsError"]
        parsed_exif["exif_headingrmserror"] = gnss_info["HeadingRmsError"]


def get_metadata_from_path(image_path, parsed_exif):
    # Set the quality
    parsed_exif["exif_kvalitet"] = EXIF_QUALITIES["nonexistent"]

    # Use os.stat to get a timestamp.
    file_stat = os.stat(image_path)
    time_created = datetime.fromtimestamp(min([file_stat.st_mtime, file_stat.st_ctime]))
    parsed_exif["exif_tid"] = time_created.strftime("%Y-%m-%dT%H:%M:%S.%f")
    parsed_exif["exif_dato"] = time_created.strftime("%Y-%m-%d")

    # Process the elements in the image path
    path_elements = image_path.split(os.sep)
    for elem in path_elements:
        _get_metadata_from_path_element(elem, parsed_exif)

    # Set the filename
    parsed_exif["exif_filnavn"] = path_elements[-1]


HP_REGEX = re.compile(r"hp(\d+)", re.IGNORECASE)
FELT_REGEX = re.compile(r"f(\d)", re.IGNORECASE)
VEG_REGEX = re.compile(f"([{''.join(LOVLIG_VEGKATEGORI)}])([{''.join(LOVLIG_VEGSTATUS)}])(\d+)", re.IGNORECASE)
METER_REGEX = re.compile(r"(?<!k)m(\d+)")
KILOMETER_REGEX = re.compile(r"km(\d{2})[_,\.](\d{3})")
FYLKE_REGEX = re.compile(r"^(\d{2})\b")
LOVLIGE_FYLKER = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "14", "15", "16", "17", "18",
                  "19", "20", "50"]


def _get_metadata_from_path_element(elem, parsed_exif):
    hp_matches = HP_REGEX.findall(elem)
    if hp_matches:
        parsed_exif["exif_hp"] = hp_matches[0].lstrip("0")

    fylke_matches = FYLKE_REGEX.findall(elem)
    if fylke_matches:
        for m in fylke_matches:
            if m in LOVLIGE_FYLKER:
                parsed_exif["exif_fylke"] = m.lstrip("0")

    felt_matches = FELT_REGEX.findall(elem)
    if felt_matches:
        parsed_exif["exif_feltkode"] = felt_matches[0][0].lstrip("0")

    veg_matches = VEG_REGEX.findall(elem)
    if veg_matches:
        parsed_exif["exif_vegkat"] = veg_matches[0][0].upper()
        parsed_exif["exif_vegstat"] = veg_matches[0][1].upper()
        parsed_exif["exif_vegnr"] = veg_matches[0][2].lstrip("0")
        
    meter_match = METER_REGEX.findall(elem)
    kilometer_match = KILOMETER_REGEX.findall(elem)
    if meter_match:
        parsed_exif["exif_meter"] = meter_match[0].lstrip("0")
    elif kilometer_match:
        meter = 1000 * int(kilometer_match[0][0]) + int(kilometer_match[0][1])
        parsed_exif["exif_meter"] = str(meter)
