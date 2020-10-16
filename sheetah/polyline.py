#!/usr/bin/env python3
from copy import copy
import math
import numpy as np

# required by aggregate
from random import shuffle

from geomdl import BSpline
from geomdl import utilities
from polylineinterface import PolylineInterface

from cavaliercontours import CAVCPolyline

from shapely.geometry.polygon import Polygon, LineString

class Polyline(PolylineInterface):
    def __init__(self, vertices, closed):
        self._vertices = np.array(vertices)

        # delete zero length lines
        dup = np.all(np.isclose(self._vertices[:-1,:2], self._vertices[1:,:2]), axis=1)
        dup = np.append(dup, False)
        self._vertices = self._vertices[~dup,:]

        if self._vertices.size > 0:
            assert(len(self._vertices.shape) == 2)
            assert(self._vertices.shape[1] == 3)

        self._closed = closed

        self._cavc_up_to_date = False
        self._shapely_up_to_date = False
        self._lines_up_to_date = False

    def _update_cavc(self):
        if self._cavc_up_to_date:
            return
        self._cavc_pline = CAVCPolyline(self._vertices, self._closed)
        self._cavc_up_to_date = True

    def _update_shapely(self):
        # TODO remove np transpose cleanly
        if self._shapely_up_to_date:
            return
        if self.is_closed():
            self._shapely = Polygon(np.transpose(self.to_lines()))
        else:
            self._shapely = LineString(np.transpose(self.to_lines()))
        self._shapely_up_to_date = True

    def _update_lines(self):
        if self._lines_up_to_date:
            return

        precision = 1e-3
        points = []
        n = self._vertices.shape[0]
        for i in range(n - int(not self._closed)):
            a = self._vertices[i,:2]
            b = self._vertices[(i+1)%n,:2]
            bulge = self._vertices[i,2]
            if points:
                points.pop(-1)
            if math.isclose(bulge, 0):
                points += [a, b]
            else:
                rot = np.array([[0,-1],
                                [1, 0]])
                on_right = bulge >= 0
                if not on_right:
                    rot = -rot
                bulge = abs(bulge)
                ab = b-a
                chord = np.linalg.norm(ab)
                radius = chord * (bulge + 1. / bulge) / 4
                center_offset = radius - chord * bulge / 2
                center = a + ab/2 + center_offset / chord * rot.dot(ab)

                a_dir = a - center
                b_dir = b - center
                rad_start = math.atan2(a_dir[1], a_dir[0])
                rad_end   = math.atan2(b_dir[1], b_dir[0])

                # TODO handle case where bulge almost 0 or inf (line or circle)
                if not math.isclose(rad_start, rad_end):
                    if on_right != (rad_start < rad_end):
                        if on_right:
                            rad_start -= 2*math.pi
                        else:
                            rad_end -= 2*math.pi

                    rad_len = abs(rad_end - rad_start)
                    if radius > precision:
                        max_angle = 2 * math.acos(1.0 - precision / radius)
                    else:
                        max_angle = math.pi
                    nb_segments = max(2, math.ceil(rad_len / max_angle) + 1)

                    angles = np.linspace(rad_start, rad_end, nb_segments + 1)
                    arc_data = (center.reshape(2,1) + radius *
                                np.vstack((np.cos(angles), np.sin(angles))))
                    points += np.transpose(arc_data).tolist()
        self._lines = np.transpose(np.array(points))
        self._lines_up_to_date = True

    @property
    def raw(self):
        return self._vertices

    @property
    def start(self):
        return self._vertices[0][:2]

    @property
    def end(self):
        return self._vertices[-1][:2]

    @property
    def bounds(self):
        self._update_cavc()
        return self._cavc_pline.get_extents()

    @property
    def centroid(self):
        self._update_shapely()
        return self._shapely.centroid

    def is_closed(self):
        return self._closed

    def is_ccw(self):
        self._update_cavc()
        return self._cavc_pline.get_area() >= 0

    # TODO
    def is_simple(self):
        return True

    def reverse(self):
        polyline = copy(self)
        polyline._cavc_pline = None
        polyline._cavc_up_to_date = False
        polyline._shapely_up_to_date = False
        polyline._lines_up_to_date = False
        polyline._vertices = np.flip(polyline._vertices, axis=0)
        polyline._vertices[:,2] = -polyline._vertices[:,2]
        if polyline._closed:
            polyline._vertices[:,:2] = np.roll(polyline._vertices[:,:2], 1, axis=0)
        else:
            polyline._vertices[:,2] = np.roll(polyline._vertices[:,2], -1, axis=0)
            polyline._vertices[-1,2] = 0.
        return polyline


    def contains(self, object):
        if not self._closed:
            return False
        if isinstance(object,(list, np.ndarray)):
            point = np.array(object)
            self._update_cavc()
            return self._cavc_pline.get_winding_number(object) != 0
        elif isinstance(object, Polyline):
            self._update_shapely()
            object._update_shapely()
            return self._shapely.contains(object._shapely)
        else:
            raise Exception('Incorrect argument type')

    def intersects(self, polyline):
        self._update_shapely()
        polyline._update_shapely()
        return self._shapely.intersects(polyline._shapely)

    def affine(self, d, r, s):
        polyline = copy(self)
        polyline._cavc_pline = None
        polyline._cavc_up_to_date = False
        polyline._shapely_up_to_date = False
        polyline._lines_up_to_date = False
        r_rad = r / 180 * math.pi
        cos = math.cos(r_rad) * s
        sin = math.sin(r_rad)
        tr_mat = np.array([[cos,-sin, d[0]],
                           [sin, cos, d[1]],
                           [  0,   0,    1]])
        polyline._vertices = polyline._vertices.transpose()
        vert = polyline._vertices[:-1]
        vert = np.dot(tr_mat, np.insert(vert, 2, 1., axis=0))
        vert[-1] = polyline._vertices[-1]
        polyline._vertices = vert.T

        return polyline

    def offset(self, offset):
        self._update_cavc()
        cavc_plines = self._cavc_pline.parallel_offset(offset, 0)
        polylines = []
        for cp in cavc_plines:
            polyline = copy(self)
            polyline._cavc_pline = cp
            polyline._cavc_up_to_date = True
            polyline._shapely_up_to_date = False
            polyline._lines_up_to_date = False
            polyline._vertices = cp.vertex_data()
            polyline._closed = cp.is_closed()
            polylines.append(polyline)
        return polylines

    def loop(self, limit_angle, selected_radius, loop_radius):
        polyline = copy(self)
        polyline._cavc_pline = None
        polyline._cavc_up_to_date = False
        polyline._shapely_up_to_date = False
        polyline._lines_up_to_date = False

        # prepare for later representation
        polyline._vertices = np.copy(polyline._vertices.transpose())

        limit_bulge = math.tan((math.pi - limit_angle) / 4)
        ids = np.where(np.abs(polyline._vertices[2]) >= limit_bulge)[0]

        cur = np.take(polyline._vertices, ids, axis=1)
        next_ids = (ids+1)%polyline._vertices.shape[1]
        next = np.take(polyline._vertices[:2], next_ids, axis=1)

        # i, x, y, b, h_theta, vx, vy
        data = np.vstack((ids, cur, 2*np.arctan(np.abs(cur[2])), next-cur[:2]))

        # i, x, y, b, h_theta, vx, vy, d
        data = np.vstack((data, np.linalg.norm(data[-2:], axis=0)))

        radius = data[7] / (2 * np.sin(data[4]))
        ignored = np.where(np.logical_not(np.isclose(radius, selected_radius)))[0]
        data = np.delete(data, ignored, axis=1)

        # i, x, y, b, h_theta, vx, vy, d, h
        data = np.vstack((data, (data[7] + 2 * loop_radius * np.sin(data[4])) * np.tan(data[4]) / 2))

        a = data[1:3]
        ab = data[5:7]
        normalized_ab = ab / data[7]
        ab_normal = np.array([-normalized_ab[1], normalized_ab[0]])
        h = data[8]
        top = a + ab / 2 + ab_normal * h
        half_top_side = loop_radius * np.sin(data[4])
        new_a = top + normalized_ab * half_top_side
        new_b = top - normalized_ab * half_top_side

        new_b = np.insert(new_b, 2, 0, axis=0)
        new_a = np.vstack((new_a, -1/data[3]))
        for i in reversed(range(data.shape[1])):
            id = int(data[0, i] + 0.1)
            polyline._vertices[2, id] = 0

            polyline._vertices = np.insert(polyline._vertices, id+1, new_b[:,i], axis=1)
            polyline._vertices = np.insert(polyline._vertices, id+1, new_a[:,i], axis=1)

        polyline._vertices = polyline._vertices.transpose()
        return polyline


    def to_lines(self):
        self._update_lines()
        return self._lines

    # def to_gcode(self):
    #     pass

