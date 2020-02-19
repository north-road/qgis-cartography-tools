# -*- coding: utf-8 -*-

"""
***************************************************************************
    provider.py
    ---------------------
    Date                 : February 2020
    Copyright            : (C) 2020 by Nyall Dawson
    Email                : nyall dot dawson at gmail dot com
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

import os
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import QgsProcessingProvider

from cartography_tools.processing.algorithm import (
    RemoveRoundaboutsAlgorithm,
    RemoveCuldesacsAlgorithm,
    RemoveCrossRoadsAlgorithm
)
from cartography_tools.gui.gui_utils import GuiUtils


class CartographyToolsProvider(QgsProcessingProvider):
    """
    Processing provider for cartography tools
    """

    def __init__(self):
        super().__init__()
        self.algs = []

    def icon(self):
        """
        Returns the provider's icon
        """
        return GuiUtils.get_icon("providerR.svg")

    def svgIconPath(self):
        """
        Returns a path to the provider's icon as a SVG file
        """
        return GuiUtils.get_icon_svg("providerR.svg")

    def name(self):
        """
        Display name for provider
        """
        return self.tr('Cartography tools')

    def versionInfo(self):
        """
        Provider plugin version
        """
        return "1.0.0"

    def id(self):
        """
        Unique ID for provider
        """
        return 'cartographytools'

    def loadAlgorithms(self):
        """
        Called when provider must populate its available algorithms
        """
        for a in [RemoveRoundaboutsAlgorithm, RemoveCuldesacsAlgorithm, RemoveCrossRoadsAlgorithm]:
            self.addAlgorithm(a())

    def tr(self, string, context=''):
        """
        Translates a string
        """
        if context == '':
            context = 'CartographyTools'
        return QCoreApplication.translate(context, string)
