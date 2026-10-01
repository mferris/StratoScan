import SwiftUI

/// The whole radar — rings, sweep, aircraft blips, and collision-avoiding
/// labels with leader lines — drawn as one Canvas every frame. Unlike the
/// web version (Canvas for blips/rings, separate DOM divs for labels,
/// because HTML canvas can't measure DOM text), SwiftUI's GraphicsContext
/// can both measure and draw text, so everything lives in a single Canvas
/// here — simpler than the two-layer split the browser needed.
struct RadarView: View {
    @ObservedObject var viewModel: RadarViewModel
    /// Diameter of the circular rings/sweep/map — smaller than the full
    /// Canvas frame on purpose, so labels have real margin to roam into
    /// (unclipped, unlike the circular map/rings) without being cramped.
    let diameter: CGFloat
    /// Text and symbols, scaled up on an iPad's bigger screen (#39); 1 on a phone.
    var uiScale: CGFloat = 1

    private let rangeRings = 4
    @State private var pinchStart: (range: Double, centre: (east: Double, north: Double), anchor: CGPoint)?
    @State private var dragStart: (translation: CGSize, centre: (east: Double, north: Double))?
    private let sweepSpeed: Double = 0.008 * 60 // radians/sec (web version: 0.008/frame @ ~60fps)
    private let smoothTau = 0.35
    private let labelGap: CGFloat = 10
    private let labelMargin: CGFloat = 4
    private let labelSpringTau = 0.22
    private let labelSeparationPasses = 8

    // The chosen theme's colours (Palette), read as each frame is drawn.
    private var pal: Palette { Palette.current }
    private var colorRing: Color { pal.ring }
    private var colorRingBright: Color { pal.ringBright }
    private var colorSweep: Color { pal.sweep }
    private var colorTextDim: Color { pal.textDim }
    private var colorLow: Color { pal.low }

    var body: some View {
        GeometryReader { geo in
            TimelineView(.animation) { timeline in
                Canvas { context, canvasSize in
                    render(context: &context, canvasSize: canvasSize, now: timeline.date)
                }
            }
            .drawingGroup()
            .contentShape(Rectangle())
            // Double-tap zooms in a step on the spot tapped; a single tap picks
            // an aircraft; a pinch zooms from the full ring down to about a
            // mile, keeping the spot under the fingers where it is; a drag
            // moves the zoomed view (roadmap 2.9).
            .gesture(SpatialTapGesture(count: 2).onEnded { tap in
                viewModel.zoom(to: viewModel.rangeNm / 2, anchor: anchor(tap.location, geo.size),
                               from: (viewModel.rangeNm, viewModel.viewCentre))
            }.exclusively(before: SpatialTapGesture().onEnded { tap in
                viewModel.selectedHex = viewModel.plane(at: tap.location)?.hex
            }))
            .simultaneousGesture(MagnifyGesture()
                .onChanged { value in
                    if pinchStart == nil {
                        pinchStart = (viewModel.rangeNm, viewModel.viewCentre, anchor(value.startLocation, geo.size))
                    }
                    guard let s = pinchStart else { return }
                    viewModel.zoom(to: s.range / Double(value.magnification), anchor: s.anchor, from: (s.range, s.centre))
                }
                .onEnded { _ in pinchStart = nil })
            .simultaneousGesture(DragGesture(minimumDistance: 10)
                .onChanged { value in
                    // A pinch moves both fingers; the pinch decides, and the
                    // drag starts again from wherever the pinch left the view.
                    guard pinchStart == nil, viewModel.rangeNm < viewModel.ringNm - 0.01 else { dragStart = nil; return }
                    if dragStart == nil {
                        // Dragging a view that follows something lets go of it.
                        let c = viewModel.viewCentre
                        viewModel.followHex = nil
                        viewModel.centreOnMe = false
                        viewModel.setPan(c)
                        dragStart = (value.translation, viewModel.pan)
                    }
                    guard let s = dragStart else { return }
                    let perPoint = viewModel.rangeNm / Double(diameter * 0.44)
                    viewModel.setPan((s.centre.east - Double(value.translation.width - s.translation.width) * perPoint,
                                      s.centre.north + Double(value.translation.height - s.translation.height) * perPoint))
                }
                .onEnded { _ in dragStart = nil })
        }
    }

