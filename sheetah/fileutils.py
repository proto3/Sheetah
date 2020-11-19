import numpy as np
import ezdxf
import svgpathtools as svgpt
import pathlib

from math import radians

import polyline as pl
from job import Job

def _load_polylines_dxf(filepath):
    dwg = ezdxf.readfile(filepath)
    msp = dwg.modelspace()
    polylines = []
    for e in msp:
        if e.dxftype() == 'LINE':
            polyline = pl.line2polyline(e.dxf.start[:2], e.dxf.end[:2])
        elif e.dxftype() == 'ARC':
            polyline = pl.arc2polyline(e.dxf.center, e.dxf.radius,
                                       radians(e.dxf.start_angle),
                                       radians(e.dxf.end_angle))
        elif e.dxftype() == 'CIRCLE':
            polyline = pl.circle2polyline(e.dxf.center, e.dxf.radius)
        elif e.dxftype() == 'LWPOLYLINE':
            vertices = np.array(e.get_points()).transpose()[[0,1,4]]
            polyline = pl.Polyline(vertices, e.closed)
        elif e.dxftype() == 'SPLINE':
            polyline = pl.spline2polyline(e.dxf.degree,
                [list(i) for i in np.array(e.control_points)[:,:2]], e.closed)
        else:
            raise Exception('unimplemented \"'+e.dxftype()+'\" dxf entity.')
        polylines.append(polyline)

    return polylines

def _load_polylines_svg(filepath):
    px_per_inch = 96
    mm_per_inch = 25.4
    px_per_mm = px_per_inch / mm_per_inch

    svg_items = svgpt.svg2paths(filepath,
                                convert_lines_to_paths=True,
                                convert_polylines_to_paths=True,
                                convert_polygons_to_paths=True,
                                return_svg_attributes=False)
    polylines = []
    for i in svg_items[0][0]:
        if isinstance(i, svgpt.path.Line):
            line = np.array([[svgpt.real(i.point(0.0)), svgpt.imag(i.point(0.0))],
                             [svgpt.real(i.point(1.0)), svgpt.imag(i.point(1.0))]])
            line /= px_per_mm
            if np.allclose(line[0], line[1]):
                continue
            polyline = pl.line2polyline(line[0], line[1])
        elif isinstance(i, svgpt.path.CubicBezier):
            control_points = np.array([[svgpt.real(i.start),    svgpt.imag(i.start)],
                                       [svgpt.real(i.control1), svgpt.imag(i.control1)],
                                       [svgpt.real(i.control2), svgpt.imag(i.control2)],
                                       [svgpt.real(i.end),      svgpt.imag(i.end)]])
            control_points /= px_per_mm
            polyline = pl.spline2polyline(3, control_points.tolist(), False)
        else:
            raise Exception('unknown type', i)
        polylines.append(polyline)
    return polylines

def load(filepath):
    # Load file as polylines only (line, arc, spline, etc are converted).
    path = pathlib.Path(filepath)
    extension = path.suffix.lower()
    name = path.stem
    if extension == '.dxf':
        raw_polylines = _load_polylines_dxf(filepath)
    elif extension == '.svg':
        raw_polylines = _load_polylines_svg(filepath)
    else:
        raise Exception('unknown extension \"' + extension + '\".')

    # Aggregate consecutive polylines.
    polylines = pl.aggregate(raw_polylines)

    # Check for no complex polylines (self crossing).
    for polyline in polylines:
        if not polyline.is_simple():
            # TODO find a way to show user where is(are) the intersection(s)
            raise Exception('Self crossing geometry found')

    # TODO detect geometry that cross others


    # TODO remove buggy closed single lines
    polylines = [p for p in polylines if p._vertices.shape[0] > 1]

    # Group polylines as exterior and interior contours.
    # Exterior is always the last in a group.
    contour_groups = pl.group_as_contours(polylines)

    bounds = [g[-1].bounds.flatten() for g in contour_groups]
    bounds = np.transpose(np.vstack(bounds))
    global_pos = np.min(bounds, axis=1)[:2]

    # Create jobs and return.
    jobs = []
    for i, contours in enumerate(contour_groups):
        if len(contour_groups) > 1:
            job_name = format('%s %i'%(name, i))
        else:
            job_name = name
        local_pos = contours[-1].bounds[0]
        shifted = [c.affine(-local_pos, 0, 1) for c in contours]
        job = Job(job_name, shifted)
        job.position = local_pos - global_pos
        jobs.append(job)
    return jobs