def line2polyline(start, end):
    return Polyline(np.insert([start, end], 2, 0., axis=1), False)

def arc2polyline(center, radius, rad_start, rad_end):
    #TODO numpify
    bulge = math.tan(math.fmod(rad_end - rad_start + 2*math.pi, 2*math.pi) / 4)
    # bulge = tan(remainder(end - start, 2*pi) / 4)
    vertices = [[center[0] + radius * math.cos(rad_start),
                 center[1] + radius * math.sin(rad_start), bulge],
                [center[0] + radius * math.cos(rad_end),
                 center[1] + radius * math.sin(rad_end), 0]]
    return Polyline(vertices, False) # TODO sure not closed ?

def circle2polyline(center, radius):
    #TODO numpify
    # use two bulges to draw a circle
    vertices = [[center[0] + radius, center[1], 1],
                [center[0] - radius, center[1], 1]]
    return Polyline(vertices, True)

# TODO replace with biarc
def spline2polyline(degree, control_points, closed):
    epsilon = 1e-2
    spline = BSpline.Curve()
    spline.degree = degree
    spline.ctrlpts = control_points
    if closed:
        spline.ctrlpts += spline.ctrlpts[:spline.degree]
        m = spline.degree + len(spline.ctrlpts)
        spline.knotvector = [i/m for i in range(m+1)]
        curve_range = (spline.knotvector[spline.degree], spline.knotvector[len(spline.ctrlpts)])
        nb_seg_init = len(spline.ctrlpts)
    else:
        spline.knotvector = utilities.generate_knot_vector(spline.degree, len(spline.ctrlpts))
        curve_range = (0, 1)
        nb_seg_init = len(spline.ctrlpts) - 1

    t = np.linspace(curve_range[0], curve_range[1], num=nb_seg_init)
    curve_data = np.hstack((t.reshape(nb_seg_init,1), np.array(spline.evaluate_list(t))))
    curve_data = np.transpose(curve_data)
    i = 1
    while i < np.size(curve_data, 1):
        t_mid = (curve_data[0][i] + curve_data[0][i-1]) / 2
        a = curve_data[1:,i-1]
        b = curve_data[1:,i]
        c = spline.evaluate_single(t_mid)
        ab = b - a
        ac = c - a
        ac_proj_in_ab = np.sum(ab * ac, axis=0) / np.sum(np.square(ab), axis=0)
        dist_to_curve = np.linalg.norm(ac_proj_in_ab * ab - ac, axis=0)

        if dist_to_curve > epsilon:
            curve_data = np.insert(curve_data, i, [t_mid, c[0], c[1]], axis=1)
        else:
            i += 1
    curve_data = np.transpose(curve_data[1:])
    vertices = np.insert(curve_data, 2, 0., axis=1)
    if closed:
        return Polyline(vertices[:-1], True)
    else:
        return Polyline(vertices, False)

