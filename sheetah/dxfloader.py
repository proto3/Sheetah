import numpy as np
import ezdxf, math
from shapely.geometry.polygon import Polygon, LineString, LinearRing
from shapely.ops import polygonize_full, linemerge
from shapely.affinity import translate
from shapely import wkt

def arc2lines(center, radius, start=None, end=None):
    max_error = 1e-2
    max_angle = 2 * math.acos(1.0 - max_error / radius)
    is_circle = False
    if start is None or end is None:
        is_circle = True
        start = 0.
        end = 2 * math.pi
        nb_segments = max(2, math.ceil(2 * math.pi / max_angle) + 1)
    else:
        if end < start:
            end += math.pi*2
        arc = math.fmod((end - start) + 2 * math.pi, 2 * math.pi)
        nb_segments = max(2, math.ceil(arc / max_angle) + 1)
    theta = np.linspace(start, end, nb_segments + 1)
    x = center[0] + radius * np.cos(theta)
    y = center[1] + radius * np.sin(theta)
    if is_circle:
        return np.column_stack([x, y])[:-1]
    else:
        return np.column_stack([x, y])

def bulge2lines(a, b, bulge):
    rot = np.array([[0,-1],
                    [1, 0]])
    on_right = bulge >= 0
    if not on_right:
        rot = -rot
    bulge = abs(bulge)
    ab = b-a
    d = np.linalg.norm(ab)
    r = d * (bulge + 1. / bulge) / 4
    center_offset = r - d * bulge / 2
    center_pos = a + ab/2 + center_offset / d * rot.dot(ab)
    a_dir = a - center_pos
    b_dir = b - center_pos
    a_angle = math.atan2(a_dir[1], a_dir[0])
    b_angle = math.atan2(b_dir[1], b_dir[0])
    if on_right:
        return arc2lines(center_pos, r, start=a_angle, end=b_angle)
    else:
        return np.flip(arc2lines(center_pos, r, start=b_angle, end=a_angle),
                       axis=0)
def spline2lines(spline):
    epsilon = 1e-2

    t = np.linspace(0.0, 1.0, num=4).reshape(4,1)
    points = (spline[0] * (1-t)**3 +
              spline[1] * 3 * t * (1-t)**2 +
              spline[2] * 3 * t**2 * (1-t) +
              spline[3] * t**3)

    i = 1
    curve_data = np.hstack((t, points)).transpose()
    while i < np.size(curve_data, 1):
        t_mid = (curve_data[0][i] + curve_data[0][i-1]) / 2

        a = curve_data[1:,i-1]
        b = curve_data[1:,i]
        c = (spline[0] * (1-t_mid)**3 +
             spline[1] * 3 * t_mid * (1-t_mid)**2 +
             spline[2] * 3 * t_mid**2 * (1-t_mid) +
             spline[3] * t_mid**3)
        ab = b - a
        ac = c - a
        ac_proj_in_ab = np.sum(ab * ac, axis=0) / np.sum(np.square(ab), axis=0)
        dist_to_curve = np.linalg.norm(ac_proj_in_ab * ab - ac, axis=0)

        if dist_to_curve > epsilon:
            curve_data = np.insert(curve_data, i, [t_mid, c[0], c[1]], axis=1)
        else:
            i += 1

    return curve_data[1:]

