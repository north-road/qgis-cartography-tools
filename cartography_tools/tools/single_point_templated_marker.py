# -*- coding: utf-8 -*-
"""QGIS Cartography Tools

.. note:: This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt import uic
from qgis.PyQt.QtGui import QFontMetrics
from qgis.PyQt.QtWidgets import QSizePolicy

from qgis.core import (
    QgsVectorLayer,
    QgsMapLayer,
    QgsMapLayerType,
    QgsWkbTypes,
    QgsFieldProxyModel
)
from qgis.gui import QgsMapCanvas

from cartography_tools.tools.map_tool import Tool
from cartography_tools.gui.gui_utils import GuiUtils

WIDGET, BASE = uic.loadUiType(
    GuiUtils.get_ui_file_path('marker_settings.ui'))


class MarkerSettingsWidget(BASE, WIDGET):

    def __init__(self, parent=None):
        super(MarkerSettingsWidget, self).__init__(parent)
        self.setupUi(self)

        self.code_combo.setEditable(True)
        self.code_combo.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        self.code_combo.setMinimumWidth(QFontMetrics(self.font()).width('X') * 40)

        self.field_rotation_combo.setFilters(QgsFieldProxyModel.Numeric)

        self.setFocusProxy(self.field_code_combo)

    def set_layer(self, layer):
        self.field_code_combo.setLayer(layer)
        self.field_rotation_combo.setLayer(layer)


class SinglePointTemplatedMarkerTool(Tool):
    ID = 'SINGLE_POINT_TEMPLATED_MARKER'

    def __init__(self, canvas: QgsMapCanvas, cad_dock_widget, iface, action):
        super().__init__(SinglePointTemplatedMarkerTool.ID, action, canvas, cad_dock_widget, iface)
        self.widget = None

    def cadCanvasMoveEvent(self, event):  # pylint: disable=missing-docstring
        self.snap_indicator.setMatch(event.mapPointMatch())

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

    def delete_widget(self):
        if self.widget:
            self.widget.releaseKeyboard()

            self.widget = None

    def deactivate(self):
        super().deactivate()
        self.delete_widget()

    def activate(self):
        super().activate()
        self.create_widget()

    def set_layer(self, layer: QgsVectorLayer):
        if self.widget:
            self.widget.set_layer(layer)
