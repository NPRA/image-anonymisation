"""From: https://github.com/vegvesen/vegbilder/blob/master/trinn1_lagmetadata/vegbilder_lesexif.py"""
import os
import re
import json
import sys
import traceback
import iso8601
import xmltodict
import xml.dom.minidom
import numpy as np
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
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
ID_TIMESTAMP_FORMATTER = "%Y-%m-%dT%H.%M.%S"

#: Pattern to remove from the filename when creating the deterministic id
ID_REMOVE_FROM_FILENAME_PATTERN = re.compile(r"_f\d+")

#: Pattern for extracting strekning/delstrekning from strings on the form `SxDy`
STREKNING_PATTERN = re.compile(r"S(\d+)D(\d+)\b")

#: Pattern for extracting kryss-info from filename
KRYSS_PATTERN = re.compile(r"_S(\d+)D(\d+)_m(\d+)_([KSA])D(\d+)")

#: The exif qualities give an indication of the data contained in the exif of an image.
#: 2 means that the metadata we are expecting is present, as well as the gps-position
#: 1 means that the gps position could not be found.
#: 0 means that the metadata could not be found.
EXIF_QUALITIES = {
    "good": "2",
    "missing_values": "1",
    "nonexistent": "0",
}

#: Template dictionary for the EXIF contents.
EXIF_TEMPLATE = {
    "exif_tid": None,
    "exif_dato": None,
    "exif_dataeier": None,
    "exif_camera": None,
    "exif_imagetype": None,
    "exif_imagewidth": None,
    "exif_imagehigh": None,
    "exif_speed_ms": None,
    "exif_heading": None,
    "exif_gpsposisjon": None,
    "exif_altitude": None,
    "exif_moh": None,
    "exif_strekningsnavn": None,
    "exif_fylke": None,
    "exif_vegkat": None,
    "exif_vegstat": None,
    "exif_vegnr": None,
    "exif_roadtype": "Ukjent",
    "exif_hp": None,  # null
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
    "exif_imageproperties": None,  # null
    "exif_basislinje": None,
    "exif_reflinkinfo": None,  # Null
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

    # Add general image metadata to the exif.
    parsed_exif["exif_imagetype"] = config.image_type
    parsed_exif["exif_imagewidth"] = str(img.size[0])
    parsed_exif["exif_imagehigh"] = str(img.size[1])

    # Get the EXIF data
    exif = img._getexif()

    if exif is not None:
        # Convert the integer keys in the exif dict to text
        labeled = label_exif(exif)
        gpsinfo_exif = labeled.get("GPSInfo", None)
        gpsinfo = None if not gpsinfo_exif else get_gpsinfo(labeled)

        # Default quality will be "good" which corresponds to "2" for any image that has exif.
        parsed_exif["exif_kvalitet"] = EXIF_QUALITIES["good"]
        parsed_exif["exif_camera"] = labeled.get("Model", None)
        if config.data_eier:
            parsed_exif["exif_dataeier"] = config.data_eier

        reflink_info_xml = labeled.get("ReflinkInfo", None)

        # This is to make sure the correct time is read from the image.
        if "DateTimeOriginal" in labeled.keys():
            # Convert time format "year:month:day hours:minutes:seconds" -> "year-month-dayThours:minutes:seconds"
            timestamp = labeled["DateTimeOriginal"].split(" ")
            timestamp[0] = timestamp[0].replace(":", "-")
            # Save date
            parsed_exif["exif_dato"] = timestamp[0]
            timestamp = "T".join(timestamp)
            parsed_exif["exif_tid"] = timestamp

        if reflink_info_xml:
            process_reflink_info(reflink_info_xml, parsed_exif)
        else:
            # Lower the quality level to 'missing values'
            parsed_exif["exif_kvalitet"] = EXIF_QUALITIES["missing_values"]
            # Extract road info from file name
            # check if it's the full string
            extract_road_info_from_filename(image_path, parsed_exif, labeled)
            # Extract GPS information from the image
            if gpsinfo_exif:
                process_gpsinfo_tag(gpsinfo, parsed_exif)

        # Title of image.
        XPTitle = labeled.get("XPTitle", b"").decode("utf16")
        parsed_exif["exif_xptitle"] = XPTitle

    else:
        LOGGER.warning(__name__, "No EXIF data found for image. Attempting to reconstruct data from image path.")
        if image_path is not None:
            # Set the quality
            parsed_exif["exif_kvalitet"] = EXIF_QUALITIES["nonexistent"]
            get_metadata_from_path(image_path, parsed_exif)

    # Get a deterministic ID from the exif data.
    parsed_exif["bildeid"] = get_deterministic_id(parsed_exif, parsed_exif["exif_feltkode"])
    # Insert the folder name
    parsed_exif["mappenavn"] = get_mappenavn(image_path, parsed_exif)
    # Set roadident if it hasn't already been set.
    parsed_exif["exif_roadident"] = create_roadident_from_extracted_data(parsed_exif) \
        if not parsed_exif["exif_roadident"] else parsed_exif["exif_roadident"]
    return parsed_exif


def get_deterministic_id(exif, feltkode):
    """
    This function will create a unique deterministic ID from the EXIF metadata. The id is created by concatenating the
    timestamp and filename (without extension and "feltkode").

    :param exif: EXIF metadata contents
    :type exif: dict
    :param feltkode: The "feltkode" (Lane number/name) of the image.
    :type feltkode: str
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
    deterministic_id = timestamp + "_" + filename + f"_{config.image_type}_{feltkode}"
    return deterministic_id


def get_rel_path(image_path):
    dirs = image_path.split(os.sep)[:-1]
    if config.exif_top_dir in dirs:
        # Uncomment below for forward-slash separator or backward-slash.
        rel_path = "/".join(dirs[(dirs.index(config.exif_top_dir) + 1):])
        # rel_path = os.sep.join(dirs[(dirs.index(config.exif_top_dir) + 1):])
    else:
        LOGGER.warning(__name__, f"Top directory '{config.exif_top_dir}' not found in image path '{image_path}'. "
                                 f"'rel_path' will be empty")
        rel_path = ""
    return rel_path


def get_mappenavn(image_path, exif):
    dirs = image_path.split(os.sep)[:-1]
    if config.exif_top_dir in dirs:
        # Uncomment below for forward-slash separator or backward-slash.
        rel_path = "/".join(dirs[(dirs.index(config.exif_top_dir) + 1):])
        # rel_path = os.sep.join(dirs[(dirs.index(config.exif_top_dir) + 1):])
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
        meter=exif["exif_meter"],
        feltkode=exif["exif_feltkode"],
        strekningreferanse=exif["exif_strekningreferanse"],
        relative_input_dir=rel_path
    )
    folder_name = config.exif_mappenavn.format(**format_values)
    assert "{" not in folder_name and "}" not in folder_name, f"Invalid `Mappenavn`: {config.db_folder_name} -> " \
                                                              f"{folder_name}."
    return folder_name


def get_gpsinfo(labeled_exif):
    """
    Decodes and gets the GPSInfo from the exif.
    """
    gpsinfo = {}
    for key in labeled_exif['GPSInfo'].keys():
        decode = GPSTAGS.get(key, key)
        gpsinfo[decode] = labeled_exif['GPSInfo'][key]
    return gpsinfo


def label_exif(exif):
    """
    Convert the standard integer EXIF-keys in `exif` to text keys.

    :param exif: EXIF dict from `PIL.Image._getexif`.
    :type exif: dict
    :return: EXIF dict with text keys.
    :rtype: dict
    """
    return {TAGS.get(key): value for key, value in exif.items()}


def extract_road_info_from_filename(filepath, parsed_exif, labeled_exif):
    """
    Extracts the road info from the file name.
    """
    get_metadata_from_path(filepath, parsed_exif)
    filename = filepath.split(os.sep)[-1]
    # Convert time format "year:month:day hours:minutes:seconds" -> "year-month-dayThours:minutes:seconds"
    timestamp = labeled_exif.get("DateTimeOriginal", None)
    if timestamp:
        timestamp = timestamp.split(" ")
        timestamp[0] = timestamp[0].replace(":", "-")

        # Save date
        parsed_exif["exif_dato"] = timestamp[0]
        timestamp = "T".join(timestamp)
        parsed_exif["exif_tid"] = timestamp

    parsed_exif["exif_filnavn"] = filename
    road_info_list = filename.split(".")[0].split("_")
    for path_elem in road_info_list:
        strekning_match = STREKNING_PATTERN.findall(path_elem)
        if strekning_match:
            parsed_exif["exif_strekning"], parsed_exif["exif_delstrekning"] = _strekning_delstrekning(
                strekning_match[0])


def create_roadident_from_extracted_data(parsed_exif):
    """
    A helper function to create a roadident string
    from the parsed_exif data.
    The string should have the format: "{vegkat+vegstatus+vegnr} S{strekning}D{delstrekning} m{meter}"
    E.G: FV63 S10D3 m41
    """
    roadident_roadpart_string = f"S{parsed_exif['exif_strekning']}D{parsed_exif['exif_delstrekning']}"
    kryss_string = f"K{parsed_exif['exif_kryssdel']}"
    sideanlegg_string = f"A{parsed_exif['exif_sideanleggsdel']}"
    roadident_special_roadtype_string = f" {sideanlegg_string} " if parsed_exif[
        "exif_sideanleggsdel"] else f" {kryss_string} " \
        if parsed_exif["exif_kryssdel"] else ""
    roadident_anchor_string = f" M{parsed_exif['exif_ankerpunkt']} " if parsed_exif['exif_ankerpunkt'] else ""
    # Stitch together the elements of the roadident-string
    roadident_string = f"{parsed_exif['exif_vegkat']}{parsed_exif['exif_vegstat']}{parsed_exif['exif_vegnr']}" \
                       f" {roadident_roadpart_string}" \
                       f"{roadident_anchor_string}" \
                       f"{roadident_special_roadtype_string}" \
                       f" m{parsed_exif['exif_meter']}"
    return roadident_string


def process_strekning_and_kryss(path_elem):
    # Look for kryss-info in filename
    kryss_matches = KRYSS_PATTERN.findall(path_elem)
    if kryss_matches:
        return _kryss(kryss_matches[0])
    return None, None, None, None, None


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
    return strekning, delstrekning, ankerpunkt, kryssdel, sideanleggsdel


def _strekning_delstrekning(matches):
    # Get strekning/delstrekning metadata
    strekning = matches[0]
    delstrekning = matches[1]
    return strekning, delstrekning


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


def process_reflink_info(contents, parsed_exif):
    """
    Process the `ReflinkInfo` XML from the EXIF header.

    :param contents: XML-contents. If `contents` is `None`, a dict with the required keys and None values, will be
                     returned.
    :type contents: bytes | None
    :param parsed_exif: Dictionary to hold the extracted values
    :type parsed_exif: dict
    :return: Relevant information extracted from `contents`
    :rtype: None
    """
    if contents is None:
        # If we got None, it means that the EXIF header did not contain  the `ReflinkInfo` XML.
        parsed_exif["exif_kvalitet"] = EXIF_QUALITIES["missing_values"]
        return

    # Prettify XML
    contents = to_pretty_xml(contents)

    # Parse XML
    parsed_contents = xmltodict.parse(contents)

    try:
        if "ReflinkInfo" in parsed_contents:
            reflink_info = parsed_contents["ReflinkInfo"]
            parsed_exif["exif_reflinkid"] = reflink_info["ReflinkId"]
            parsed_exif["exif_reflinkposisjon"] = reflink_info["ReflinkPosition"]

        elif "AdditionalInfoNorway2" in parsed_contents:
            # From RoadInfo
            road_info = parsed_contents["AdditionalInfoNorway2"]["RoadInfo"]
            parsed_exif["exif_reflinkid"] = road_info["ReflinkId"]
            parsed_exif["exif_reflinkposisjon"] = road_info["ReflinkPosition"]
            parsed_exif["exif_roadident"] = road_info["RoadIdent"]

            # From GnssInfo
            gnss_info = parsed_contents["AdditionalInfoNorway2"]["GnssInfo"]
            if config.image_type == "360" and (
                    not gnss_info["Latitude"] or not gnss_info["Longitude"] or not gnss_info["Altitude"]):
                # If the elements of the gpsposisjon-string does not exist,
                # the exif quality will be lowered to "missing valuse", "1"
                parsed_exif["exif_kvalitet"] = EXIF_QUALITIES["missing_values"]

            image_info = parsed_contents["AdditionalInfoNorway2"]["ImageInfo"]
            update_exif_with_reflink_data(parsed_exif, road_info, gnss_info, image_info)
    except KeyError as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        LOGGER.warning(__name__, f"Got a KeyError from key '{e}'. The output .json file will have missing values. "
                                 f"Please check the input image's RefLink-exif tag for furhter inspection. "
                                 f"Full traceback {traceback.print_exc(exc_type, exc_value, exc_traceback)}")


def update_exif_with_reflink_data(parsed_exif, road_info, gnss_info, image_info):
    """
    Update the parsed_exif with the relevant values that can be found in the "AdditionalInfoNorway2"-tag
    in the reflink of the image.
    It will only update the fields that haven't been updated yet.

    :param parsed_exif: A dictionary to hold the extracted values
    :type parsed_exif: dict
    :param road_info: A dictionary containing road information from the reflink xml
    :type road_info: dict
    :param gnss_info: A dictionary containing gnss (global satellite system) information form the reflink xml
    :type gnss_info: dict
    :param image_info: A dictionary containing image information from the reflink xml
    :type image_info: dict
    :rtype: None
    """

    # Create the gps_posisjon-string to the correct format.
    gps_posisjon_string = f"srid=4326;POINT Z( {gnss_info['Longitude']} {gnss_info['Latitude']} {gnss_info['Altitude']} )"
    road_info_string_list = image_info["StorageFile"].split(os.sep)
    filename = road_info_string_list[-1]
    strekningsreferanse_list = road_info["RoadIdent"].split(" ")[1]
    strekning = strekningsreferanse_list[1:strekningsreferanse_list.index("D")]
    delstrekning = strekningsreferanse_list[strekningsreferanse_list.index("D") + 1:]
    strekningsreferanse = "/".join([f"S{strekning}", f"D{delstrekning}"])
    for elem in road_info_string_list:
        _get_metadata_from_path_element(elem, parsed_exif)

    _, _, ankerpunkt, \
    kryssdel, sideanleggsdel = process_strekning_and_kryss(filename)
    mappenavn = f"/".join(road_info_string_list[:len(road_info_string_list) - 1])

    # A dictionary to map where the information for each tag is read from.
    exif_tags_lookup_reflink = {
        "exif_roadident": road_info["RoadIdent"],
        "exif_roll": gnss_info["Roll"],
        "exif_pitch": gnss_info["Pitch"],
        "exif_geoidalseparation": gnss_info["GeoidalSeparation"],
        "exif_northrmserror": gnss_info["NorthRmsError"],
        "exif_eastrmserror": gnss_info["EastRmsError"],
        "exif_downrmserror": gnss_info["DownRmsError"],
        "exif_rollrmserror": gnss_info["RollRmsError"],
        "exif_pitchrmserror": gnss_info["PitchRmsError"],
        "exif_headingrmserror": gnss_info["HeadingRmsError"],
        "exif_altitude": gnss_info["Altitude"],
        "exif_moh": gnss_info["Altitude"],
        "exif_fylke": image_info["fylke"] if image_info else None,
        "exif_speed_ms": str(round(float(gnss_info["Speed"]), 2)),
        "exif_gpsposisjon": gps_posisjon_string,
        "exif_heading": gnss_info["Heading"],
        "exif_roadtype": image_info["roadtype"],
        "exif_meter": str(round(float(image_info["meter"]), 2)),
        "exif_strekning": strekning,
        "exif_delstrekning": delstrekning,
        "exif_strekningreferanse": strekningsreferanse,
        "exif_kryssdel": kryssdel,
        "exif_sideanleggsdel": sideanleggsdel,
        "exif_ankerpunkt": ankerpunkt,
        "exif_filnavn": filename,
        "exif_mappenavn": mappenavn
    }

    # Set the a value for each tag.
    # Only set new values to the parsed exif tag if it hasn't already been set.
    for key, value in exif_tags_lookup_reflink.items():
        if value:
            parsed_exif[key] = value


def get_metadata_from_path(image_path, parsed_exif):
    # Use os.stat to get a timestamp.
    file_stat = os.stat(image_path)
    time_created = datetime.fromtimestamp(min([file_stat.st_mtime, file_stat.st_ctime]))
    if parsed_exif["exif_tid"] is None:
        parsed_exif["exif_tid"] = time_created.strftime("%Y-%m-%dT%H:%M:%S.%f")
    if parsed_exif["exif_dato"] is None:
        parsed_exif["exif_dato"] = time_created.strftime("%Y-%m-%d")

    # Process the elements in the image path
    path_elements = image_path.split(os.sep)
    for elem in path_elements:
        _get_metadata_from_path_element(elem, parsed_exif)

    # Set the filename
    parsed_exif["exif_filnavn"] = path_elements[-1]


FELT_REGEX = re.compile(r"f(\d\w*)", re.IGNORECASE)
VEG_REGEX = re.compile(f"([{''.join(LOVLIG_VEGKATEGORI)}])([{''.join(LOVLIG_VEGSTATUS)}])(\d+)", re.IGNORECASE)
METER_REGEX = re.compile(r"(?<!k)m(\d+)")
KILOMETER_REGEX = re.compile(r"km(\d{2})[_,\.](\d{3})")
FYLKE_REGEX = re.compile(r"^(\d{2})\b")
LOVLIGE_FYLKER = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "14", "15", "16", "17", "18",
                  "19", "20", "50"]


def _get_metadata_from_path_element(elem, parsed_exif):
    fylke_matches = FYLKE_REGEX.findall(elem)
    if fylke_matches:
        for m in fylke_matches:
            if m in LOVLIGE_FYLKER:
                parsed_exif["exif_fylke"] = m.lstrip("0")

    felt_matches = FELT_REGEX.findall(elem)
    if felt_matches:
        parsed_exif["exif_feltkode"] = felt_matches[0].lstrip("0")

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
    process_strekning_and_kryss(elem)


def process_gpsinfo_tag(gpsinfo, parsed_exif):
    """
    Prcesses the GPSInfo-tag and creates the gpsposisjon-string for it.
    The values of the GPSInfo is given as a tuple with the nominator and the denominator.
    To get the value in decimal numbers, do the division.
    """
    # Get the *tudes from the tag.
    latitude = gpsinfo['GPSLatitude']
    longitude = gpsinfo["GPSLongitude"]
    altitude = gpsinfo['GPSAltitude']

    # Convert to decimal numbers.
    lat = convert_tude_decimal(latitude)
    long = convert_tude_decimal(longitude)
    alt = altitude[0] / altitude[1]

    # Make sure the decimal is of the correct sign.
    lat = -lat if gpsinfo["GPSLatitudeRef"].strip() == 'S' else lat
    long = -long if gpsinfo["GPSLongitudeRef"].strip() == 'W' else long

    # Create the exif_gposisjon string on the correct format
    parsed_exif["exif_gpsposisjon"] = f"srid=4326;POINT Z( {long} {lat} {alt} )"
    parsed_exif["exif_altitude"] = f"{alt}"

    # Parse the speed information and convert it to m/s
    speed = gpsinfo.get('GPSSpeed', None)
    if speed:
        parsed_exif['exif_speed_ms'] = str(to_ms(speed, gpsinfo['GPSSpeedRef'].strip()))

    # Parse the direction information.
    direction = gpsinfo.get('GPSImgDirection', None)
    if direction:
        parsed_exif['exif_heading'] = direction[0] / direction[1]


def to_ms(speed, speed_ref):
    """
    Converts the speed value of speed_ref to m/s.

    """
    # Denominator for m/s conversion.
    # K: Km/h
    # M: Mph
    # N: Knots
    denominator = {
        # This is an error with the tagging. The ref is K, while the speed value is in m/s.
        # If this is fixed, the denominator for 'K' should be 3.6
        'K': 1,
        'M': 2.237,
        'N': 1.944
    }
    speed = speed[0] / speed[1]
    m_s = speed / denominator[speed_ref]
    return m_s


def convert_tude_decimal(tude):
    """
    Converts a *tude (longitude or latitude) on the form (degrees, hours, minutes)
    to a decimal number.
    """
    decimal_tude = [float(x) / float(y) for x, y in tude]
    decimal_tude = decimal_tude[0] + decimal_tude[1] / 60 + decimal_tude[2] / 3600
    return decimal_tude
