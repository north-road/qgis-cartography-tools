def break_lines_into_similar_segments(inputs, min_dist):
    changed = True
    outputs = []
    iter = 0
    while inputs:
        # print(len(inputs))
        iter += 1
        if iter > 300:
            print(len(inputs))
            return
        g = inputs[0]

        inputs = inputs[1:]

        changed = False
        to_compare = inputs[:]
        to_compare.extend(outputs)
        for other in to_compare:
            if g.shortestLine(other).length() > min_dist:
                continue

            parts = [QgsGeometry(p.clone()) for p in split_to_similar_sections(g, other, min_dist)]
            if len(parts) > 2:
                ok = True
                for p in parts:
                    if not p.constGet().length() > min_dist * .5:
                        ok = False
                        break
                if ok:
                    inputs.extend(parts)
                    changed = True
            continue
            for pp in (0, 1):
                # print(pp)
                if pp == 0:
                    ref_point = QgsPointXY(other.constGet().startPoint())
                else:
                    ref_point = QgsPointXY(other.constGet().endPoint())

                dist, closest_point, vertex, left_of = g.closestSegmentWithContext(ref_point)
                if dist > min_dist or dist == 0:
                    continue

                # print(vertex)
                # if vertex != 1 and vertex != g.constGet().numPoints() - 1:
                dd = g.lineLocatePoint(QgsGeometry.fromPointXY(closest_point))

                dddd = QgsGeometry(g.constGet().curveSubstring(0, dd))
                dddd2 = QgsGeometry(g.constGet().curveSubstring(dd, g.constGet().length()))

                if dddd.constGet().length() > min_dist * .5 and dddd2.constGet().length() > min_dist * .5:
                    # print(dddd.length(), dddd2.length())
                    # print('splitting')
                    inputs.append(dddd)
                    inputs.append(dddd2)
                    changed = True
                    break

            # print(changed)
            if changed:
                break

        if not changed:
            outputs.append(g)

    return outputs


def split_to_similar_sections(g1, g2, dist):
    buffer = g2.buffer(dist, 0, QgsGeometry.CapFlat, QgsGeometry.JoinStyleMiter, 20)
    # f = QgsFeature()
    # f.setGeometry(buffer)
    # polys.dataProvider().addFeature(f)
    u1 = g1.intersection(buffer)
    d1 = g1.difference(buffer)

    parts1 = [p.clone() for p in u1.parts() if p.wkbType() == QgsWkbTypes.LineString and p.length() > 0]
    parts1.extend([p.clone() for p in d1.parts() if p.wkbType() == QgsWkbTypes.LineString and p.length() > 0])

    # if we get two parts, and one is <= DIST long, we don't split (T intersection)
    if len(parts1) == 2 and (parts1[0].length() <= dist * 1.01 or parts1[1].length() <= dist * 1.01):
        return [g1.constGet().clone()]

    return parts1


def average_linestrings(line1, line2):
    g1 = line1.clone()
    g2 = line2.clone()

    # project points from g2 onto g1
    for n in range(g2.numPoints()):
        v = g2.pointN(n)

        dist, pt, after, leftOf = g1.closestSegment(v)
        g1.insertVertex(QgsVertexId(0, 0, after.vertex), pt)

    # iterate through vertices in g1
    out = []
    for n in range(g1.numPoints()):
        v = g1.pointN(n)
        dist, pt, after, leftOf = g2.closestSegment(v)
        # average pts

        x = (v.x() + pt.x()) / 2
        y = (v.y() + pt.y()) / 2
        out.append(QgsPoint(x, y))

    return QgsLineString(out)


layer = QgsProject.instance().mapLayersByName('baseline_roads_and_tracks')[0]
output = QgsProject.instance().mapLayersByName('output')[0]
output.dataProvider().truncate()

# step 1 - find all roundabouts

request = QgsFeatureRequest().setFilterRect(iface.mapCanvas().extent())
roundabouts = layer.getSelectedFeatures(request)
filter_exp = QgsExpression('ROADTYPE<=5')
exp = QgsExpression('street=\'ROUNDABOUT\'')
context = layer.createExpressionContext()
exp.prepare(context)
filter_exp.prepare(context)
roundabouts = []
not_roundabouts = {}

not_roundabout_index = QgsSpatialIndex()