# AGGREGATOR ###################################################################
class EdgeConnector:
    def polyline2connectors(polyline):
        a = EdgeConnector(polyline, True)
        b = EdgeConnector(polyline, False)
        a.opp_end = b
        b.opp_end = a
        return (a, b)

    def __init__(self, polyline, forward):
        self.pos = polyline.start if forward else polyline.end
        self.opp_end = None
        self.next = None
        self.marked = False
        self._polyline = polyline
        self._forward = forward

    def connect(self, other):
        self.next = other
        other.next = self

    def disconnect(self):
        if self.next is not None:
             self.next.next = None
        self.next = None

    def connected(self):
        return self.next is not None

    def mark(self):
        self.marked = True
        if self.next is not None:
            self.next.marked = True

    def polyline(self):
        if self._forward:
            return self._polyline
        else:
            return self._polyline.reverse()

class KdTree:
    def __init__(self, connector, split_dir=True, precision=1e-2):
        self._connectors = [connector]
        self._split_dir = split_dir # True is for vertical
        self._precision = precision
        self._pos = connector.pos
        self._tl_child = self._br_child = None
        self._complex_joint = False

    def insert(self, connector):
        if np.allclose(connector.pos, self._pos, atol=self._precision):
            if not self._complex_joint:
                if len(self._connectors) == 2:
                    self._complex_joint = True
                    for e in self._connectors:
                        e.disconnect()
                else:
                    connector.connect(self._connectors[0])
            self._connectors.append(connector)
            return

        if self._split_dir: # vertical split
            tl = connector.pos[0] < self._pos[0]
        else: # horizontal split
            tl = connector.pos[1] > self._pos[1]

        if tl:
            if self._tl_child is not None:
                self._tl_child.insert(connector)
            else:
                self._tl_child = KdTree(connector, not self._split_dir)
        else:
            if self._br_child is not None:
                self._br_child.insert(connector)
            else:
                self._br_child = KdTree(connector, not self._split_dir)

