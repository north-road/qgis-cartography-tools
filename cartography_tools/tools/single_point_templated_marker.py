# -*- coding: utf-8 -*-
"""QGIS Cartography Tools

.. note:: This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.
"""

from qgis.PyQt.QtCore import Qt

from qgis.core import (
    QgsVectorLayer,
    QgsMapLayer,
    QgsMapLayerType,
    QgsWkbTypes,
    QgsFeature,
    QgsGeometry
)
from qgis.gui import (
    QgsMapCanvas,
    QgsMapMouseEvent
)

from cartography_tools.tools.map_tool import Tool
from cartography_tools.tools.marker_settings_widget import MarkerSettingsWidget


class SinglePointTemplatedMarkerTool(Tool):
    ID = 'SINGLE_POINT_TEMPLATED_MARKER'

    def __init__(self, canvas: QgsMapCanvas, cad_dock_widget, iface, action):
        super().__init__(SinglePointTemplatedMarkerTool.ID, action, canvas, cad_dock_widget, iface)
        self.widget = None
        self.layer = None
        self.initial_point = None

    def cadCanvasMoveEvent(self, event):  # pylint: disable=missing-docstring
        self.snap_indicator.setMatch(event.mapPointMatch())

    def cadCanvasPressEvent(self, e: QgsMapMouseEvent):
        point = self.toLayerCoordinates(self.layer, e.snapPoint())
        if self.initial_point is None:
            self.initial_point = point
        else:
            f=QgsFeature(self.layer.fields())

            f[self.widget.code_field()] = self.widget.code_value()
            f[self.widget.rotation_field()] = self.initial_point.azimuth(point)

            f.setGeometry(QgsGeometry.fromPointXY(self.initial_point))
            self.layer.addFeature(f)
            self.layer.triggerRepaint()

            self.initial_point = None

    def is_compatible_with_layer(self, layer: QgsMapLayer):
        if layer is None:
            return False

        if layer.type() != QgsMapLayerType.VectorLayer:
            return False

        return layer.geometryType() == QgsWkbTypes.PointGeometry and layer.isEditable()

    def create_widget(self):
        self.delete_widget()

        self.widget = MarkerSettingsWidget()
        self.iface.addUserInputWidget(self.widget)
        self.widget.setFocus(Qt.TabFocusReason)
        self.widget.set_layer(self.layer)

    def delete_widget(self):
        if self.widget:
            self.widget.releaseKeyboard()
            self.widget.deleteLater()
            self.widget = None

    def deactivate(self):
        super().deactivate()
        self.delete_widget()

    def activate(self):
        super().activate()
        self.create_widget()

    def set_layer(self, layer: QgsVectorLayer):
        self.layer = layer
        if self.widget:
            self.widget.set_layer(layer)
