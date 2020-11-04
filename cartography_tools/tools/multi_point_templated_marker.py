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

from cartography_tools.tools.map_tool import Tool
from cartography_tools.tools.marker_settings_widget import MarkerSettingsWidget
from cartography_tools.tools.points_along_line_item import PointsAlongLineItem
from cartography_tools.gui.gui_utils import GuiUtils
from cartography_tools.core.geometry import GeometryUtils


class MultiPointTemplatedMarkerTool(Tool):
    ID = 'MULTI_POINT_TEMPLATED_MARKER'

    def __init__(self, canvas: QgsMapCanvas,
                 cad_dock_widget,
                 iface,
                 action,
                 fixed_number_points: Optional[int] = None,
                 single_segment_digitizing: bool=False):
        super().__init__(MultiPointTemplatedMarkerTool.ID, action, canvas, cad_dock_widget, iface)

        self.setCursor(QgsApplication.getThemeCursor(QgsApplication.Cursor.CapturePoint))

        self.fixed_number_points = fixed_number_points
        self.single_segment_digitizing=single_segment_digitizing
        self.widget = None
        self._layer = None
        self.points = []
        self.line_item = None

    def create_point_feature(self, point: Optional[QgsPointXY] = None, angle: Optional[float] = None) -> QgsFeature:
        f = QgsFeature(self.current_layer().fields())

        if self.widget.code_field():
            f[self.widget.code_field()] = self.widget.code_value()

        if angle is not None and self.widget.rotation_field():
            f[self.widget.rotation_field()] = angle

        if point is not None:
            f.setGeometry(QgsGeometry.fromPointXY(point))

        return f

    def cadCanvasMoveEvent(self, event):  # pylint: disable=missing-docstring
        self.snap_indicator.setMatch(event.mapPointMatch())

        if self.points and self.line_item:
            # update preview line item
            self.line_item.set_hover_point(event.snapPoint())
            self.line_item.update()

    def set_line_item_symbol(self):
        f = self.create_point_feature()

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
        self.line_item.set_symbol(symbol_image)
        self.line_item.update()

    def create_line_item(self, map_point: QgsPointXY):
        self.line_item = PointsAlongLineItem(self.canvas(), map_point)
        self.set_line_item_symbol()
        self.line_item.set_orientation(self.widget.orientation())
        self.line_item.set_include_endpoints(self.widget.include_endpoints())
        if not self.fixed_number_points and self.widget.is_fixed_distance():
            self.line_item.set_marker_distance(self.widget.marker_distance())
        else:
            self.line_item.set_marker_count(self.fixed_number_points or self.widget.marker_count())
        self.line_item.update()

    def remove_line_item(self):
        if self.line_item:
            self.canvas().scene().removeItem(self.line_item)
            del self.line_item
            self.line_item = None

    def cadCanvasPressEvent(self, e: QgsMapMouseEvent):
        if not self.current_layer():
            self.points = []
            self.remove_line_item()
            return

        point = self.toLayerCoordinates(self.current_layer(), e.snapPoint())
        if not self.points and e.button() == Qt.LeftButton:
            # first point -- create the preview item
            self.points.append(point)
            self.create_line_item(e.snapPoint())
            self.current_layer().triggerRepaint()
        elif e.button() == Qt.LeftButton and not self.single_segment_digitizing:
            # subsequent left clicks -- add node to line
            self.points.append(point)
            self.line_item.add_point(e.snapPoint())
        elif self.points and (e.button() == Qt.RightButton or (e.button() == Qt.LeftButton and self.single_segment_digitizing)):
            if e.button() == Qt.LeftButton:
                self.points.append(point)

            # right click -- finish line
            self.create_features()
            self.current_layer().triggerRepaint()
            self.points = []
            self.remove_line_item()

    def create_features(self):
        if not self.current_layer():
            return

        res = GeometryUtils.generate_rotated_points_along_path(self.points,
                                                               point_count=self.fixed_number_points or (self.widget.marker_count() if not self.widget.is_fixed_distance() else None),
                                                               point_distance=self.widget.marker_distance() if not self.fixed_number_points and self.widget.is_fixed_distance() else None,
                                                               orientation=-self.widget.orientation(),
                                                               include_endpoints=self.widget.include_endpoints())
        if not res:
            return

        self.current_layer().beginEditCommand(self.tr('Create Markers Along Line'))
        for point, angle in res:
            f = self.create_point_feature(point=point, angle=angle)
            self.current_layer().addFeature(f)
        self.current_layer().endEditCommand()
        self.current_layer().triggerRepaint()

    def keyPressEvent(self, e):
        if self.points and e.key() == Qt.Key_Escape and not e.isAutoRepeat():
            self.remove_line_item()
            if self.current_layer():
                self.current_layer().triggerRepaint()
            self.points = []

    def is_compatible_with_layer(self, layer: QgsMapLayer, is_editable: bool):
        if layer is None:
            return False

        if layer.type() != QgsMapLayerType.VectorLayer:
            return False

        return layer.geometryType() == QgsWkbTypes.PointGeometry and is_editable

    def create_widget(self):
        self.delete_widget()

        self.widget = MarkerSettingsWidget(show_marker_count=self.fixed_number_points is None,
                                           show_orientation=True,
                                           show_placement=self.fixed_number_points is None)
        self.set_user_input_widget(self.widget)
        self.widget.set_layer(self.current_layer())

        self.widget.count_changed.connect(self.count_changed)
        self.widget.distance_changed.connect(self.distance_changed)
        self.widget.code_changed.connect(self.code_changed)
        self.widget.orientation_changed.connect(self.orientation_changed)
        self.widget.placement_changed.connect(self.placement_changed)

    def count_changed(self, count):
        if self.line_item and not self.widget.is_fixed_distance():
            self.line_item.set_marker_count(count)
            self.line_item.update()

    def distance_changed(self, distance):
        if self.line_item and self.widget.is_fixed_distance():
            self.line_item.set_marker_distance(distance)
            self.line_item.update()

    def orientation_changed(self):
        if self.line_item:
            self.line_item.set_orientation(self.widget.orientation())
            self.line_item.update()

    def placement_changed(self):
        if self.line_item:
            self.line_item.set_include_endpoints(self.widget.include_endpoints())
            self.line_item.update()

    def code_changed(self):
        if self.line_item and self.points:
            self.set_line_item_symbol()

    def delete_widget(self):
        if self.widget:
            self.widget.releaseKeyboard()
            self.widget.deleteLater()
            self.widget = None

    def deactivate(self):
        super().deactivate()
        self.points = []
        self.delete_widget()
        self.remove_line_item()

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


class TwoPointTemplatedMarkerTool(MultiPointTemplatedMarkerTool):
    ID = 'TWO_POINT_TEMPLATED_MARKER'

    def __init__(self, canvas: QgsMapCanvas, cad_dock_widget, iface, action):
        super().__init__(canvas=canvas,
                         cad_dock_widget=cad_dock_widget,
                         iface=iface,
                         action=action,
                         fixed_number_points=1,
                         single_segment_digitizing=True)
