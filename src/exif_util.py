"""From: https://github.com/vegvesen/vegbilder/blob/master/trinn1_lagmetadata/vegbilder_lesexif.py"""
import xml.dom.minidom
import uuid
import json
import re
from copy import deepcopy

from PIL import Image # Må installeres, pakken heter PILLOW
from PIL.ExifTags import TAGS, GPSTAGS
import xmltodict # Må installeres, rett fram

from src.Logger import LOGGER


def get_exif(img, image_path):
    # img.verify()
    exif = img._getexif()
    if exif is None:
        LOGGER.error(__name__, f"No EXIF data found for file {image_path}.")
        exif = {}

    labeled = get_labeled_exif(exif)

    # Fisker ut XML'en som er stappet inn som ikke-standard exif element
    xmldata = pyntxml(labeled)
    if xmldata is not None:
        # Fisker ut mer data fra viatech xml
        viatekmeta = fiskFraviatechXML(xmldata)
    else:
        err_msg = f"Unable to clean XML-data for file {image_path}."
        LOGGER.error(__name__, err_msg, save=True)
        viatekmeta = {}

    # Bildetittel - typisk etelleranna med viatech Systems
    XPTitle = ''
    if 'XPTitle' in labeled.keys():
        XPTitle = labeled['XPTitle'].decode('utf16')

    viatekmeta['exif_xptitle'] = XPTitle
    viatekmeta['bildeuiid'] = str(uuid.uuid4())
    return viatekmeta


def write_exif(exif, output_filepath):
    with open(output_filepath, "w") as out_file:
        json.dump(exif, out_file, indent=4, ensure_ascii=False)

def fiksutf8( meta):
    """
    Fjerner ugyldige tegn fra datastrukturen før de får gjort mer skade
    """

    kortalfabet = 'abcdefghijklmnopqrstuvwxyz'
    alfabet = kortalfabet + 'æøå'
    tegn  = '0123456789.,:;-_ *+/++<>\\()#?='
    godkjent = tegn + alfabet + alfabet.upper()
    raretegn = False

    tulletegn = set( )
    # Prøver å fikse tegnsett
    if meta and isinstance( meta, dict):
        old = deepcopy( meta)
        for key, value in old.items():
            if isinstance( value, str):
                nystr = ''
                rart = False
                for bokstav in value:
                    if bokstav in godkjent:
                        nystr += bokstav
                    else:
                        tulletegn.add( bokstav)
                        rart = True

                if rart:
                    nystr = nystr.replace( 'Æ', '_')
                    nystr = nystr.replace( 'Å', '_')

                    nystr = re.sub('_{2,}', '_', nystr )

                    raretegn = True
                meta[key] = nystr

    # if len(tulletegn) > 0:
    # print( "Tulletegn: ", tulletegn)

    return meta

def fiskFraviatechXML(imagepropertiesxml):
    """
    Leser relevante data fra viatech XML header.
    """

    # with open( 'imageproperties.xml') as f:
    # imagepropertiesxml  = f.readlines()

    ip = xmltodict.parse( imagepropertiesxml)



    dLat = ip['ImageProperties']['GeoTag']['dLatitude']
    dLon = ip['ImageProperties']['GeoTag']['dLongitude']
    dAlt = ip['ImageProperties']['GeoTag']['dAltitude']

    try:
        heading = ip['ImageProperties']['Heading']
    except KeyError:
        heading = None

    try:
        speed    = ip['ImageProperties']['Speed']
    except KeyError:
        speed = None

    if speed == 'NaN':
        speed = None

    if heading == 'NaN':
        heading == None

    ewkt = ' '.join( [ 'srid=4326;POINT Z(', dLon, dLat, dAlt, ')' ] )

    tidsstempel = ip['ImageProperties']['@Date']
    kortdato = tidsstempel.split('T')[0]
    exif_veg = ip['ImageProperties']['VegComValues']['VCRoad']

    # Pent formatterte mappenavn
    mappenavn = re.sub( r'\\', '/', ip['ImageProperties']['ImageName'] )
    mapper = mappenavn.split('/')

    if len( exif_veg) >= 3:
        exif_vegnr   = exif_veg[2:]
        exif_vegstat = exif_veg[1]
        exif_vegkat  = exif_veg[0]
    else:
        exif_vegnr   = exif_veg
        exif_vegstat = None
        exif_vegkat  = None

    lovlig_vegstatus = ["S", "H", "W", "A", "P", "E", "B", "U", "Q", "V", "X", "M", "T", "G" ]
    lovlig_vegkat = ["E", "R", "F", "K", "P", "S" ]

    if exif_vegstat not in lovlig_vegstatus or exif_vegkat not in lovlig_vegkat:
        # logging.info( ' '.join( [ 'VCRoad=', exif_veg, 'følger ikke KAT+STAT+vegnr syntaks:', mappenavn ] ) )
        print( 'VCRoad=', exif_veg, 'følger ikke KAT+STAT+vegnr syntaks:', mappenavn )


    retval =  {
        'exif_tid' : tidsstempel,
        'exif_dato' : kortdato,
        'exif_speed' : speed,
        'exif_heading' : heading,
        'exif_gpsposisjon' : ewkt,
        'exif_strekningsnavn' : ip['ImageProperties']['VegComValues']['VCArea'],
        'exif_fylke'          : ip['ImageProperties']['VegComValues']['VCCountyNo'],
        'exif_vegkat'        : exif_vegkat,
        'exif_vegstat'       : exif_vegstat,
        'exif_vegnr'         : exif_vegnr,
        'exif_hp'            : ip['ImageProperties']['VegComValues']['VCHP'],
        'exif_meter'            : ip['ImageProperties']['VegComValues']['VCMeter'],
        'exif_feltkode'            : ip['ImageProperties']['VegComValues']['VCLane'],
        'exif_mappenavn'    :  '/'.join( mapper[0:-1] ),
        'exif_filnavn'      : mapper[-1],
        'exif_strekningreferanse' : '/'.join( mapper[-4:-2]),
        'exif_imageproperties'    : imagepropertiesxml

    }

    return retval