class DXFLoader:
    def load(filename):
        dwg = ezdxf.readfile(filename)
        msp = dwg.modelspace()
        geom_list = list()

        for e in msp:
            if e.dxftype() == 'LINE':
                path = (e.dxf.start[:2], e.dxf.end[:2])
                DXFLoader._store_geom(geom_list, LineString(path))
            elif e.dxftype() == 'ARC':
                start = e.dxf.start_angle * math.pi / 180
                end = e.dxf.end_angle * math.pi / 180
                path = arc2lines(e.dxf.center[:2], e.dxf.radius, start, end)
                DXFLoader._store_geom(geom_list, LineString(path))
            elif e.dxftype() == 'CIRCLE':
                path = arc2lines(e.dxf.center[:2], e.dxf.radius)
                DXFLoader._store_geom(geom_list, LinearRing(path))
            elif e.dxftype() == 'LWPOLYLINE':
                points = np.array(e.get_points())
                path = np.empty((0,2))
                for i in range(len(points)-1):
                    line = points[i:i+2,:2]
                    bulge = points[i][4]
                    if bulge != 0:
                        line = bulge2lines(line[0], line[1], bulge)
                    path = np.vstack((path[:-1], line))
                if e.closed:
                    if points[-1][4] != 0:
                        a = points[-1][:2]
                        b = points[0][:2]
                        bulge = points[-1][4]
                        path = np.vstack((path[:-1], bulge2lines(a, b, bulge)))
                    DXFLoader._store_geom(geom_list, LinearRing(path))
                else:
                    DXFLoader._store_geom(geom_list, LineString(path))
            elif e.dxftype() == 'SPLINE':
                if e.dxf.degree != 3:
                    raise Exception('Only cubic splines are implemented.')
                if e.dxf.n_control_points != 4:
                    raise Exception('Only 4 control points splines are implemented.')
                if e.closed:
                    raise Exception('Only open splines are implemented.')
                path = spline2lines(np.array(e.control_points)[:,:2])
                DXFLoader._store_geom(geom_list, LineString(path.transpose()))
            else:
                raise Exception('unimplemented \"'+e.dxftype()+'\" dxf entity.')

        # extract polygons from the geoms list
        result, dangles, cuts, invalids = polygonize_full(geom_list)
        polygons = list(result)

        # look for open paths in the remaining geoms
        lines = linemerge(list(cuts))
        if isinstance(lines, LineString):
            lines = [lines]
        else:
            lines = list(lines)

        if list(invalids):
            raise Exception('found invalid geometry (mobius loop, etc).')

        if not polygons and not lines:
            raise Exception('no geometry found.')

        # flatten polygons exterior/interior hierarchy
        for i, p in enumerate(polygons):
            if p.interiors:
                polygons[i] = Polygon(p.exterior.coords)

        # fail on self crossing lines
        for line in lines:
            if not line.is_simple:
                raise Exception('found self crossing lines.')

        # fail on overlapping geoms
        elements = polygons + lines
        for i, a in enumerate(elements):
            for b in elements[i+1:]:
                if a.intersects(b) and not a.contains(b) and not b.contains(a):
                    raise Exception('found overlapping geoms.')

        parts = list()
        if polygons:
            hierarchy = [(elements[0], [])]
            for p in elements[1:]:
                DXFLoader.append_to_hierarchy(hierarchy, p)
            hierarchy = DXFLoader.extract_subparts(hierarchy)
            for node in hierarchy:
                if isinstance(node[0], LineString):
                    x, y, _, _ = node[0].bounds
                    line = translate(node[0], xoff=-x, yoff=-y)
                    parts.append((None, [line]))
                else:
                    paths = [e[0] for e in node[1]
                             if isinstance(e[0], LineString)]
                    holes = [LinearRing(e[0].exterior) for e in node[1]
                             if isinstance(e[0], Polygon)]
                    polygon = Polygon(LinearRing(node[0].exterior), holes)
                    if not polygon.is_valid:
                        raise Exception(
                            'invalid polygon (see shapely definition).')
                    x, y, _, _ = polygon.exterior.bounds
                    polygon = translate(polygon, xoff=-x, yoff=-y)
                    paths = [translate(l, xoff=-x, yoff=-y) for l in paths]
                    parts.append((polygon, paths))
        else:
            for line in lines:
                x, y, _, _ = line.bounds
                line = translate(line, xoff=-x, yoff=-y)
                parts.append((None, [line]))

        return parts

    def append_to_hierarchy(hierarchy, geom):
        children_id = list()
        for i, node in enumerate(hierarchy):
            if geom.contains(node[0]):
                children_id.append(i)
        if children_id:
            children = list()
            for i in sorted(children_id, reverse=True):
                children.append(hierarchy.pop(i))
            hierarchy.append((geom, children))
            return

        for node in hierarchy:
            if node[0].contains(geom):
                DXFLoader.append_to_hierarchy(node[1], geom)
                return

        hierarchy.append((geom, []))

    def extract_subparts(hierarchy):
        flatten = list()
        while hierarchy:
            subparts = list()
            for ext_bloc in hierarchy:
                flatten.append((ext_bloc[0], []))
                for int_bloc in ext_bloc[1]:
                    flatten[-1][1].append((int_bloc[0], []))
                    if int_bloc[1]:
                        subparts += int_bloc[1]
            hierarchy = subparts
        return flatten

    def _store_geom(elt_list, elt):
        elt_list.append(wkt.loads(wkt.dumps(elt, rounding_precision=3)))
