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

from qgis.PyQt import sip
from qgis.PyQt.QtCore import (QTranslator,
                              QCoreApplication,
                              QTimer)
from qgis.PyQt.QtWidgets import (
    QToolBar,
    QAction,
    QActionGroup
)

from qgis.core import (
    QgsApplication,
    QgsMapLayerType,
    QgsMapLayer,
    QgsVectorLayer
)
from qgis.gui import QgisInterface

from cartography_tools.processing.provider import CartographyToolsProvider
from cartography_tools.gui.gui_utils import GuiUtils
from cartography_tools.tools.single_point_templated_marker import SinglePointTemplatedMarkerTool
from cartography_tools.tools.multi_point_templated_marker import (
    MultiPointTemplatedMarkerTool,
    TwoPointTemplatedMarkerTool,
    MultiPointSegmentCenterTemplatedMarkerTool
)


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

        self.iface.currentLayerChanged.connect(self.current_layer_changed)
        self.iface.actionToggleEditing().toggled.connect(self.editing_toggled)

    def get_map_tool_action_group(self):
        try:
            return self.iface.mapToolActionGroup()
        except AttributeError:
            return [o for o in self.iface.mainWindow().findChildren(QActionGroup) if self.iface.actionPan() in o.actions()][0]

    def create_tools(self):
        """
        Creates all map tools ands add them to the QGIS interface
        """
        action_single_point_templated_marker = QAction(GuiUtils.get_icon(
            'single_point_templated_marker.svg'), self.tr('Single Point Templated Marker'))
        action_single_point_templated_marker.setCheckable(True)
        self.tools[SinglePointTemplatedMarkerTool.ID] = SinglePointTemplatedMarkerTool(self.iface.mapCanvas(),
                                                                                       self.iface.cadDockWidget(),
                                                                                       self.iface,
                                                                                       action_single_point_templated_marker)
        self.tools[SinglePointTemplatedMarkerTool.ID].setAction(action_single_point_templated_marker)
        action_single_point_templated_marker.triggered.connect(partial(
            self.switch_tool, SinglePointTemplatedMarkerTool.ID))
        action_single_point_templated_marker.setData(SinglePointTemplatedMarkerTool.ID)
        self.toolbar.addAction(action_single_point_templated_marker)
        self.actions.append(action_single_point_templated_marker)

        self.get_map_tool_action_group().addAction(action_single_point_templated_marker)


        # single point at center of line tool

        action_single_point_at_center_of_line = QAction(GuiUtils.get_icon(
            'marker_at_center_of_line.svg'), self.tr('Single Point Templated Marker Via Two Points'))
        action_single_point_at_center_of_line.setCheckable(True)
        self.tools[TwoPointTemplatedMarkerTool.ID] = TwoPointTemplatedMarkerTool(self.iface.mapCanvas(),
                                                                                       self.iface.cadDockWidget(),
                                                                                       self.iface,
                                                                                       action_single_point_at_center_of_line)
        self.tools[TwoPointTemplatedMarkerTool.ID].setAction(action_single_point_at_center_of_line)
        action_single_point_at_center_of_line.triggered.connect(partial(
            self.switch_tool, TwoPointTemplatedMarkerTool.ID))
        action_single_point_at_center_of_line.setData(TwoPointTemplatedMarkerTool.ID)
        self.toolbar.addAction(action_single_point_at_center_of_line)
        self.actions.append(action_single_point_at_center_of_line)

        self.get_map_tool_action_group().addAction(action_single_point_at_center_of_line)


        # multi point tool

        action_multi_point_templated_marker = QAction(GuiUtils.get_icon(
            'multi_point_templated_marker.svg'), self.tr('Multiple Point Templated Marker Along LineString'))
        action_multi_point_templated_marker.setCheckable(True)
        self.tools[MultiPointTemplatedMarkerTool.ID] = MultiPointTemplatedMarkerTool(self.iface.mapCanvas(),
                                                                                       self.iface.cadDockWidget(),
                                                                                       self.iface,
                                                                                       action_multi_point_templated_marker)
        self.tools[MultiPointTemplatedMarkerTool.ID].setAction(action_multi_point_templated_marker)
        action_multi_point_templated_marker.triggered.connect(partial(
            self.switch_tool, MultiPointTemplatedMarkerTool.ID))
        action_multi_point_templated_marker.setData(MultiPointTemplatedMarkerTool.ID)
        self.toolbar.addAction(action_multi_point_templated_marker)
        self.actions.append(action_multi_point_templated_marker)

        self.get_map_tool_action_group().addAction(action_single_point_templated_marker)

        # multi at center of segment point tool

        action_multi_point_center_segment_templated_marker = QAction(GuiUtils.get_icon(
            'multi_point_templated_marker_at_center.svg'), self.tr('Multiple Point Templated Marker At Center Of Segments'))
        action_multi_point_center_segment_templated_marker.setCheckable(True)
        self.tools[MultiPointSegmentCenterTemplatedMarkerTool.ID] = MultiPointSegmentCenterTemplatedMarkerTool(self.iface.mapCanvas(),
                                                                                       self.iface.cadDockWidget(),
                                                                                       self.iface,
                                                                                       action_multi_point_center_segment_templated_marker)
        self.tools[MultiPointSegmentCenterTemplatedMarkerTool.ID].setAction(action_multi_point_center_segment_templated_marker)
        action_multi_point_center_segment_templated_marker.triggered.connect(partial(
            self.switch_tool, MultiPointSegmentCenterTemplatedMarkerTool.ID))
        action_multi_point_center_segment_templated_marker.setData(MultiPointSegmentCenterTemplatedMarkerTool.ID)
        self.toolbar.addAction(action_multi_point_center_segment_templated_marker)
        self.actions.append(action_multi_point_center_segment_templated_marker)

        self.get_map_tool_action_group().addAction(action_single_point_templated_marker)

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

    def switch_tool(self, tool_id: str):
        """
        Switches to the tool with the specified tool_id
        """
        tool = self.tools[tool_id]
        if self.iface.mapCanvas().mapTool() == tool:
            return

        self.iface.mapCanvas().setMapTool(tool)
        self.active_tool = tool
        self.active_tool.set_layer(self.iface.activeLayer())

    def current_layer_changed(self, layer: QgsMapLayer):
        """
        Called when the current layer changes
        """
        self.enable_actions_for_layer(layer)

        if self.active_tool:
            self.active_tool.set_layer(layer)

    def editing_toggled(self, enabled: bool):
        """
        Called when editing mode is toggled
        """
        QTimer.singleShot(0, partial(self.enable_actions_for_layer, self.iface.activeLayer(), enabled))

    def enable_actions_for_layer(self, layer: QgsMapLayer, forced_edit_state=None):
        """
        Toggles whether actions should be enabled for the specified layer
        """

        is_editable = forced_edit_state
        if is_editable is None:
            if isinstance(layer, QgsVectorLayer):
                is_editable = layer.isEditable()
            else:
                is_editable = False

        for action in self.actions:
            if sip.isdeleted(action):
                continue

            if self.tools.get(action.data()):
                tool = self.tools[action.data()]
                action.setEnabled(tool.is_compatible_with_layer(layer, is_editable))
                if tool == self.active_tool and not action.isEnabled():
                    self.iface.mapCanvas().unsetMapTool(tool)
                    self.iface.actionPan().trigger()