    /// A point on screen as a fraction of the radar's radius from its middle.
    private func anchor(_ p: CGPoint, _ size: CGSize) -> CGPoint {
        let r = diameter * 0.44
        return CGPoint(x: (p.x - size.width / 2) / r, y: (p.y - size.height / 2) / r)
    }

    private func render(context: inout GraphicsContext, canvasSize: CGSize, now: Date) {
        let cx = canvasSize.width / 2
        let cy = canvasSize.height / 2
        let r = diameter * 0.44

        let dt: Double
        if let last = viewModel.lastFrameTime {
            dt = min(0.25, max(0, now.timeIntervalSince(last)))
        } else {
            dt = 0
        }
        viewModel.lastFrameTime = now

        // Rings, crosshair and sweep belong to the ground, not the screen: they
        // centre on the radar and mark real distances from it, so zooming and
        // panning carry them along with the map (they used to stay put while
        // their labels changed, which said nothing about where you were).
        let k = r / CGFloat(viewModel.rangeNm)          // points per nm
        let c = viewModel.viewCentre
        let radar = CGPoint(x: cx - CGFloat(c.east) * k, y: cy + CGFloat(c.north) * k)
        // clipped to the map's circle (the whole diameter), which runs a little
        // past the 20 nm ring at full view
        let edge = diameter / 2
        let view = Path(ellipseIn: CGRect(x: cx - edge, y: cy - edge, width: edge * 2, height: edge * 2))
        context.drawLayer { ctx in
            ctx.clip(to: view)
            drawRings(&ctx, radar: radar, k: k, cx: cx, cy: cy, r: edge)
            drawSweep(&ctx, radar: radar, k: k)
        }
        drawCompass(&context, cx: cx, cy: cy, r: r)
        drawPlanes(&context, cx: cx, cy: cy, r: r, canvasSize: canvasSize, dt: dt)

        viewModel.sweepAngle += sweepSpeed * dt
        if viewModel.sweepAngle > .pi * 2 { viewModel.sweepAngle -= .pi * 2 }
    }

    // MARK: - Rings

    private func drawRings(_ context: inout GraphicsContext, radar: CGPoint, k: CGFloat, cx: CGFloat, cy: CGFloat, r: CGFloat) {
        let ring = CGFloat(viewModel.ringNm)
        let step = ring / CGFloat(rangeRings)                 // 5 nm
        var rings: [(nm: CGFloat, major: Bool)] = (1...rangeRings).map { (step * CGFloat($0), true) }
        // Close in, the 5 nm rings are off the screen: add one every nanomile
        // so there is always a distance to read.
        if viewModel.rangeNm <= 6 {
            rings += stride(from: 1, to: ring, by: 1).filter { $0.truncatingRemainder(dividingBy: step) != 0 }.map { (CGFloat($0), false) }
        }
        // brighter than the rings: zoomed in they sit over busy streets
        let labelColor = pal.ringLabel
        for (nm, major) in rings {
            let ringR = nm * k
            // skip rings wholly outside the view, or so big or small they're noise
            let d = hypot(radar.x - cx, radar.y - cy)
            if d - ringR > r || ringR - d > r * 1.02 || ringR < 6 { continue }
            var path = Path()
            path.addEllipse(in: CGRect(x: radar.x - ringR, y: radar.y - ringR, width: ringR * 2, height: ringR * 2))
            context.stroke(path, with: .color(nm == ring ? colorRingBright : colorRing.opacity(major ? 1 : 0.55)), lineWidth: 1)
            // The label sits where the ring crosses the line from the radar
            // toward the middle of the view, so it is on screen whenever the
            // ring is; straight north of the radar when they coincide.
            let toward = d > 1 ? CGPoint(x: (cx - radar.x) / d, y: (cy - radar.y) / d) : CGPoint(x: 0, y: -1)
            let at = CGPoint(x: radar.x + toward.x * ringR + 6, y: radar.y + toward.y * ringR + 4)
            if hypot(at.x - cx, at.y - cy) < r - 14 {
                context.draw(Text("\(Int(nm))nm").font(.system(size: 10 * uiScale, weight: .medium, design: .monospaced)).foregroundColor(labelColor),
                             at: at, anchor: .topLeading)
            }
        }

        // the crosshair: north-south and east-west through the radar
        let reach = ring * k
        var cross = Path()
        cross.move(to: CGPoint(x: radar.x, y: radar.y - reach)); cross.addLine(to: CGPoint(x: radar.x, y: radar.y + reach))
        cross.move(to: CGPoint(x: radar.x - reach, y: radar.y)); cross.addLine(to: CGPoint(x: radar.x + reach, y: radar.y))
        context.stroke(cross, with: .color(pal.crosshair), lineWidth: 1)

        var dot = Path()
        dot.addEllipse(in: CGRect(x: radar.x - 3, y: radar.y - 3, width: 6, height: 6))
        context.fill(dot, with: .color(colorSweep))
    }