def aggregate(polylines):
    ready_polylines = [p for p in polylines if p._closed]
    open_polylines = [p for p in polylines if not p._closed]
    if not open_polylines:
        return ready_polylines

    # shuffle polylines to ensure KdTree correct distribution
    shuffle(open_polylines)

    connectors = []
    for p in open_polylines:
        connectors += EdgeConnector.polyline2connectors(p)
    tree = KdTree(connectors[0])
    for c in connectors[1:]:
        tree.insert(c)

    updated = True
    while updated:
        updated = False
        for c in connectors:
            if not c.connected() and not c.marked: # unprocessed single end
                parts = []
                updated = True
                current = c
                current.mark()
                while current is not None:
                    parts.append(current.polyline())
                    current = current.opp_end
                    current.mark()
                    current = current.next
                if len(parts) > 1:
                    vertices = np.vstack([p._vertices[:-1] for p in parts[:-1]])
                    vertices = np.vstack((vertices, parts[-1]._vertices))
                    if np.allclose(vertices[0,:2], vertices[-1, :2], atol=1e-3):
                        closed = True
                        vertices = np.delete(vertices, -1, axis=0)
                    else:
                        closed = False
                    ready_polylines.append(Polyline(vertices, closed))
                else:
                    ready_polylines.append(parts[0])
        if not updated: # no more single ends
            for c in connectors: # look for a loop and cut it open
                if c.connected() and not c.marked:
                    c.disconnect()
                    updated = True
                    break
    return ready_polylines
# !AGGREGATOR #################################################################
class HierarchyNode:
    def __init__(self, polyline):
        self._polyline = polyline
        self._children = []

    def polyline(self):
        return self._polyline

    def is_closed(self):
        return self._polyline._closed

    def contains(self, other):
        return self._polyline.contains(other._polyline)

    def add_child(self, child):
        self._children.append(child)

    def children(self):
        return self._children

def append_to_hierarchy(hierarchy, node):
    children_id = []
    for i, n in enumerate(hierarchy):
        if node.contains(n):
            children_id.append(i)
    if children_id:
        for i in sorted(children_id, reverse=True):
            node.add_child(hierarchy.pop(i))
        hierarchy.append(node)
        return

    for n in hierarchy:
        if n.contains(node):
            append_to_hierarchy(n.children(), node)
            return

    hierarchy.append(node)

def extract_groups(hierarchy):
    groups = []
    while hierarchy:
        sublevel_hierarchy = []
        for exterior in hierarchy:
            group = [exterior.polyline()]
            for interior in exterior.children():
                group.insert(0, interior.polyline())
                if interior.children():
                    sublevel_hierarchy += interior.children()
            groups.append(group)
        hierarchy = sublevel_hierarchy
    return groups

def group_as_contours(polylines):
    hierarchy = [HierarchyNode(polylines[0])]
    for polyline in polylines[1:]:
        append_to_hierarchy(hierarchy, HierarchyNode(polyline))
    groups = extract_groups(hierarchy)
    return groups
