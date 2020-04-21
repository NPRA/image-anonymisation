class SDOGeometry:
    def __init__(self, gtype, srid, elem_info, ordinates):
        self.gtype = gtype
        self.srid = srid
        self.elem_info = elem_info
        self.ordinates = ordinates

    def __str__(self):
        return "SDOGeometry({})".format(", ".join(f"{k}={v}" for k, v in self.__dict__.items()))

    def __repr__(self):
        return self.__str__()


def get_geometry_converter(connection):
    # Get types
    obj_type = connection.gettype("MDSYS.SDO_GEOMETRY")
    element_info_type_obj = connection.gettype("MDSYS.SDO_ELEM_INFO_ARRAY")
    ordinate_type_obj = connection.gettype("MDSYS.SDO_ORDINATE_ARRAY")

    def _converter(value):
        # Create object
        obj = obj_type.newobject()
        obj.SDO_ELEM_INFO = element_info_type_obj.newobject()
        obj.SDO_ORDINATES = ordinate_type_obj.newobject()
        # Set values of object
        obj.SDO_GTYPE = value.gtype
        obj.SDO_SRID = value.srid
        obj.SDO_ELEM_INFO.extend(value.elem_info)
        obj.SDO_ORDINATES.extend(value.ordinates)
        return obj

    return _converter, obj_type
