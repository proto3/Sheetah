Introduction
==============================

.. figure:: ../_static/images/sheetah.jpg
    :figwidth: 700px
    :target: ../_static/images/sheetah.jpg

`Sheetah`_ is a CAM software, or the visible tip of the iceberg. This is the
interface you interact with when loading DXF or SVG files. It generates G-codes
that are sent to Klipper and reacts to events coming back (ignition failure, arc
loss, etc). G-code is generated on the fly meaning it can skip, retry, reorder
jobs depending on events and user choices. It also features webcam based
augmented reality and THC realtime monitoring.

.. _Sheetah: https://github.com/proto3/sheetah
