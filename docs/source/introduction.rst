Introduction
==============================

`Sheetah`_ is a plasma CAM software. It allows you to import DXF or SVG
drawings, to configure cut parameters and generates G-Codes. Alternatively, it
can connect to `Klipper for plasma`_ controller and generate G-codes on the fly,
while monitoring cut and handling runtime errors (ignition timeout, arc loss,
etc).

.. figure:: _static/images/sheetah.jpg
    :figwidth: 700px
    :target: _static/images/sheetah.jpg

Planned features:
    - Better user interface for parts. Drag, scale, multiply, rectangle selection, etc
    - Augmented reality to place parts on the machine virtually
    - Configurable post-processor to make G-Code compatible with any plasma controller
    - Complete arc handling instead of discretizing into lines (also convert curves into arcs)
    - Nesting algorithm, possibly with `SVGnest`_
    - Packaged release

.. _Sheetah: https://github.com/proto3/sheetah
.. _Klipper for plasma: https://github.com/proto3/klipper-plasma
.. _SVGnest: https://github.com/Jack000/SVGnest
