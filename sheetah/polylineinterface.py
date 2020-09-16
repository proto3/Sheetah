from abc import ABC, abstractmethod, abstractproperty

class PolylineInterface(ABC):
    @abstractproperty
    def raw(self):
        pass

    @abstractproperty
    def start(self):
        pass

    @abstractproperty
    def end(self):
        pass

    @abstractproperty
    def bounds(self):
        pass

    @abstractmethod
    def is_closed(self):
        pass

    @abstractmethod
    def is_ccw(self):
        pass

    @abstractmethod
    def is_simple(self):
        pass

    @abstractmethod
    def reverse(self):
        pass

    @abstractmethod
    def contains(self, object):
        pass

    @abstractmethod
    def intersects(self, polyline):
        pass

    @abstractmethod
    def affine(self, d, r, s):
        pass

    @abstractmethod
    def offset(self, offset):
        pass

    @abstractmethod
    def to_lines(self):
        pass

    # @abstractmethod
    # def to_gcode(self):
    #     pass

## STATIC METHODS ##
# def line2polyline(start, end):
#     pass
#
# def arc2polyline(center, radius, rad_start, rad_end):
#     pass
#
# def circle2polyline(center, radius):
#     pass
#
# def spline2polyline(degree, control_points, closed):
#     pass
#
# def aggregate(polylines):
#     pass
#
# def group_as_contours(polylines):
#     pass