for f in layer.getFeatures(request):
    context.setFeature(f)
    if not filter_exp.evaluate(context):
        continue

    if not isinstance(f.geometry().constGet(), QgsLineString):
        if f.geometry().constGet().numGeometries() > 1:
            assert False, 'Not multipart!'
        f.setGeometry(f.geometry().constGet().geometryN(0).clone())

    if exp.evaluate(context):
        roundabouts.append(f)
    else:
        not_roundabouts[f.id()] = f
        not_roundabout_index.addFeature(f)

print('found {} roundabout parts'.format(len(roundabouts)))
print('found {} not roundabouts'.format(len(not_roundabouts)))

all_roundabouts = QgsGeometry.unaryUnion([r.geometry() for r in roundabouts])
all_roundabouts = all_roundabouts.mergeLines()

for roundabout in all_roundabouts.parts():
    touching = not_roundabout_index.intersects(roundabout.boundingBox())
    if not touching:
        continue

    this_touching_parts = []
    roundabout_engine = QgsGeometry.createGeometryEngine(roundabout)
    roundabout_engine.prepareGeometry()
    roundabout_geom = QgsGeometry(roundabout.clone())
    roundabout_centroid = roundabout_geom.centroid()

    other_points = []

    # find all touching roads, and move the touching part to the centroid
    for t in touching:
        touching_geom = not_roundabouts[t].geometry()
        touching_road = touching_geom.constGet()[0].clone() if isinstance(touching_geom.constGet(),
                                                                          QgsMultiLineString) else touching_geom.constGet().clone()
        if not roundabout_engine.intersects(touching_road):
            # print('not touching!!')
            continue

        # work out if start or end of line touched the roundabout
        nearest = roundabout_geom.nearestPoint(touching_geom)
        dist, v = touching_geom.closestVertexWithContext(QgsPointXY(nearest.constGet().x(),
                                                                    nearest.constGet().y()))

        if v == 0:
            # print('started at roundabout')
            # touching_road.insertVertex(QgsVertexId(0,0,0), roundabout_centroid.constGet())
            other_points.append((touching_road.endPoint(), False, t))
        else:
            # print('ended at roundabout')
            # touching_road.insertVertex(QgsVertexId(0,0,touching_road.numPoints()), roundabout_centroid.constGet())
            other_points.append((touching_road.startPoint(), True, t))

        not_roundabouts[t].setGeometry(QgsGeometry(touching_road.clone()))

    # see if any incoming segments originate at the same place ("V" patterns)
    averaged = set()
    # print(other_points)
    for point1, is_start1, id1 in other_points:
        if id1 in averaged:
            continue

        parts_to_average = [id1]
        for point2, is_start2, id2 in other_points:
            if id2 == id1:
                continue

            if point2 != point1:
                # todo tolerance?
                continue

            parts_to_average.append(id2)

        if len(parts_to_average) == 1:
            line = not_roundabouts[parts_to_average[0]].geometry().constGet().clone()
            if not is_start1:
                line.insertVertex(QgsVertexId(0, 0, 0), roundabout_centroid.constGet())
            else:
                line.insertVertex(QgsVertexId(0, 0, line.numPoints()), roundabout_centroid.constGet())
            not_roundabouts[parts_to_average[0]].setGeometry(QgsGeometry(line))
            continue

        if len(parts_to_average) > 2:
            continue
        assert len(parts_to_average) == 2
        src_part, other_part = parts_to_average
        averaged.add(src_part)
        averaged.add(other_part)

        averaged_line = average_linestrings(not_roundabouts[src_part].geometry().constGet(),
                                            not_roundabouts[other_part].geometry().constGet())

        if not is_start1:
            averaged_line.insertVertex(QgsVertexId(0, 0, 0), roundabout_centroid.constGet())
        else:
            averaged_line.insertVertex(QgsVertexId(0, 0, averaged_line.numPoints()), roundabout_centroid.constGet())

        not_roundabouts[src_part].setGeometry(QgsGeometry(averaged_line))
        del not_roundabouts[other_part]

# iteration 2: remove small dead-end roads
index = QgsSpatialIndex()
roads = {}
for id, f in not_roundabouts.items():
    index.addFeature(f)
    roads[id] = f

# look for small roads, which only touch on one side
THRESHOLD = 0.0003
filtered = {}
for id, f in roads.items():
    if f.geometry().length() >= THRESHOLD:
        filtered[id] = f
        continue

    touching_candidates = index.intersects(f.geometry().boundingBox())
    if not touching_candidates:
        # kill it!
        continue

    candidate = f.geometry().constGet().clone()
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

    if touching_start and touching_end:
        # keep it, it joins two roads
        filtered[id] = f
        continue