    /// N, S, E, W stay at the edge of the view: they say which way is which,
    /// not where anything is.
    private func drawCompass(_ context: inout GraphicsContext, cx: CGFloat, cy: CGFloat, r: CGFloat) {
        let compassColor = pal.compass
        let compassFont = Font.system(size: 13 * uiScale, weight: .semibold)
        context.draw(Text("N").font(compassFont).foregroundColor(compassColor), at: CGPoint(x: cx, y: cy - r + 16), anchor: .center)
        context.draw(Text("S").font(compassFont).foregroundColor(compassColor), at: CGPoint(x: cx, y: cy + r - 10), anchor: .center)
        context.draw(Text("E").font(compassFont).foregroundColor(compassColor), at: CGPoint(x: cx + r - 12, y: cy + 5), anchor: .center)
        context.draw(Text("W").font(compassFont).foregroundColor(compassColor), at: CGPoint(x: cx - r + 12, y: cy + 5), anchor: .center)
    }

    // MARK: - Sweep

    /// The sweep turns about the radar, out to its 20 nm ring.
    private func drawSweep(_ context: inout GraphicsContext, radar: CGPoint, k: CGFloat) {
        let angle = viewModel.sweepAngle
        let r = CGFloat(viewModel.ringNm) * k
        let cx = radar.x, cy = radar.y
        var wedge = Path()
        wedge.addEllipse(in: CGRect(x: cx - r, y: cy - r, width: r * 2, height: r * 2))
        let gradient = Gradient(stops: [
            .init(color: colorSweep.opacity(0.35), location: 0),
            .init(color: colorSweep.opacity(0), location: 0.06),
            .init(color: colorSweep.opacity(0), location: 1),
        ])
        context.fill(wedge, with: .conicGradient(gradient, center: CGPoint(x: cx, y: cy), angle: .radians(angle - .pi / 2)))

        let lineEnd = CGPoint(x: cx + r * cos(angle), y: cy + r * sin(angle))
        var line = Path()
        line.move(to: CGPoint(x: cx, y: cy))
        line.addLine(to: lineEnd)
        context.drawLayer { ctx in
            ctx.addFilter(.shadow(color: colorSweep, radius: 4))
            ctx.stroke(line, with: .color(colorSweep), lineWidth: 2)
        }
    }

    // MARK: - Planes, labels, leader lines

