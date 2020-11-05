# -*- coding: utf-8 -*-
"""QGIS Cartography Tools

.. note:: This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.
"""
from typing import Optional

from qgis.PyQt import sip
from qgis.PyQt.QtCore import Qt
from qgis.core import (
    QgsVectorLayer,
    QgsMapLayer,
    QgsMapLayerType,
    QgsWkbTypes,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsRenderContext,
    QgsExpressionContextUtils,
    QgsProperty,
    QgsApplication,
    NULL,
    QgsSymbol
)
from qgis.gui import (
    QgsMapCanvas,
    QgsMapMouseEvent
)

from cartography_tools.gui.gui_utils import GuiUtils
from cartography_tools.tools.map_tool import Tool
from cartography_tools.tools.marker_settings_widget import MarkerSettingsWidget
from cartography_tools.tools.point_rotation_item import PointRotationItem


class SinglePointTemplatedMarkerTool(Tool):
    ID = 'SINGLE_POINT_TEMPLATED_MARKER'

    def __init__(self, canvas: QgsMapCanvas, cad_dock_widget, iface, action):
        super().__init__(SinglePointTemplatedMarkerTool.ID, action, canvas, cad_dock_widget, iface)

        self.setCursor(QgsApplication.getThemeCursor(QgsApplication.Cursor.CapturePoint))

        self.widget = None
        self._layer = None
        self.initial_point = None
        self.rotation_item = None

    def create_feature(self, point: QgsPointXY, rotation: float) -> QgsFeature:
        f = QgsFeature(self.current_layer().fields())

        if self.widget.code_field():
            f[self.widget.code_field()] = self.widget.code_value()

        if self.widget.rotation_field():
            f[self.widget.rotation_field()] = rotation

        f.setGeometry(QgsGeometry.fromPointXY(point))

        return f

    def cadCanvasMoveEvent(self, event):  # pylint: disable=missing-docstring
        self.snap_indicator.setMatch(event.mapPointMatch())

        if self.initial_point is not None and self.rotation_item and self.current_layer():
            # update preview rotation
            point = self.toLayerCoordinates(self.current_layer(), event.snapPoint())
            self.rotation_item.set_symbol_rotation(self.initial_point.azimuth(point))
            self.rotation_item.update()

    def create_rotation_item(self, map_point: QgsPointXY):
        f = self.create_feature(point=self.initial_point, rotation=0)

        # find symbol for feature
        renderer = self.current_layer().renderer().clone()
        context = QgsRenderContext.fromMapSettings(self.canvas().mapSettings())
        context.expressionContext().appendScope(QgsExpressionContextUtils.layerScope(self.current_layer()))
        context.expressionContext().setFeature(f)

        renderer.startRender(context, self.current_layer().fields())
        symbol = renderer.originalSymbolForFeature(f, context)
        if symbol is None:
            # e.g. code which doesn't match existing category
            if len(renderer.symbols(context)):
                symbol = renderer.symbols(context)[0]
            else:
                symbol = QgsSymbol.defaultSymbol(self.current_layer().geometryType())

        renderer.stopRender(context)

        # clear existing data defined rotation
        symbol.setDataDefinedAngle(QgsProperty())

        # render symbol to image
        symbol_image = GuiUtils.big_marker_preview_image(symbol, context.expressionContext())

        self.rotation_item = PointRotationItem(self.canvas())
        self.rotation_item.set_symbol(symbol_image)
        self.rotation_item.set_point_location(map_point)
        self.rotation_item.set_symbol_rotation(0)
        self.rotation_item.update()

    def remove_rotation_item(self):
        if self.rotation_item:
            self.canvas().scene().removeItem(self.rotation_item)
            del self.rotation_item
            self.rotation_item = None

    def cadCanvasPressEvent(self, e: QgsMapMouseEvent):
        if not self.current_layer():
            self.initial_point = None
            self.remove_rotation_item()
            return

        point = self.toLayerCoordinates(self.current_layer(), e.snapPoint())
        if self.initial_point is None and e.button() == Qt.LeftButton:
            # depending on whether a rotation field is selected, we either start the interactive rotation or
            # immediately create the feature
            if self.widget.rotation_field():
                self.initial_point = point
                self.create_rotation_item(e.snapPoint())
                self.current_layer().triggerRepaint()
            else:
                f = self.create_feature(point=point, rotation=NULL)
                self.current_layer().addFeature(f)
                self.current_layer().triggerRepaint()
        else:
            if e.button() == Qt.LeftButton:
                f = self.create_feature(point=self.initial_point, rotation=self.initial_point.azimuth(point))
                self.current_layer().addFeature(f)

            self.current_layer().triggerRepaint()
            self.initial_point = None
            self.remove_rotation_item()

    def keyPressEvent(self, e):
        if self.initial_point and e.key() == Qt.Key_Escape and not e.isAutoRepeat():
            self.remove_rotation_item()
            if self.current_layer():
                self.current_layer().triggerRepaint()
            self.initial_point = None

    def is_compatible_with_layer(self, layer: QgsMapLayer, is_editable: bool):
        if layer is None:
            return False

        if layer.type() != QgsMapLayerType.VectorLayer:
            return False

        return layer.geometryType() == QgsWkbTypes.PointGeometry and is_editable

    def create_widget(self):
        self.delete_widget()

        self.widget = MarkerSettingsWidget()
        self.set_user_input_widget(self.widget)
        self.widget.set_layer(self.current_layer())

    def delete_widget(self):
        if self.widget:
            self.widget.releaseKeyboard()
            self.widget.deleteLater()
            self.widget = None

    def deactivate(self):
        super().deactivate()
        self.delete_widget()
        self.remove_rotation_item()

    def activate(self):
        super().activate()
        self.create_widget()

    def set_layer(self, layer: QgsVectorLayer):
        self._layer = layer
        if self.widget:
            self.widget.set_layer(layer)

    def current_layer(self) -> Optional[QgsVectorLayer]:
        if self._layer is not None and not sip.isdeleted(self._layer):
            return self._layer
        return None
