# -*- coding: utf-8 -*-
"""QGIS Cartography Tools

.. note:: This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.
"""

import math

from qgis.PyQt.QtCore import (
    Qt,
    QSizeF
)
from qgis.PyQt.QtGui import (
    QImage,
    QPixmap,
    QFontMetricsF,
    QColor,
    QPainter,
    QPen,
    QPainterPath,
    QBrush,
    QFont
)
from qgis.core import (
    QgsRectangle,
    QgsPointXY,
    QgsGeometry
)
from qgis.gui import QgsMapCanvasItem

from cartography_tools.gui.gui_utils import GuiUtils


class PointsAlongLineItem(QgsMapCanvasItem):
    """
    A map canvas item which shows a linestring with equally spaced marker points
    """

    def __init__(self, canvas, start_point):
        super().__init__(canvas)

        self.canvas = canvas

        self.rotation = 0
        self.pixmap = QPixmap()
        self.item_size = QSizeF()

        self.marker_font = QFont()
        self.marker_font.setPointSize(12)
        self.marker_font.setBold(True)

        self.arrow_path = QPainterPath()

        im = QImage(24, 24, QImage.Format_ARGB32)
        im.fill(Qt.transparent)
        self.set_symbol(im)

        self.points = [start_point]
        self.hover_point = None

        self.pen = QPen()
        self.pen.setWidth(GuiUtils.scale_icon_size(4))
        self.pen.setColor(QColor(Qt.white))

        self.marker_count = 2

        self.update_rect()
        self.update()

    def set_hover_point(self, point):
        self.hover_point = point
        self.update_rect()
        self.update()

    def add_point(self, point):
        self.points.append(point)
        self.update_rect()
        self.update()

    def update_rect(self):
        if not self.points:
            self.setVisible(False)
            return

        map_to_pixel = self.canvas.getCoordinateTransform()

        width = self.pen.width() + (self.pixmap.width() / 2 if self.pixmap else 0)

        all_points = self.points + ([self.hover_point] if self.hover_point else [])

        r = QgsRectangle()

        for p in all_points:
            transformed_point = map_to_pixel.transform(p)
            point_rect = QgsRectangle(transformed_point.x() - width, transformed_point.y() - width,
                                      transformed_point.x() + width, transformed_point.y() + width)
            if r.isEmpty():
                r = point_rect
            else:
                r.combineExtentWith(point_rect)

            prev_point = p

        res = map_to_pixel.mapUnitsPerPixel()
        top_left = map_to_pixel.toMapCoordinates(r.xMinimum(), r.yMinimum())

        self.setRect(QgsRectangle(top_left.x(), top_left.y(), top_left.x() + r.width() * res, top_left.y() - r.height() * res))

        self.setVisible(True)

    def updatePosition(self):
        self.update_rect()

    def paint(self, painter, option, widget):
        if not painter or not self.points:
            return

        all_points = self.points + ([self.hover_point] if self.hover_point else [])
        if len(all_points) < 2:
            return
        
        if all_points[-1] == all_points[-2]:
            all_points = all_points[:-1]
        if len(all_points) < 2:
            return


        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        canvas_points = [self.toCanvasCoordinates(p) - self.pos() for p in all_points]

        total_length = 0
        prev_point = None
        for p in all_points:
            if prev_point is not None:
                total_length += prev_point.distance(p)
            prev_point = p

        line_path = QPainterPath()
        line_path.moveTo(canvas_points[0].x(), canvas_points[0].y())
        for p in canvas_points[1:]:
            line_path.lineTo(p.x(), p.y())

        # draw arrow, using a red line over a thicker white line so that the arrow is visible
        # against a range of backgrounds
        pen = QPen()
        pen.setWidth(GuiUtils.scale_icon_size(4))
        pen.setColor(QColor(255,255,255,100))
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawPath(line_path)
        pen.setWidth(GuiUtils.scale_icon_size(1))
        pen.setColor(QColor(255,0,0,100))
        painter.setPen(pen)
        painter.drawPath(line_path)

        distance = 0
        if self.marker_count == 1:
            marker_spacing = total_length
        else:
            marker_spacing = total_length / (self.marker_count-1)

        line_geom = QgsGeometry.fromPolylineXY(all_points)

        if self.pixmap and total_length:
            for i in range(self.marker_count):

                point = line_geom.interpolate(distance)
                marker_point = self.toCanvasCoordinates(point.asPoint()) - self.pos()

                angle = line_geom.interpolateAngle(distance)*180/math.pi

                painter.save()
                painter.translate(marker_point.x(),
                                   marker_point.y())
                painter.rotate(angle)
                painter.drawPixmap(-self.pixmap.width() /2,-self.pixmap.height() /2, self.pixmap)
                painter.restore()

                distance += marker_spacing

        painter.restore()

    def point_along_line_at_distance(self, points, distance):
        traversed = 0
        prev_point = points[0]
        for p in points[1:]:
            this_segment_length = p.distance(prev_point)
            if traversed + this_segment_length < distance:
                traversed += this_segment_length
                prev_point = p
                continue

            fraction = (distance - traversed)/this_segment_length
            dx = p.x() - prev_point.x()
            dy = p.y() - prev_point.y()
            return QgsPointXY(prev_point.x() + dx * fraction, prev_point.y() + dy * fraction)

        return prev_point

    def set_symbol(self, symbol_image: QImage):
        self.pixmap = QPixmap.fromImage(symbol_image)

    def set_marker_count(self, count):
        self.marker_count = count