    private func drawPlanes(_ context: inout GraphicsContext, cx: CGFloat, cy: CGFloat, r: CGFloat, canvasSize: CGSize, dt: Double) {
        let alpha = 1 - exp(-dt / smoothTau)
        let springAlpha = 1 - exp(-dt / labelSpringTau)
        let c = viewModel.viewCentre
        let inRange = viewModel.planes.values.filter { viewModel.distanceFromCentre($0) <= viewModel.rangeNm * 1.05 }

        // pass 1: motion + blips
        for p in inRange {
            p.bearing += Geo.bearingDelta(from: p.bearing, to: p.targetBearing) * alpha
            p.range += (p.targetRange - p.range) * alpha
            p.color = PlaneState.altColor(p.alt)

            // Placed relative to the view's centre -- the radar, or a followed
            // aircraft -- at the view's zoom (roadmap 2.9).
            let o = RadarViewModel.offset(p)
            p.anchorX = cx + CGFloat((o.east - c.east) / viewModel.rangeNm) * r
            p.anchorY = cy - CGFloat((o.north - c.north) / viewModel.rangeNm) * r

            drawBlip(&context, p: p)
        }

        let inView = inRange.filter { viewModel.distanceFromCentre($0) <= viewModel.rangeNm }
        // This phone, when the owner has asked to be shown.
        if let m = viewModel.meOffset {
            let mx = cx + CGFloat((m.east - c.east) / viewModel.rangeNm) * r
            let my = cy - CGFloat((m.north - c.north) / viewModel.rangeNm) * r
            if hypot(mx - cx, my - cy) <= r {
                let dot = Path(ellipseIn: CGRect(x: mx - 6, y: my - 6, width: 12, height: 12))
                context.fill(dot, with: .color(Color(hex: "#3b82f6")))
                context.stroke(dot, with: .color(.white), lineWidth: 2)
                context.draw(Text("YOU").font(.system(size: 9 * uiScale, weight: .bold, design: .monospaced))
                                .foregroundColor(Color(hex: "#93c5fd")),
                             at: CGPoint(x: mx, y: my + 14), anchor: .top)
            }
        }
        // When the view is centred elsewhere, mark where the radar is.
        if c.east != 0 || c.north != 0 {
            let rx = cx - CGFloat(c.east / viewModel.rangeNm) * r
            let ry = cy + CGFloat(c.north / viewModel.rangeNm) * r
            if hypot(rx - cx, ry - cy) <= r {
                let mark = Path(ellipseIn: CGRect(x: rx - 5, y: ry - 5, width: 10, height: 10))
                context.stroke(mark, with: .color(colorSweep), lineWidth: 1.5)
            }
        }
        // Labels off: only the tapped plane keeps one.
        let visible = viewModel.labelMode == .off ? inView.filter { $0.hex == viewModel.selectedHex } : inView
        for p in inView where !visible.contains(where: { $0 === p }) {
            p.labelX = nil; p.labelY = nil
        }

        // pass 2: measure labels, ease toward desired position
        for p in visible {
            let content = labelContent(for: p)
            let metrics = measure(content, context: context)
            p.labelW = metrics.size.width
            p.labelH = metrics.size.height

            let wantRight = p.anchorX < canvasSize.width * 0.78
            p.labelSide = wantRight ? .right : .left
            let desiredX = wantRight ? p.anchorX + labelGap : p.anchorX - labelGap - p.labelW
            let desiredY = p.anchorY - p.labelH / 2

            if p.labelX == nil {
                p.labelX = desiredX
                p.labelY = desiredY
            } else {
                p.labelX! += (desiredX - p.labelX!) * springAlpha
                p.labelY! += (desiredY - p.labelY!) * springAlpha
            }
        }

        // pass 3: push apart any labels that still overlap
        let arr = Array(visible)
        for _ in 0..<labelSeparationPasses {
            for i in 0..<arr.count {
                guard i + 1 < arr.count else { continue }
                for j in (i + 1)..<arr.count {
                    let a = arr[i], b = arr[j]
                    guard let ax = a.labelX, let ay = a.labelY, let bx = b.labelX, let by = b.labelY else { continue }
                    let overlapX = min(ax + a.labelW, bx + b.labelW) - max(ax, bx) + labelMargin
                    let overlapY = min(ay + a.labelH, by + b.labelH) - max(ay, by) + labelMargin
                    guard overlapX > 0, overlapY > 0 else { continue }

                    var dx = (bx + b.labelW / 2) - (ax + a.labelW / 2)
                    var dy = (by + b.labelH / 2) - (ay + a.labelH / 2)
                    if abs(dx) < 0.01 && abs(dy) < 0.01 {
                        let ang = Double(stableHash(a.hex + b.hex) % 360) * .pi / 180
                        dx = cos(ang); dy = sin(ang)
                    }

                    if overlapX < overlapY {
                        let push = overlapX / 2 * (dx < 0 ? -1 : 1)
                        a.labelX! -= push; b.labelX! += push
                    } else {
                        let push = overlapY / 2 * (dy < 0 ? -1 : 1)
                        a.labelY! -= push; b.labelY! += push
                    }
                }
            }
        }

        // pass 4: clamp, draw leader line + label box
        for p in visible {
            guard var lx = p.labelX, var ly = p.labelY else { continue }
            lx = max(2, min(canvasSize.width - p.labelW - 2, lx))
            ly = max(2, min(canvasSize.height - p.labelH - 2, ly))
            p.labelX = lx
            p.labelY = ly

            let attachX = p.labelSide == .right ? lx : lx + p.labelW
            let attachY = max(ly, min(p.anchorY, ly + p.labelH))

            var leader = Path()
            leader.move(to: CGPoint(x: p.anchorX, y: p.anchorY))
            leader.addLine(to: CGPoint(x: attachX, y: attachY))
            context.stroke(leader, with: .color(p.color.opacity(0.55)), lineWidth: 1)

            drawLabel(&context, p: p, at: CGPoint(x: lx, y: ly))
        }
    }

