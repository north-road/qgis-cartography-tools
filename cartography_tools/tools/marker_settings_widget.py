# -*- coding: utf-8 -*-
"""QGIS Cartography Tools

.. note:: This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.
"""
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QSize, pyqtSignal
from qgis.PyQt.QtGui import QFontMetrics
from qgis.PyQt.QtWidgets import QSizePolicy
from qgis.core import (
    QgsFieldProxyModel,
    QgsVectorLayer,
    QgsCategorizedSymbolRenderer,
    QgsSymbolLayerUtils,
    NULL
)

from cartography_tools.gui.gui_utils import GuiUtils

WIDGET, BASE = uic.loadUiType(
    GuiUtils.get_ui_file_path('marker_settings.ui'))


class MarkerSettingsWidget(BASE, WIDGET):

    count_changed = pyqtSignal(int)

    def __init__(self, show_marker_count=False, parent=None):
        super(MarkerSettingsWidget, self).__init__(parent)
        self.setupUi(self)

        self.code_combo.setEditable(True)
        self.code_combo.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        self.code_combo.setMinimumWidth(QFontMetrics(self.font()).width('X') * 40)

        self.field_code_combo.setAllowEmptyFieldName(True)

        self.field_rotation_combo.setFilters(QgsFieldProxyModel.Numeric)
        self.field_rotation_combo.setAllowEmptyFieldName(True)

        self.setFocusProxy(self.field_code_combo)

        self.field_code_combo.fieldChanged.connect(self.field_code_changed)
        self.field_rotation_combo.fieldChanged.connect(self.field_rotation_changed)
        self.code_combo.currentTextChanged.connect(self.code_changed)
        self.marker_count_spin.valueChanged.connect(self.marker_count_changed)

        if not show_marker_count:
            self.marker_count_label.setVisible(False)
            self.marker_count_spin.setVisible(False)

        self.marker_count_spin.setMinimum(2)

        self.layer = None

    def set_layer(self, layer: QgsVectorLayer):
        if self.layer:
            self.layer.rendererChanged.disconnect(self.update_for_renderer)

        self.layer = layer
        self.field_code_combo.setLayer(layer)
        self.field_rotation_combo.setLayer(layer)

        prev_code = self.code_value()

        if layer and layer.customProperty('cartography_tools/feature_code_field'):
            self.field_code_combo.setField(layer.customProperty('cartography_tools/feature_code_field'))
        elif layer and isinstance(layer.renderer(), QgsCategorizedSymbolRenderer):
            # otherwise default to categorized field, if possible...
            self.field_code_combo.setField(layer.renderer().classAttribute())
        if layer and layer.customProperty('cartography_tools/marker_rotation_field'):
            self.field_rotation_combo.setField(layer.customProperty('cartography_tools/marker_rotation_field'))
        if layer and layer.customProperty('cartography_tools/last_feature_code'):
            prev_code = layer.customProperty('cartography_tools/last_feature_code')
        if layer and layer.customProperty('cartography_tools/last_marker_count'):
            self.marker_count_spin.setValue(int(layer.customProperty('cartography_tools/last_marker_count')))

        self.update_for_renderer()
        if self.layer:
            layer.rendererChanged.connect(self.update_for_renderer)

        # try to restore code value correctly
        self.set_code_value(prev_code)

    def set_code_value(self, value):
        index = -1

        for i in range(self.code_combo.count()):
            if self.code_combo.itemText(i) == value:
                index = i
                break

        if index >= 0:
            self.code_combo.setCurrentIndex(index)
        else:
            self.code_combo.setCurrentText(value)

    def update_for_renderer(self):
        if not self.layer:
            return

        icon_size = GuiUtils.scale_icon_size(16)

        renderer = self.layer.renderer()
        if isinstance(renderer, QgsCategorizedSymbolRenderer):
            prev_value = self.code_combo.currentText()
            self.code_combo.clear()

            prev_index = -1

            for category in renderer.categories():
                if category.value() is not None and category.value() != NULL:
                    if category.value() == prev_value:
                        prev_index = self.code_combo.count()
                    icon = QgsSymbolLayerUtils.symbolPreviewIcon(category.symbol(), QSize(icon_size, icon_size))

                    item_label = f'{category.label()} - ({category.value()})' if category.label() != category.value() else category.value()
                    self.code_combo.addItem(icon, item_label)
                    self.code_combo.setItemData(self.code_combo.count() - 1, category.value())

            if prev_index >= 0:
                self.code_combo.setCurrentIndex(prev_index)
            else:
                self.code_combo.setCurrentText(prev_value)

    def field_code_changed(self):
        if not self.field_code_combo.layer():
            return

        self.field_code_combo.layer().setCustomProperty('cartography_tools/feature_code_field',
                                                        self.field_code_combo.currentField())

        self.code_combo.setEnabled(bool(self.field_code_combo.currentField()))

    def field_rotation_changed(self):
        if not self.field_rotation_combo.layer():
            return

        self.field_rotation_combo.layer().setCustomProperty('cartography_tools/marker_rotation_field',
                                                            self.field_rotation_combo.currentField())

    def code_changed(self):
        if not self.field_rotation_combo.layer():
            return

        self.field_rotation_combo.layer().setCustomProperty('cartography_tools/last_feature_code',
                                                            self.code_combo.currentText())

    def marker_count_changed(self):
        if not self.field_rotation_combo.layer():
            return

        self.field_rotation_combo.layer().setCustomProperty('cartography_tools/last_marker_count',
                                                            self.marker_count_spin.value())
        self.count_changed.emit(self.marker_count_spin.value())

    def code_field(self):
        return self.field_code_combo.currentField()

    def code_value(self):
        if self.code_combo.itemText(self.code_combo.currentIndex()) == self.code_combo.currentText():
            return self.code_combo.currentData() or self.code_combo.currentText()
        else:
            return self.code_combo.currentText()

    def rotation_field(self):
        return self.field_rotation_combo.currentField()

    def marker_count(self):
        return self.marker_count_spin.value()
