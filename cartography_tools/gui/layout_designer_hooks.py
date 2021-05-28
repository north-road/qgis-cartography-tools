# -*- coding: utf-8 -*-
"""Layout Designer Hooks

.. note:: This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.
"""

__author__ = '(C) 2021 by Nyall Dawson'
__date__ = '28/05/2021'
__copyright__ = 'Copyright 2021, North Road'
# This will get replaced with a git SHA1 when you do a git archive
__revision__ = '$Format:%H$'

from functools import partial

from qgis.PyQt.QtCore import (
    QObject
)
from qgis.PyQt.QtGui import (
    QKeySequence
)
from qgis.PyQt.QtWidgets import (
    QAction,
)
from qgis.core import (
    QgsLayoutItemMap
)
from qgis.gui import (
    QgisInterface,
    QgsLayoutDesignerInterface
)

from cartography_tools.gui.gui_utils import GuiUtils


class LayoutDesignerHooks(QObject):
    """
    Hooks for customizing layout designers
    """

    def init_gui(self, iface: QgisInterface):
        """
        Initializes the hooks
        """
        iface.layoutDesignerOpened.connect(self.designer_opened)
        iface.layoutDesignerWillBeClosed.connect(self.designer_will_be_closed)

    def unload(self, iface: QgisInterface):
        """
        Unloads the hooks
        """
        iface.layoutDesignerOpened.disconnect(self.designer_opened)
        iface.layoutDesignerWillBeClosed.disconnect(self.designer_will_be_closed)

    def designer_opened(self, designer: QgsLayoutDesignerInterface):
        """
        Called whenever a new layout designer window is opened
        """
        toggle_unplaced_labels_action = QAction(self.tr('Show Unplaced Labels on Maps'), parent=designer)
        toggle_unplaced_labels_action.setCheckable(True)
        toggle_unplaced_labels_action.setIcon(GuiUtils.get_icon(
            'show_unplaced_labels.svg'))

        # determine initial check state
        layout = designer.layout()
        maps = [item for item in layout.items() if isinstance(item, QgsLayoutItemMap)]
        initial_checked = all(m.mapFlags() & QgsLayoutItemMap.ShowUnplacedLabels for m in maps)
        toggle_unplaced_labels_action.setChecked(initial_checked)
        toggle_unplaced_labels_action.toggled.connect(partial(self.toggle_unplaced_labels, designer))
        toggle_unplaced_labels_action.setShortcut(QKeySequence('Ctrl+Shift+U'))

        tb = designer.actionsToolbar()
        tb.addSeparator()
        tb.addAction(toggle_unplaced_labels_action)
        designer.viewMenu().addSeparator()
        designer.viewMenu().addAction(toggle_unplaced_labels_action)

    def designer_will_be_closed(self, designer: QgsLayoutDesignerInterface):
        """
        Called whenever a layout designer is closed
        """

    def toggle_unplaced_labels(self, designer: QgsLayoutDesignerInterface, checked: bool):
        """
        Toggles unplaced label visibility for the specified designer
        """
        layout = designer.layout()
        maps = [item for item in layout.items() if isinstance(item, QgsLayoutItemMap)]
        for m in maps:
            flags = m.mapFlags()
            if checked:
                flags |= QgsLayoutItemMap.ShowUnplacedLabels
            else:
                flags &= ~QgsLayoutItemMap.ShowUnplacedLabels
            m.setMapFlags(flags)
            m.invalidateCache()