    private func drawBlip(_ context: inout GraphicsContext, p: PlaneState) {
        if p.hex == viewModel.selectedHex {
            let r = 16 * uiScale
            let ring = Path(ellipseIn: CGRect(x: p.anchorX - r, y: p.anchorY - r, width: r * 2, height: r * 2))
            context.stroke(ring, with: .color(pal.text.opacity(0.85)), lineWidth: 1.5)
        }
        var tri = Path()
        tri.move(to: CGPoint(x: 0, y: -9))
        tri.addLine(to: CGPoint(x: 6, y: 7))
        tri.addLine(to: CGPoint(x: 0, y: 3))
        tri.addLine(to: CGPoint(x: -6, y: 7))
        tri.closeSubpath()

        context.drawLayer { ctx in
            ctx.translateBy(x: p.anchorX, y: p.anchorY)
            ctx.rotate(by: .radians(p.hdg * .pi / 180))
            ctx.scaleBy(x: uiScale, y: uiScale)
            if p.isNetwork {
                // Reported by a public network, not heard by this radar: hollow
                // and dimmed, as on the kiosk, so a glance always tells "my
                // radar heard this" from "the network says it's there".
                ctx.stroke(tri, with: .color(p.color.opacity(0.55)), lineWidth: 1.2)
            } else {
                ctx.addFilter(.shadow(color: p.color, radius: 6))
                ctx.fill(tri, with: .color(p.color))
            }
        }
    }

    // MARK: - Label content & layout

    private struct LabelContent {
        let callsign: String
        let callsignColor: Color
        let badgeText: String
        let badgeColor: Color
        let typeLine: String?
        let altLine: String
        let routeLine: String?
    }

    private func labelContent(for p: PlaneState) -> LabelContent {
        let speedTxt = p.speed.map { "\(Int($0.rounded()))" } ?? "--"
        let altLine = "\(PlaneState.altLabel(p.alt)) · \(speedTxt)kt"
        var routeLine: String?
        if let r = p.feedRoute {
            routeLine = r.plausible == false ? "\(r.text) (unconfirmed)" : r.text
        } else if let route = viewModel.routeClient.cache[p.cs], let r = route {
            routeLine = "\(r.from) → \(r.to)"
        }
        if viewModel.labelMode != .full && p.hex != viewModel.selectedHex {
            return LabelContent(callsign: p.cs, callsignColor: p.color, badgeText: "", badgeColor: p.badgeColor,
                                typeLine: nil, altLine: PlaneState.altLabel(p.alt), routeLine: nil)
        }
        return LabelContent(
            callsign: p.cs, callsignColor: p.color,
            badgeText: p.airlineLabel, badgeColor: p.badgeColor,
            typeLine: p.typeLabel, altLine: altLine, routeLine: routeLine
        )
    }

    private var fontCallsign: Font { .system(size: 11 * uiScale, weight: .bold, design: .monospaced) }
    private var fontBadge: Font { .system(size: 8 * uiScale, weight: .bold, design: .monospaced) }
    private var fontLine: Font { .system(size: 9 * uiScale, design: .monospaced) }

    private struct LabelMetrics {
        let size: CGSize
        let lineHeights: [CGFloat]
    }

