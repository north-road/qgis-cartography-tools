# -*- coding: utf-8 -*-
"""QGIS Cartography Tools

.. note:: This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.
"""

import math

from qgis.gui import QgsMapCanvasItem

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
    QBrush
)

from cartography_tools.gui.gui_utils import GuiUtils


class PointRotationItem(QgsMapCanvasItem):
    """
    A map canvas item which shows an angle display and preview of marker rotation
    """

    def __init__(self, canvas):
        super().__init__(canvas)

        self.rotation = 0
        self.pixmap = QPixmap()
        self.item_size = QSizeF()

        self.marker_font = self.font()
        self.marker_font.setPointSize(12)
        self.marker_font.setBold(True)

        self.arrow_path = QPainterPath()

        im = QImage(24, 24, QImage.Format_ARGB32)
        im.fill(Qt.transparent)
        self.setSymbol(im)

    def paint(self, painter):
        if not painter:
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        # do a bit of trigonometry to find out how to transform a rotated item such
        # that the center point is at the point feature
        x = 0.0
        y = 0.0

        if self.pixmap.width() > 0 and self.pixmap.height() > 0:
            half_item_diagonal = math.sqrt(
                self.pixmap.width() * self.pixmap.width() + self.pixmap.height() * self.pixmap.height()) / 2
            diagonal_angle = math.acos(self.pixmap.width() / (half_item_diagonal * 2)) * 180 / math.pi
            x = half_item_diagonal * math.cos((self.rotation - diagonal_angle) * math.pi / 180)
            y = half_item_diagonal * math.sin((self.rotation - diagonal_angle) * math.pi / 180)

        painter.rotate(self.rotation)
        painter.translate(x - self.pixmap.width() / 2.0, -y - self.pixmap.height() / 2.0)
        painter.drawPixmap(0, 0, self.pixmap)

        # draw arrow, using a red line over a thicker white line so that the arrow is visible
        # against a range of backgrounds
        pen = QPen()
        pen.setWidth(GuiUtils.scale_icon_size(4))
        pen.setColor(QColor(Qt.white))
        painter.setPen(pen)
        painter.drawPath(self.arrow_path)
        pen.setWidth(GuiUtils.scale_icon_size(1))
        pen.setColor(QColor(Qt.red))
        painter.setPen(pen)
        painter.drawPath(self.arrow_path)
        painter.restore()

        # draw numeric value beside the symbol
        painter.save()
        buffer_pen = QPen()
        buffer_pen.setColor(Qt.white)
        buffer_pen.setWidthF(GuiUtils.scale_icon_size(4))
        fm = QFontMetricsF(self.marker_font)
        label = QPainterPath()
        label.addText(self.pixmap.width(), self.pixmap.height() / 2.0 + fm.height() / 2.0, self.marker_font,
                      str(self.rotation))
        painter.setPen(buffer_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(label)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(Qt.black))
        painter.drawPath(label)

        painter.restore()

    def set_point_location(self, p):
        transformed_point = self.toCanvasCoordinates(p)
        self.setPos(transformed_point.x() - self.pixmap.width() / 2.0,
                    transformed_point.y() - self.pixmap.height() / 2.0)

    def set_symbol_rotation(self, rotation: float):
        self.rotation = rotation

    def set_symbol(self, symbol_image: QImage):
        self.pixmap = QPixmap.fromImage(symbol_image)
        fm = QFontMetricsF(self.marker_font)

        # set item size
        self.item_size.setWidth(self.pixmap.width() + fm.width("360"))

        pixmap_height = self.pixmap.height()
        font_height = fm.height()
        if pixmap_height >= font_height:
            self.item_size.setHeight(self.pixmap.height())
        else:
            self.item_size.setHeight(fm.height())

        half_item_width = self.pixmap.width() / 2.0
        self.arrow_path.clear()
        self.arrow_path.moveTo(half_item_width, pixmap_height)
        self.arrow_path.lineTo(half_item_width, 0)
        self.arrow_path.moveTo(self.pixmap.width() * 0.25, pixmap_height * 0.25)
        self.arrow_path.lineTo(half_item_width, 0)
        self.arrow_path.lineTo(self.pixmap.width() * 0.75, pixmap_height * 0.25)
