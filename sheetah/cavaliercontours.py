import ctypes, pathlib
from copy import copy
import numpy as np

libname = pathlib.Path().absolute() / "libCavalierContours.so"
c_lib = ctypes.CDLL(libname)
c_lib.cavc_get_path_length.restype = ctypes.c_double
c_lib.cavc_get_area.restype = ctypes.c_double

# TODO use instead of ctypes.c_double * 3
# class VertexStruct(ctypes.Structure):
#     _fields_ = [('x', ctypes.c_double),
#                 ('y', ctypes.c_double),
#                 ('bulge', ctypes.c_double)]

class PointStruct(ctypes.Structure):
    _fields_ = [('x', ctypes.c_double),
                ('y', ctypes.c_double)]

class CAVCPolyline:
    def __init__(self, vertices, closed):
        vertices = np.array(vertices)
        if not vertices.flags['C_CONTIGUOUS']:
            vertices = vertices.copy()
        vertex_data = vertices.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
        vertex_count = ctypes.c_uint32(vertices.shape[0])
        is_closed = ctypes.c_int(closed)
        self.c_pline_ptr = c_lib.cavc_pline_new(vertex_data, vertex_count,
                                                is_closed)

    def __del__(self):
        c_lib.cavc_pline_delete(self.c_pline_ptr)

    def vertex_count(self):
        return c_lib.cavc_pline_vertex_count(self.c_pline_ptr)

    def vertex_data(self):
        vertex_data = (ctypes.c_double * 3 * self.vertex_count())()
        c_lib.cavc_pline_vertex_data(self.c_pline_ptr, vertex_data)
        return np.ctypeslib.as_array(vertex_data)

    def is_closed(self):
        return bool(c_lib.cavc_pline_is_closed(self.c_pline_ptr))

    def parallel_offset(self, delta, option_flags):
        delta = ctypes.c_double(delta)
        ret_ptr = ctypes.pointer(ctypes.c_void_p())
        flags = ctypes.c_int(option_flags)
        c_lib.cavc_parallel_offet(self.c_pline_ptr, delta, ret_ptr, flags)
        pline_list = ret_ptr.contents

        # explodes list into python objects that can free memory themselves
        pline_count = c_lib.cavc_pline_list_count(pline_list)
        plines = []
        for i in range(pline_count):
            c_pline_ptr = c_lib.cavc_pline_list_release(pline_list, 0)
            pline = copy(self) # skip constructor
            pline.c_pline_ptr = c_pline_ptr
            plines.append(pline)
        c_lib.cavc_pline_list_delete(pline_list)
        return plines

    def get_path_length(self):
        return c_lib.cavc_get_path_length(self.c_pline_ptr)

    def get_area(self):
        return c_lib.cavc_get_area(self.c_pline_ptr)

    def get_winding_number(self, point):
        c_point = PointStruct(point[0], point[1])
        return c_lib.cavc_get_winding_number(self.c_pline_ptr, c_point)

    def get_extents(self):
        min_x = ctypes.pointer(ctypes.c_double())
        min_y = ctypes.pointer(ctypes.c_double())
        max_x = ctypes.pointer(ctypes.c_double())
        max_y = ctypes.pointer(ctypes.c_double())
        c_lib.cavc_get_extents(self.c_pline_ptr, min_x, min_y, max_x, max_y)
        return np.array([[min_x.contents.value, min_y.contents.value],
                         [max_x.contents.value, max_y.contents.value]])
