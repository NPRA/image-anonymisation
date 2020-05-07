class SDOGeometry:
    """
    Intermediate class to represent SDO_GEOMETRY objects. If an object of this class is inserted with a
    `src.db.DatabaseClient.connect` connection, it will be converted to an SDO_GEOMETRY object before insertion.
    Conversion is done using the converter returned by `src.db.geometry.get_geometry_converter`.
    See https://docs.oracle.com/database/121/SPATL/sdo_geometry-object-type.htm#SPATL489 for a description of the
    parameters

    :param gtype: SDO_GTYPE
    :type gtype: int | None
    :param srid: SDO_SRID
    :type srid: int | None
    :param point: SDO_POINT
    :type point: list of (int | float) | None
    :param elem_info: SDO_ELEM_INFO
    :type elem_info: list of int | None
    :param ordinates: SDO_ORDINATES
    :type ordinates: list of (int | float) | None
    """
    def __init__(self, gtype=None, srid=None, point=None, elem_info=None, ordinates=None):
        self.gtype = gtype
        self.srid = srid
        self.point = point
        self.elem_info = elem_info
        self.ordinates = ordinates

    def __str__(self):
        return "SDOGeometry({})".format(", ".join(f"{k}={v}" for k, v in self.__dict__.items()))

    def __repr__(self):
        return self.__str__()


def get_geometry_converter(connection):
    """
    Get a converter for SDO_GEOMETRY objects which can be used in input type handlers.

    :param connection: Connection to the database
    :type connection: cx_Oracle.Connection
    :return: Conversion function which accepts a `src.db.geometry.SDOGeometry` instance, an returns an SDO_GEOMETRY
             object.
    :rtype: function
    """
    # Get types
    geometry_obj_type = connection.gettype("MDSYS.SDO_GEOMETRY")
    element_info_type = connection.gettype("MDSYS.SDO_ELEM_INFO_ARRAY")
    ordinate_type = connection.gettype("MDSYS.SDO_ORDINATE_ARRAY")
    point_type = connection.gettype("MDSYS.SDO_POINT_TYPE")

    # Conversion function
    def _converter(value):
        # Create object
        obj = geometry_obj_type.newobject()

        # Set values of object
        obj.SDO_GTYPE = value.gtype
        obj.SDO_SRID = value.srid

        if value.point is not None:
            obj.SDO_POINT = point_type.newobject()
            # Assign X and Y
            obj.SDO_POINT.X, obj.SDO_POINT.Y = value.point[:2]
            # Assign Z if we got a third coordinate
            if len(value.point) > 2:
                obj.SDO_POINT.Z = value.point[2]

        if value.elem_info is not None:
            obj.SDO_ELEM_INFO = element_info_type.newobject()
            obj.SDO_ELEM_INFO.extend(value.elem_info)

        if value.ordinates is not None:
            obj.SDO_ORDINATES = ordinate_type.newobject()
            obj.SDO_ORDINATES.extend(value.ordinates)

        return obj

    return _converter, geometry_obj_type