def lesexif( filnavn):
    """
    Omsetter Exif-header til metadata for bruk i bildedatabase

    """
    exif = get_exif( filnavn)

    labeled = get_labeled_exif( exif)

    # Fisker ut XML'en som er stappet inn som ikke-standard exif element
    xmldata = pyntxml( labeled)

    # Fisker ut mer data fra viatech xml
    viatekmeta = fiskFraviatechXML( xmldata)

    ## Omsetter Exif GPSInfo => lat, lon desimalgrader, formatterer som EWKT
    ## Overflødig - bruker (lat,lon,z) fra viatech xml
    # try:
    # geotags = get_geotagging(exif)
    # except ValueError:
    # ewkt = ''
    # print( 'kan ikke lese geotag', filnavn)
    # else:
    # (lat, lon) = get_coordinates( geotags)
    # ewkt = 'srid=4326;POINT(' + str(lon) + ' ' + str(lat) + ')'

    # Bildetittel - typisk etelleranna med viatech Systems
    XPTitle = ''
    if 'XPTitle' in labeled.keys():
        XPTitle = labeled['XPTitle'].decode('utf16')

    viatekmeta['exif_xptitle'] = XPTitle

    return viatekmeta

#% -------------------------------------------------------
#
# Hjelpefunksjoner for diverse exif-manipulering
#
# ---------------------------------------------------
def get_decimal_from_dms(dms, ref):
    """
    Konverterer EXIF-grader til desimalgrader

    Fra https://developer.here.com/blog/getting-started-with-geocoding-exif-image-metadata-in-python3
    """


    degrees = dms[0][0] / dms[0][1]
    minutes = dms[1][0] / dms[1][1] / 60.0
    seconds = dms[2][0] / dms[2][1] / 3600.0

    if ref in ['S', 'W']:
        degrees = -degrees
        minutes = -minutes
        seconds = -seconds

    return round(degrees + minutes + seconds, 6)

def get_coordinates(geotags):
    """
    Fisker koordinater ut av EXIF-taggene

    Fra https://developer.here.com/blog/getting-started-with-geocoding-exif-image-metadata-in-python3
    """

    lat = get_decimal_from_dms(geotags['GPSLatitude'], geotags['GPSLatitudeRef'])

    lon = get_decimal_from_dms(geotags['GPSLongitude'], geotags['GPSLongitudeRef'])

    return (lat,lon)

def pyntxml( exif_labelled):
    """
    Fjerner litt rusk fra den XML'en som viatech legger i Exif-header. Obfuskerer fører og bilnr
    """

    try:
        raw = exif_labelled[None]
    except KeyError:
        return None
    else:
        # fjerner '\ufeff' - tegnet aller først i teksten
        xmlstr = raw.decode('utf8')[1:]
        plainxml = xml.dom.minidom.parseString(xmlstr)
        prettyxml = plainxml.toprettyxml()

        # Obfuskerer
        prettyxml = re.sub(r'Driver>.*<', 'Driver>FJERNET<', prettyxml)
        prettyxml = re.sub(r'CarID>.*<', 'CarID>FJERNET<', prettyxml)
        prettyxml = re.sub(r'Comment>.*<', 'Comment>FJERNET<', prettyxml)

        return prettyxml



def get_geotagging(exif):
    """
    Bedre håndtering av geotag i exif-header

    Fra https://developer.here.com/blog/getting-started-with-geocoding-exif-image-metadata-in-python3
    """
    if not exif:
        raise ValueError("No EXIF metadata found")

    geotagging = {}
    for (idx, tag) in TAGS.items():
        if tag == 'GPSInfo':
            if idx not in exif:
                raise ValueError("No EXIF geotagging found")

            for (key, val) in GPSTAGS.items():
                if key in exif[idx]:
                    geotagging[val] = exif[idx][key]

    return geotagging


# def get_exif(filename):
#     image = Image.open(filename)
#     image.verify()
#     return image._getexif()

def get_labeled_exif(exif):

    labeled = {}
    for (key, val) in exif.items():
        labeled[TAGS.get(key)] = val

    return labeled