# dissolve and split

FIELD = 'STREET'

dissolved_parts = {}
features = {}
for id, f in filtered.items():
    if not f[FIELD] in dissolved_parts:
        dissolved_parts[f[FIELD]] = [f.geometry()]
        features[f[FIELD]] = f
    else:
        dissolved_parts[f[FIELD]].append(f.geometry())

DUAL_THRESHOLD = 0.0005
TOUCHING_THRESHOLD = 0.0000001

idx = 1
named_parts = {}
dissolved_index = QgsSpatialIndex()
for street, parts in dissolved_parts.items():
    dissolved = QgsGeometry.unaryUnion(parts)
    dissolved = dissolved.mergeLines()

    new_parts = [QgsGeometry(p.clone()) for p in dissolved.parts()]
    # print(street + ' ' + str(len(new_parts)))
    new_parts2 = break_lines_into_similar_segments(new_parts, DUAL_THRESHOLD * 1.1)

    for p in new_parts2:
        f = QgsFeature(features[street])
        f.setId(idx)
        f.setGeometry(p)
        dissolved_index.addFeature(f)
        named_parts[idx] = f
        idx += 1

# collapse dual carriage


collapsed = {}
processed = set()
for id, f in named_parts.items():
    if id in processed:
        continue

    box = f.geometry().boundingBox()
    box.grow(DUAL_THRESHOLD)

    similar_candidates = dissolved_index.intersects(box)
    if not similar_candidates:
        collapsed[id] = f
        processed.add(id)
        continue

    candidate = f.geometry()

    parts = []

    for t in similar_candidates:
        if t == id:
            continue

        if named_parts[t][FIELD] != f[FIELD]:
            continue

        dist = candidate.hausdorffDistance(named_parts[t].geometry())
        if dist < DUAL_THRESHOLD:
            parts.append(t)

    if len(parts) == 0:
        collapsed[id] = f
        continue

    if len(parts) > 1:
        continue
    assert len(parts) == 1, len(parts)
    other = named_parts[parts[0]].geometry()
    averaged = QgsGeometry(average_linestrings(candidate.constGet(), other.constGet()))

    # reconnect touching lines
    touching_candidates = dissolved_index.intersects(candidate.boundingBox())

    for touching_candidate in touching_candidates:
        if touching_candidate == id or touching_candidate == parts[0]:
            continue

        # print(touching_candidate)

        touching_candidate_geom = named_parts[touching_candidate].geometry()
        # either the start or end of touching_candidate_geom touches candidate
        start = QgsGeometry(touching_candidate_geom.constGet().startPoint())
        end = QgsGeometry(touching_candidate_geom.constGet().endPoint())

        for cc in [candidate, other]:
            start_line = start.shortestLine(cc)
            if start_line.length() < TOUCHING_THRESHOLD:
                # start touches, move to touch averaged line
                averaged_line = start.shortestLine(averaged)
                new_start = averaged_line.constGet().endPoint()
                touching_candidate_geom.get().moveVertex(QgsVertexId(0, 0, 0), new_start)
                # print('moved start')
                break
            end_line = end.shortestLine(cc)
            if end_line.length() < TOUCHING_THRESHOLD:
                # endtouches, move to touch averaged line
                averaged_line = end.shortestLine(averaged)
                new_end = averaged_line.constGet().endPoint()
                touching_candidate_geom.get().moveVertex(
                    QgsVertexId(0, 0, touching_candidate_geom.constGet().numPoints() - 1), new_end)
                # print('moved end')
                break

        named_parts[touching_candidate].setGeometry(touching_candidate_geom)
        if touching_candidate in collapsed:
            collapsed[touching_candidate].setGeometry(touching_candidate_geom)

    f.setGeometry(averaged)
    collapsed[id] = f
    processed.add(id)
    processed.add(parts[0])

# simplify
simplifier = QgsMapToPixelSimplifier(QgsMapToPixelSimplifier.SimplifyGeometry, 0.00005,
                                     QgsMapToPixelSimplifier.Visvalingam)
for id, f in filtered.items():
    filtered[id].setGeometry(simplifier.simplify(f.geometry()))

for _, f in collapsed.items():
    f.setAttributes([])
    output.dataProvider().addFeature(f)

iface.mapCanvas().refreshAllLayers()