    private func measure(_ c: LabelContent, context: GraphicsContext) -> LabelMetrics {
        let pad: CGFloat = 6
        var lines: [(String, Font)] = [(c.callsign, fontCallsign)]
        if !c.badgeText.isEmpty { lines.append((c.badgeText, fontBadge)) }
        if let t = c.typeLine { lines.append((t, fontLine)) }
        lines.append((c.altLine, fontLine))
        if let rt = c.routeLine { lines.append((rt, fontLine)) }

        var maxW: CGFloat = 0
        var heights: [CGFloat] = []
        for (text, font) in lines {
            let resolved = context.resolve(Text(text).font(font))
            let sz = resolved.measure(in: CGSize(width: 400, height: 100))
            maxW = max(maxW, sz.width)
            heights.append(sz.height)
        }
        let gap: CGFloat = 2
        let totalH = heights.reduce(0, +) + gap * CGFloat(heights.count - 1)
        return LabelMetrics(size: CGSize(width: maxW + pad * 2, height: totalH + pad * 2), lineHeights: heights)
    }

    private func drawLabel(_ context: inout GraphicsContext, p: PlaneState, at origin: CGPoint) {
        let content = labelContent(for: p)
        let metrics = measure(content, context: context)
        let rect = CGRect(origin: origin, size: metrics.size)

        var bg = Path(roundedRect: rect, cornerRadius: 3)
        context.fill(bg, with: .color(pal.panel))
        context.stroke(bg, with: .color(pal.text.opacity(0.08)), lineWidth: 1)

        var edge = Path()
        edge.move(to: CGPoint(x: rect.minX, y: rect.minY))
        edge.addLine(to: CGPoint(x: rect.minX, y: rect.maxY))
        context.stroke(edge, with: .color(p.color), lineWidth: 2)

        let pad: CGFloat = 6
        var y = rect.minY + pad
        let x = rect.minX + pad

        let csText = context.resolve(Text(content.callsign).font(fontCallsign).foregroundColor(content.callsignColor))
        let csSize = metrics.lineHeights[0]
        context.draw(csText, at: CGPoint(x: x, y: y), anchor: .topLeading)
        y += csSize + 2

        var lineIdx = 1
        if !content.badgeText.isEmpty {
            // badge pill
            let badgeResolved = context.resolve(Text(content.badgeText).font(fontBadge).foregroundColor(.white))
            let badgeTextSize = badgeResolved.measure(in: CGSize(width: 400, height: 100))
            let badgeRect = CGRect(x: x, y: y, width: badgeTextSize.width + 8, height: metrics.lineHeights[1] + 3)
            context.fill(Path(roundedRect: badgeRect, cornerRadius: 2), with: .color(content.badgeColor))
            context.draw(badgeResolved, at: CGPoint(x: badgeRect.minX + 4, y: badgeRect.minY + 1.5), anchor: .topLeading)
            y += badgeRect.height + 2
            lineIdx = 2
        }
        if let t = content.typeLine {
            let text = context.resolve(Text(t).font(fontLine).foregroundColor(colorTextDim))
            context.draw(text, at: CGPoint(x: x, y: y), anchor: .topLeading)
            y += metrics.lineHeights[lineIdx] + 2
            lineIdx += 1
        }

        let altText = context.resolve(Text(content.altLine).font(fontLine).foregroundColor(colorTextDim))
        context.draw(altText, at: CGPoint(x: x, y: y), anchor: .topLeading)
        y += metrics.lineHeights[lineIdx] + 2
        lineIdx += 1

        if let rt = content.routeLine {
            let text = context.resolve(Text(rt).font(fontLine).foregroundColor(colorTextDim))
            context.draw(text, at: CGPoint(x: x, y: y), anchor: .topLeading)
        }
    }

    /// Stable per-pair tie-break direction when two labels want the exact
    /// same spot (e.g. two aircraft momentarily at ~identical bearing/range).
    private func stableHash(_ s: String) -> Int {
        var h = 0
        for ch in s.unicodeScalars { h = (h &* 31 &+ Int(ch.value)) & 0x7fffffff }
        return h
    }
}
