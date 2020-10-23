# -*- coding: utf-8 -*-
"""QGIS Cartography Tools

.. note:: This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.
"""

from qgis.core import QgsMapLayer
from qgis.gui import (
    QgsMapToolAdvancedDigitizing,
    QgsMapCanvas,
    QgsSnapIndicator
)


class Tool(QgsMapToolAdvancedDigitizing):
    """
    Base class for cartography map tools
    """

    def __init__(self, tool_id, action, canvas: QgsMapCanvas, cad_dock_width, iface):
        super().__init__(canvas, cad_dock_width)
        self._id = tool_id
        self.setAction(action)
        self.iface = iface
        self.snap_indicator = QgsSnapIndicator(canvas)

    def is_compatible_with_layer(self, layer: QgsMapLayer, is_editable: bool) -> bool:
        """
        Returns True if tool is compatible with the specified layer
        """
        return True
