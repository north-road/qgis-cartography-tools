# -*- coding: utf-8 -*-
"""QGIS Cartography Tools

.. note:: This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.
"""

__author__ = '(C) 2020 by Nyall Dawson'
__date__ = '19/02/2020'
__copyright__ = 'Copyright 2020, North Road'
# This will get replaced with a git SHA1 when you do a git archive
__revision__ = '$Format:%H$'

import os
from functools import partial

from qgis.PyQt.QtCore import (QTranslator,
                              QCoreApplication)
from qgis.PyQt.QtWidgets import (
    QToolBar,
    QAction
)

from qgis.core import (
    QgsApplication,
    QgsMapLayerType
)
from qgis.gui import QgisInterface

from cartography_tools.processing.provider import CartographyToolsProvider
from cartography_tools.gui.gui_utils import GuiUtils
from cartography_tools.tools.single_point_templated_marker import SinglePointTemplatedMarkerTool

VERSION = '1.0.0'


class CartographyToolsPlugin:
    """QGIS Plugin Implementation."""

    def __init__(self, iface: QgisInterface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        super().__init__()
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QgsApplication.locale()
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            '{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # processing framework
        self.provider = CartographyToolsProvider()

        self.toolbar = None
        self.actions = []
        self.tools = {}

        self.previous_layer = None
        self.edit_start_connection = None
        self.edit_stop_connection = None
        self.active_tool = None

    @staticmethod
    def tr(message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('CartographyTools', message)

    def initProcessing(self):
        """Create the Processing provider"""
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        """Creates application GUI widgets"""
        self.initProcessing()

        self.toolbar = QToolBar(self.tr('Cartography Tools'))
        self.toolbar.setObjectName('cartographyTools')
        self.iface.addToolBar(self.toolbar)

        self.create_tools()

        self.previous_layer = self.iface.activeLayer()
        self.iface.currentLayerChanged.connect(self.current_layer_changed)

    def create_tools(self):
        action_single_point_templated_marker = QAction(GuiUtils.get_icon(
            'plugin.svg'), self.tr('Single Point Templated Marker'))
        action_single_point_templated_marker.setCheckable(True)
        self.tools[SinglePointTemplatedMarkerTool.ID] = SinglePointTemplatedMarkerTool(self.iface.mapCanvas(),
                                                                                       self.iface.cadDockWidget(),
                                                                                       self.iface,
                                                                                       action_single_point_templated_marker)
        action_single_point_templated_marker.triggered.connect(partial(
            self.switch_tool, SinglePointTemplatedMarkerTool.ID))
        action_single_point_templated_marker.setData(SinglePointTemplatedMarkerTool.ID)
        self.toolbar.addAction(action_single_point_templated_marker)
        self.actions.append(action_single_point_templated_marker)

        self.enable_actions_for_layer(self.iface.activeLayer())

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        QgsApplication.processingRegistry().removeProvider(self.provider)

        if self.toolbar is not None:
            self.toolbar.deleteLater()
        for action in self.actions:
            if action is not None:
                action.deleteLater()

        self.iface.currentLayerChanged.disconnect(self.current_layer_changed)

    def switch_tool(self, tool_id):
        tool = self.tools[tool_id]
        self.iface.mapCanvas().setMapTool(tool)
        self.active_tool = tool
        self.active_tool.set_layer(self.previous_layer)

    def current_layer_changed(self, layer):
        if self.edit_start_connection:
            self.previous_layer.disconnect(self.edit_start_connection)
            self.edit_start_connection = None
        if self.edit_stop_connection:
            self.previous_layer.disconnect(self.edit_stop_connection)
            self.edit_stop_connection = None

        if layer is not None and layer.type() == QgsMapLayerType.VectorLayer:
            self.edit_start_connection = layer.editingStarted.connect(partial(self.enable_actions_for_layer, layer))
            self.edit_stop_connection = layer.editingStopped.connect(partial(self.enable_actions_for_layer, layer))

        self.enable_actions_for_layer(layer)
        self.previous_layer = layer

        if self.active_tool:
            self.active_tool.set_layer(layer)

    def enable_actions_for_layer(self, layer):
        for action in self.actions:
            if self.tools.get(action.data()):
                action.setEnabled(self.tools[action.data()].is_compatible_with_layer(layer))
