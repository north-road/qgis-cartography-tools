# -*- coding: utf-8 -*-

"""
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (QgsWkbTypes,
                       QgsExpression,
                       QgsProcessing,
                       QgsFeatureSink,
                       QgsSpatialIndex,
                       QgsGeometry,
                       QgsFeature,
                       QgsVertexId,
                       QgsMapLayer,
                       QgsProcessingException,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterField,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterExpression,
                       QgsProcessingParameterDistance,
                       QgsProcessingParameterFeatureSink)
from cartography_tools.processing.geometry import GeometryUtils


class RemoveRoundaboutsAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    EXPRESSION = 'EXPRESSION'
    OUTPUT = 'OUTPUT'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return RemoveRoundaboutsAlgorithm()

    def name(self):
        return 'removeroundabouts'

    def displayName(self):
        return self.tr('Remove roundabouts')

    def group(self):
        return self.tr('Road networks')

    def groupId(self):
        return 'road'

    def shortHelpString(self):
        return self.tr("Generalizes a road network by removing roundabouts")

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr('Input layer'),
                [QgsProcessing.TypeVectorLine]
            )
        )

        self.addParameter(
            QgsProcessingParameterExpression(
                self.EXPRESSION,
                self.tr('Identify roundabouts by'),
                parentLayerParameterName=self.INPUT
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Output layer')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(
            parameters,
            self.INPUT,
            context
        )

        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            source.fields(),
            QgsWkbTypes.LineString,
            source.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        roundabout_expression_string = self.parameterAsExpression(parameters, self.EXPRESSION, context)

        # step 1 - find all roundabouts
        exp = QgsExpression(roundabout_expression_string)
        expression_context = self.createExpressionContext(parameters, context, source)
        exp.prepare(expression_context)

        roundabouts = []
        not_roundabouts = {}
        not_roundabout_index = QgsSpatialIndex()

        total = 10.0 / source.featureCount() if source.featureCount() else 0
        features = source.getFeatures()

        id = 1
        for current, feature in enumerate(features):
            if feedback.isCanceled():
                break

            def add_feature(f, id, geom, is_roundabout):
                output_feature = QgsFeature(f)
                output_feature.setGeometry(geom)
                output_feature.setId(id)
                if is_roundabout:
                    roundabouts.append(output_feature)
                else:
                    not_roundabouts[output_feature.id()] = output_feature
                    not_roundabout_index.addFeature(output_feature)

            expression_context.setFeature(feature)

            is_roundabout = exp.evaluate(expression_context)
            if not feature.geometry().wkbType() == QgsWkbTypes.LineString:
                geom = feature.geometry()
                for p in geom.parts():
                    add_feature(feature, id, QgsGeometry(p.clone()), is_roundabout)
                    id += 1
            else:
                add_feature(feature, id, feature.geometry(), is_roundabout)
                id += 1

            # Update the progress bar
            feedback.setProgress(int(current * total))

        feedback.pushInfo(self.tr('Found {} roundabout parts'.format(len(roundabouts))))
        feedback.pushInfo(self.tr('Found {} not roundabouts'.format(len(not_roundabouts))))

        if feedback.isCanceled():
            return {self.OUTPUT: dest_id}

        all_roundabouts = QgsGeometry.unaryUnion([r.geometry() for r in roundabouts])
        feedback.setProgress(20)
        all_roundabouts = all_roundabouts.mergeLines()
        feedback.setProgress(25)

        total = 70.0 / all_roundabouts.constGet().numGeometries() if all_roundabouts.isMultipart() else 1

        for current, roundabout in enumerate(all_roundabouts.parts()):
            touching = not_roundabout_index.intersects(roundabout.boundingBox())
            if not touching:
                continue

            if feedback.isCanceled():
                break

            roundabout_engine = QgsGeometry.createGeometryEngine(roundabout)
            roundabout_engine.prepareGeometry()
            roundabout_geom = QgsGeometry(roundabout.clone())
            roundabout_centroid = roundabout_geom.centroid()

            other_points = []

            # find all touching roads, and move the touching part to the centroid
            for t in touching:
                touching_geom = not_roundabouts[t].geometry()
                touching_road = touching_geom.constGet().clone()
                if not roundabout_engine.touches(touching_road):
                    # print('not touching!!')
                    continue

                # work out if start or end of line touched the roundabout
                nearest = roundabout_geom.nearestPoint(touching_geom)
                dist, v = touching_geom.closestVertexWithContext(nearest.asPoint())

                if v == 0:
                    # started at roundabout
                    other_points.append((touching_road.endPoint(), True, t))
                else:
                    # ended at roundabout
                    other_points.append((touching_road.startPoint(), False, t))

            if not other_points:
                continue

            # see if any incoming segments originate at the same place ("V" patterns)
            averaged = set()
            for point1, started_at_roundabout1, id1 in other_points:
                if id1 in averaged:
                    continue

                if feedback.isCanceled():
                    break

                parts_to_average = [id1]
                for point2, _, id2 in other_points:
                    if id2 == id1:
                        continue

                    if point2 != point1:
                        # todo tolerance?
                        continue

                    parts_to_average.append(id2)

                if len(parts_to_average) == 1:
                    # not a <O pattern, just a round coming straight to the roundabout
                    line = not_roundabouts[id1].geometry().constGet().clone()
                    if started_at_roundabout1:
                        # extend start of line to roundabout centroid
                        line.moveVertex(QgsVertexId(0, 0, 0), roundabout_centroid.constGet())
                    else:
                        # extend end of line to roundabout centroid
                        line.moveVertex(QgsVertexId(0, 0, line.numPoints() - 1), roundabout_centroid.constGet())

                    not_roundabout_index.deleteFeature(not_roundabouts[parts_to_average[0]])
                    not_roundabouts[parts_to_average[0]].setGeometry(QgsGeometry(line))
                    not_roundabout_index.addFeature(not_roundabouts[parts_to_average[0]])

                elif len(parts_to_average) == 2:
                    # <O pattern
                    src_part, other_part = parts_to_average
                    averaged.add(src_part)
                    averaged.add(other_part)

                    averaged_line = GeometryUtils.average_linestrings(not_roundabouts[src_part].geometry().constGet(),
                                                                      not_roundabouts[other_part].geometry().constGet())

                    if started_at_roundabout1:
                        # extend start of line to roundabout centroid
                        averaged_line.moveVertex(QgsVertexId(0, 0, 0), roundabout_centroid.constGet())
                    else:
                        # extend end of line to roundabout centroid
                        averaged_line.moveVertex(QgsVertexId(0, 0, averaged_line.numPoints() - 1),
                                                 roundabout_centroid.constGet())

                    not_roundabout_index.deleteFeature(not_roundabouts[src_part])
                    not_roundabouts[src_part].setGeometry(QgsGeometry(averaged_line))
                    not_roundabout_index.addFeature(not_roundabouts[src_part])

                    not_roundabout_index.deleteFeature(not_roundabouts[other_part])
                    del not_roundabouts[other_part]

            feedback.setProgress(25 + int(current * total))

        total = 5.0 / len(not_roundabouts)
        current = 0
        for _, f in not_roundabouts.items():
            if feedback.isCanceled():
                break

            sink.addFeature(f, QgsFeatureSink.FastInsert)
            current += 1
            feedback.setProgress(95 + int(current * total))

        return {self.OUTPUT: dest_id}


class RemoveCuldesacsAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    THRESHOLD = 'THRESHOLD'
    OUTPUT = 'OUTPUT'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return RemoveCuldesacsAlgorithm()

    def name(self):
        return 'removeculdesacs'

    def displayName(self):
        return self.tr('Remove cul-de-sacs')

    def group(self):
        return self.tr('Road networks')

    def groupId(self):
        return 'road'

    def shortHelpString(self):
        return self.tr("Generalizes a road network by removing cul-de-sacs")

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr('Input layer'),
                [QgsProcessing.TypeVectorLine]
            )
        )

        self.addParameter(
            QgsProcessingParameterDistance(
                self.THRESHOLD,
                self.tr('Minimum length to retain'),
                0.0003, self.INPUT, minValue=0)
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Output layer')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(
            parameters,
            self.INPUT,
            context
        )

        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            source.fields(),
            source.wkbType(),
            source.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        threshold = self.parameterAsDouble(parameters, self.THRESHOLD, context)

        index = QgsSpatialIndex()
        roads = {}

        total = 10.0 / source.featureCount() if source.featureCount() else 0
        features = source.getFeatures()

        for current, feature in enumerate(features):
            if feedback.isCanceled():
                break

            index.addFeature(feature)
            roads[feature.id()] = feature

            feedback.setProgress(int(current * total))

        total = 90.0 / len(roads)
        removed = 0
        current = 0
        for id, f in roads.items():
            if feedback.isCanceled():
                break

            current += 1
            if f.geometry().length() >= threshold:
                sink.addFeature(f, QgsFeatureSink.FastInsert)
                feedback.setProgress(10 + int(current * total))
                continue

            touching_candidates = index.intersects(f.geometry().boundingBox())
            if len(touching_candidates) == 1:
                # small street, touching nothing but itself -- kill it!
                removed += 1
                feedback.setProgress(10 + int(current * total))
                continue

            if not f.geometry().isMultipart():
                candidate = f.geometry().constGet().clone()
            else:
                if f.geometry().constGet().numGeometries() > 1:
                    raise QgsProcessingException(self.tr('Only single-part geometries are supported'))
                candidate = f.geometry().constGet().geometryN(0).clone()

            candidate_start = candidate.startPoint()
            candidate_end = candidate.endPoint()
            start_engine = QgsGeometry.createGeometryEngine(candidate_start)
            end_engine = QgsGeometry.createGeometryEngine(candidate_end)
            touching_start = False
            touching_end = False
            for t in touching_candidates:
                if t == id:
                    continue

                if start_engine.intersects(roads[t].geometry().constGet()):
                    touching_start = True
                if end_engine.intersects(roads[t].geometry().constGet()):
                    touching_end = True

                if touching_start and touching_end:
                    break

            feedback.setProgress(10 + int(current * total))
            if touching_start and touching_end:
                # keep it, it joins two roads
                sink.addFeature(f, QgsFeatureSink.FastInsert)
                continue
            else:
                removed += 1

        feedback.pushInfo(self.tr('Removed {} cul-de-sacs'.format(removed)))

        return {self.OUTPUT: dest_id}


class RemoveCrossRoadsAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    FIELDS = 'FIELDS'
    THRESHOLD = 'THRESHOLD'
    OUTPUT = 'OUTPUT'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return RemoveCrossRoadsAlgorithm()

    def name(self):
        return 'removecrossroads'

    def displayName(self):
        return self.tr('Remove cross roads')

    def group(self):
        return self.tr('Road networks')

    def groupId(self):
        return 'road'

    def shortHelpString(self):
        return self.tr("Generalizes a road network by removing cross roads")

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr('Input layer'),
                [QgsProcessing.TypeVectorLine]
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.FIELDS,
                self.tr('Attributes which identify unique roads'), allowMultiple=True,
                parentLayerParameterName=self.INPUT
            )
        )

        self.addParameter(
            QgsProcessingParameterDistance(
                self.THRESHOLD,
                self.tr('Maximum length for candidates'),
                0.0003, self.INPUT, minValue=0)
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Output layer')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(
            parameters,
            self.INPUT,
            context
        )

        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            source.fields(),
            source.wkbType(),
            source.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        threshold = self.parameterAsDouble(parameters, self.THRESHOLD, context)
        fields = self.parameterAsFields(parameters, self.FIELDS, context)
        field_indices = [source.fields().lookupField(f) for f in fields]
        index = QgsSpatialIndex()
        roads = {}

        total = 10.0 / source.featureCount() if source.featureCount() else 0
        features = source.getFeatures()

        for current, feature in enumerate(features):
            if feedback.isCanceled():
                break

            index.addFeature(feature)
            roads[feature.id()] = feature

            feedback.setProgress(int(current * total))

        total = 90.0 / len(roads)
        current = 0
        removed = 0
        for id, f in roads.items():
            if feedback.isCanceled():
                break

            current += 1

            if f.geometry().length() >= threshold:
                sink.addFeature(f, QgsFeatureSink.FastInsert)
                feedback.setProgress(10 + int(current * total))
                continue

            # we mark identify a cross road because either side is touched by at least two other features
            # with matching identifier attributes

            candidate_attrs = [f.attributes()[i] for i in field_indices]

            touching_candidates = index.intersects(f.geometry().boundingBox())
            if not f.geometry().isMultipart():
                candidate = f.geometry().constGet().clone()
            else:
                if f.geometry().constGet().numGeometries() > 1:
                    raise QgsProcessingException(self.tr('Only single-part geometries are supported'))
                candidate = f.geometry().constGet().geometryN(0).clone()

            candidate_start = candidate.startPoint()
            candidate_end = candidate.endPoint()
            start_engine = QgsGeometry.createGeometryEngine(candidate_start)
            end_engine = QgsGeometry.createGeometryEngine(candidate_end)
            touching_start_count = 0
            touching_end_count = 0
            for t in touching_candidates:
                if t == id:
                    continue

                other = roads[t]

                other_attrs = [other.attributes()[i] for i in field_indices]
                if other_attrs != candidate_attrs:
                    continue

                if other.geometry().length() < threshold:
                    continue

                if start_engine.intersects(roads[t].geometry().constGet()):
                    touching_start_count += 1
                if end_engine.intersects(roads[t].geometry().constGet()):
                    touching_end_count += 1

                if touching_start_count >= 2 and touching_end_count >= 2:
                    break

            feedback.setProgress(10 + int(current * total))

            if touching_start_count >= 2 and touching_end_count >= 2:
                # kill it
                removed += 1
            else:
                sink.addFeature(f, QgsFeatureSink.FastInsert)

        feedback.pushInfo(self.tr('Removed {} cross roads'.format(removed)))

        return {self.OUTPUT: dest_id}


class CollapseDualCarriagewayAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    FIELDS = 'FIELDS'
    THRESHOLD = 'THRESHOLD'
    OUTPUT = 'OUTPUT'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return CollapseDualCarriagewayAlgorithm()

    def name(self):
        return 'collapsedualcarriageway'

    def displayName(self):
        return self.tr('Collapse dual carriageways')

    def group(self):
        return self.tr('Road networks')

    def groupId(self):
        return 'road'

    def shortHelpString(self):
        return self.tr("Generalizes a road network by collapsing dual carriageways")

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr('Input layer'),
                [QgsProcessing.TypeVectorLine]
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.FIELDS,
                self.tr('Attributes which identify unique roads'), allowMultiple=True,
                parentLayerParameterName=self.INPUT
            )
        )

        self.addParameter(
            QgsProcessingParameterDistance(
                self.THRESHOLD,
                self.tr('Maximum separation to collapse'),
                0.0003, self.INPUT, minValue=0)
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Output layer')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(
            parameters,
            self.INPUT,
            context
        )

        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            source.fields(),
            source.wkbType(),
            source.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        threshold = self.parameterAsDouble(parameters, self.THRESHOLD, context)
        fields = self.parameterAsFields(parameters, self.FIELDS, context)
        field_indices = [source.fields().lookupField(f) for f in fields]
        index = QgsSpatialIndex()
        roads = {}

        total = 10.0 / source.featureCount() if source.featureCount() else 0
        features = source.getFeatures()

        for current, feature in enumerate(features):
            if feedback.isCanceled():
                break

            index.addFeature(feature)
            roads[feature.id()] = feature

            feedback.setProgress(int(current * total))

        collapsed = {}
        processed = set()

        total = 85.0 / len(roads)
        current = 0
        for id, f in roads.items():
            if feedback.isCanceled():
                break

            current += 1
            feedback.setProgress(10 + current * total)

            if id in processed:
                continue

            box = f.geometry().boundingBox()
            box.grow(threshold)

            similar_candidates = index.intersects(box)
            if not similar_candidates:
                collapsed[id] = f
                processed.add(id)
                continue

            candidate = f.geometry()
            candidate_attrs = [f.attributes()[i] for i in field_indices]

            parts = []

            for t in similar_candidates:
                if t == id:
                    continue

                other = roads[t]
                other_attrs = [other.attributes()[i] for i in field_indices]
                if other_attrs != candidate_attrs:
                    continue

                dist = candidate.hausdorffDistance(other.geometry())
                if dist < threshold:
                    parts.append(t)

            if len(parts) == 0:
                collapsed[id] = f
                continue

            # todo fix this
            if len(parts) > 1:
                continue
            assert len(parts) == 1, len(parts)

            other = roads[parts[0]].geometry()
            averaged = QgsGeometry(GeometryUtils.average_linestrings(candidate.constGet(), other.constGet()))

            # reconnect touching lines
            bbox = candidate.boundingBox()
            bbox.combineExtentWith(other.boundingBox())
            touching_candidates = index.intersects(bbox)

            for touching_candidate in touching_candidates:
                if touching_candidate == id or touching_candidate == parts[0]:
                    continue

                # print(touching_candidate)

                touching_candidate_geom = roads[touching_candidate].geometry()
                # either the start or end of touching_candidate_geom touches candidate
                start = QgsGeometry(touching_candidate_geom.constGet().startPoint())
                end = QgsGeometry(touching_candidate_geom.constGet().endPoint())

                moved_start = False
                moved_end = False
                for cc in [candidate, other]:
                    start_line = start.shortestLine(cc)
                    if start_line.length() < threshold:
                        # start touches, move to touch averaged line
                        averaged_line = start.shortestLine(averaged)
                        new_start = averaged_line.constGet().endPoint()
                        touching_candidate_geom.get().moveVertex(QgsVertexId(0, 0, 0), new_start)
                        # print('moved start')
                        moved_start = True
                        continue
                    end_line = end.shortestLine(cc)
                    if end_line.length() < threshold:
                        # endtouches, move to touch averaged line
                        averaged_line = end.shortestLine(averaged)
                        new_end = averaged_line.constGet().endPoint()
                        touching_candidate_geom.get().moveVertex(
                            QgsVertexId(0, 0, touching_candidate_geom.constGet().numPoints() - 1), new_end)
                        # print('moved end')
                        moved_end = True
                        #break

                index.deleteFeature(roads[touching_candidate])
                if moved_start and moved_end:
                    if touching_candidate in collapsed:
                        del collapsed[touching_candidate]
                    processed.add(touching_candidate)
                else:
                    roads[touching_candidate].setGeometry(touching_candidate_geom)
                    index.addFeature(roads[touching_candidate])
                    if touching_candidate in collapsed:
                        collapsed[touching_candidate].setGeometry(touching_candidate_geom)

            index.deleteFeature(f)
            index.deleteFeature(roads[parts[0]])

            ff = QgsFeature(roads[parts[0]])
            ff.setGeometry(averaged)
            index.addFeature(ff)
            roads[ff.id()] = ff

            ff = QgsFeature(f)
            ff.setGeometry(averaged)
            index.addFeature(ff)
            roads[id] = ff

            collapsed[id] = ff
            processed.add(id)
            processed.add(parts[0])

        total = 5.0 / len(processed)
        current = 0
        for _, f in collapsed.items():
            if feedback.isCanceled():
                break

            sink.addFeature(f, QgsFeatureSink.FastInsert)
            current += 1
            feedback.setProgress(95 + int(current * total))

        return {self.OUTPUT: dest_id}


class AverageLinesAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return AverageLinesAlgorithm()

    def name(self):
        return 'averagelines'

    def displayName(self):
        return self.tr('Average linestrings')

    def flags(self):
        f = super().flags()
        f |= QgsProcessingAlgorithm.FlagSupportsInPlaceEdits
        return f

    def group(self):
        return self.tr('General')

    def groupId(self):
        return 'general'

    def shortHelpString(self):
        return self.tr("Creates an average of a set of linestring inputs")

    def supportInPlaceEdit(self, layer):
        return layer.type() == QgsMapLayer.VectorLayer and layer.geometryType() == QgsWkbTypes.LineGeometry

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr('Input layer'),
                [QgsProcessing.TypeVectorLine]
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Output layer')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(
            parameters,
            self.INPUT,
            context
        )

        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            source.fields(),
            source.wkbType(),
            source.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        total = 100.0 / source.featureCount() if source.featureCount() else 0
        features = source.getFeatures()

        linestring = None
        f = None
        weight = 0
        for current, feature in enumerate(features):
            if feedback.isCanceled():
                break

            if not feature.geometry().isMultipart():
                candidate = feature.geometry().constGet().clone()
            else:
                if feature.geometry().constGet().numGeometries() > 1:
                    raise QgsProcessingException(self.tr('Only single-part geometries are supported'))
                candidate = feature.geometry().constGet().geometryN(0).clone()

            if linestring is None:
                linestring = candidate.clone()
                f = QgsFeature(feature)
            else:
                weight += 1
                linestring = GeometryUtils.average_linestrings(linestring, candidate, weight)


        f.setGeometry(linestring)
        sink.addFeature(f, QgsFeatureSink.FastInsert)

        return {self.OUTPUT: dest_id}
