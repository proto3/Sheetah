import numpy as np
import ezdxf, math
from shapely.geometry.polygon import Polygon, LineString, LinearRing
from shapely.ops import polygonize_full
import shapely.wkt

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
            else:
                raise Exception('unimplemented \"'+e.dxftype()+'\" dxf entity.')

        result, dangles, cuts, invalids = polygonize_full(geom_list)
        polygons = list(result)

        # print('dangles ', list(dangles))
        # print('cuts', list(cuts))
        if list(invalids):
            raise Exception('found invalid geometry (mobius loop, etc).')

        if not polygons:
            raise Exception('no polygon found.')

        # retrieve interior assigned by polygonize to create multilevel hierarchy
        for i, p in enumerate(polygons):
            if p.interiors:
                polygons[i] = Polygon(p.exterior.coords)

        # fail on overlapped contours
        for i, a in enumerate(polygons):
            for b in polygons[i+1:]:
                if a.overlaps(b):
                    raise Exception('overlapping polygons.')

        hierarchy = [(polygons[0], [])]
        for p in polygons[1:]:
            DXFLoader.append_to_hierarchy(hierarchy, p)

        hierarchy = DXFLoader.extract_subparts(hierarchy)

        final_polygons = list()
        for block in hierarchy:
            holes = [LinearRing(b[0].exterior) for b in block[1]]
            polygon = Polygon(LinearRing(block[0].exterior), holes)
            x, y, _, _ = polygon.exterior.bounds
            polygon = shapely.affinity.translate(polygon, xoff=-x, yoff=-y)
            if not polygon.is_valid:
                raise Exception('invalid polygon (see shapely definition).')

            final_polygons.append(polygon)

        return final_polygons

    def append_to_hierarchy(hierarchy, polygon):
        children_id = list()
        for i, block in enumerate(hierarchy):
            if polygon.contains(block[0]):
                children_id.append(i)
        if children_id:
            children = list()
            for i in sorted(children_id, reverse=True):
                children.append(hierarchy.pop(i))
            hierarchy.append((polygon, children))
            return

        for block in hierarchy:
            if block[0].contains(polygon):
                DXFLoader.append_to_hierarchy(block[1], polygon)
                return

        hierarchy.append((polygon, []))

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
        elt_list.append(shapely.wkt.loads(shapely.wkt.dumps(elt, rounding_precision=3)))
