import SwiftUI

/// The whole radar — rings, sweep, aircraft blips, and collision-avoiding
/// labels with leader lines — drawn as one Canvas every frame. Unlike the
/// web version (Canvas for blips/rings, separate DOM divs for labels,
/// because HTML canvas can't measure DOM text), SwiftUI's GraphicsContext
/// can both measure and draw text, so everything lives in a single Canvas
/// here — simpler than the two-layer split the browser needed.
struct RadarView: View {
    @ObservedObject var viewModel: RadarViewModel

    private let rangeRings = 4
    private let sweepSpeed: Double = 0.008 * 60 // radians/sec (web version: 0.008/frame @ ~60fps)
    private let smoothTau = 0.35
    private let labelGap: CGFloat = 10
    private let labelMargin: CGFloat = 4
    private let labelSpringTau = 0.22
    private let labelSeparationPasses = 4

    private let colorRing = Color(hex: "#1c3236")
    private let colorRingBright = Color(hex: "#2a4a4f")
    private let colorSweep = Color(hex: "#ffb020")
    private let colorTextDim = Color(hex: "#5b7278")
    private let colorLow = Color(hex: "#ffb020")

    var body: some View {
        TimelineView(.animation) { timeline in
            Canvas { context, canvasSize in
                render(context: &context, canvasSize: canvasSize, now: timeline.date)
            }
        }
        .drawingGroup()
    }

    private func render(context: inout GraphicsContext, canvasSize: CGSize, now: Date) {
        let cx = canvasSize.width / 2
        let cy = canvasSize.height / 2
        let r = min(canvasSize.width, canvasSize.height) * 0.44

        let dt: Double
        if let last = viewModel.lastFrameTime {
            dt = min(0.25, max(0, now.timeIntervalSince(last)))
        } else {
            dt = 0
        }
        viewModel.lastFrameTime = now

        drawRings(&context, cx: cx, cy: cy, r: r)
        drawSweep(&context, cx: cx, cy: cy, r: r, dt: dt)
        drawPlanes(&context, cx: cx, cy: cy, r: r, canvasSize: canvasSize, dt: dt)

        viewModel.sweepAngle += sweepSpeed * dt
        if viewModel.sweepAngle > .pi * 2 { viewModel.sweepAngle -= .pi * 2 }
    }

    // MARK: - Rings

    private func drawRings(_ context: inout GraphicsContext, cx: CGFloat, cy: CGFloat, r: CGFloat) {
        for i in 1...rangeRings {
            let ringR = (r / CGFloat(rangeRings)) * CGFloat(i)
            var path = Path()
            path.addEllipse(in: CGRect(x: cx - ringR, y: cy - ringR, width: ringR * 2, height: ringR * 2))
            context.stroke(path, with: .color(i == rangeRings ? colorRingBright : colorRing), lineWidth: 1)

            let nm = Int((viewModel.rangeNm / Double(rangeRings) * Double(i)).rounded())
            let label = Text("\(nm)nm").font(.system(size: 10, design: .monospaced)).foregroundColor(Color(hex: "#3d5a5f"))
            context.draw(label, at: CGPoint(x: cx + 6, y: cy - ringR + 8), anchor: .topLeading)
        }

        var cross = Path()
        cross.move(to: CGPoint(x: cx, y: cy - r)); cross.addLine(to: CGPoint(x: cx, y: cy + r))
        cross.move(to: CGPoint(x: cx - r, y: cy)); cross.addLine(to: CGPoint(x: cx + r, y: cy))
        context.stroke(cross, with: .color(Color(hex: "#16282b")), lineWidth: 1)

        let compassColor = Color(hex: "#4a6b70")
        let compassFont = Font.system(size: 13, weight: .semibold)
        context.draw(Text("N").font(compassFont).foregroundColor(compassColor), at: CGPoint(x: cx, y: cy - r + 16), anchor: .center)
        context.draw(Text("S").font(compassFont).foregroundColor(compassColor), at: CGPoint(x: cx, y: cy + r - 10), anchor: .center)
        context.draw(Text("E").font(compassFont).foregroundColor(compassColor), at: CGPoint(x: cx + r - 12, y: cy + 5), anchor: .center)
        context.draw(Text("W").font(compassFont).foregroundColor(compassColor), at: CGPoint(x: cx - r + 12, y: cy + 5), anchor: .center)

        var dot = Path()
        dot.addEllipse(in: CGRect(x: cx - 3, y: cy - 3, width: 6, height: 6))
        context.fill(dot, with: .color(colorSweep))
    }

    // MARK: - Sweep

    private func drawSweep(_ context: inout GraphicsContext, cx: CGFloat, cy: CGFloat, r: CGFloat, dt: Double) {
        let angle = viewModel.sweepAngle
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
        let inRange = viewModel.planes.values.filter { $0.range <= viewModel.rangeNm || $0.targetRange <= viewModel.rangeNm }

        // pass 1: motion + blips
        for p in inRange {
            p.bearing += Geo.bearingDelta(from: p.bearing, to: p.targetBearing) * alpha
            p.range += (p.targetRange - p.range) * alpha
            p.color = PlaneState.altColor(p.alt)

            let angle = (p.bearing - 90) * .pi / 180
            let radius = CGFloat(p.range / viewModel.rangeNm) * r
            p.anchorX = cx + radius * CGFloat(cos(angle))
            p.anchorY = cy + radius * CGFloat(sin(angle))

            drawBlip(&context, p: p)
        }

        let visible = inRange.filter { $0.range <= viewModel.rangeNm }

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
        var tri = Path()
        tri.move(to: CGPoint(x: 0, y: -9))
        tri.addLine(to: CGPoint(x: 6, y: 7))
        tri.addLine(to: CGPoint(x: 0, y: 3))
        tri.addLine(to: CGPoint(x: -6, y: 7))
        tri.closeSubpath()

        context.drawLayer { ctx in
            ctx.translateBy(x: p.anchorX, y: p.anchorY)
            ctx.rotate(by: .radians(p.hdg * .pi / 180))
            ctx.addFilter(.shadow(color: p.color, radius: 6))
            ctx.fill(tri, with: .color(p.color))
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
        if let route = viewModel.routeClient.cache[p.cs], let r = route {
            routeLine = "\(r.from) → \(r.to)"
        }
        return LabelContent(
            callsign: p.cs, callsignColor: p.color,
            badgeText: p.airlineLabel, badgeColor: p.badgeColor,
            typeLine: p.typeLabel, altLine: altLine, routeLine: routeLine
        )
    }

    private let fontCallsign = Font.system(size: 13, weight: .bold, design: .monospaced)
    private let fontBadge = Font.system(size: 10, weight: .bold, design: .monospaced)
    private let fontLine = Font.system(size: 11, design: .monospaced)

    private struct LabelMetrics {
        let size: CGSize
        let lineHeights: [CGFloat]
    }

    private func measure(_ c: LabelContent, context: GraphicsContext) -> LabelMetrics {
        let pad: CGFloat = 6
        var lines: [(String, Font)] = [(c.callsign, fontCallsign), (c.badgeText, fontBadge)]
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
        context.fill(bg, with: .color(Color(hex: "#05080a").opacity(0.75)))
        context.stroke(bg, with: .color(.white.opacity(0.06)), lineWidth: 1)

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

        // badge pill
        let badgeResolved = context.resolve(Text(content.badgeText).font(fontBadge).foregroundColor(.white))
        let badgeTextSize = badgeResolved.measure(in: CGSize(width: 400, height: 100))
        let badgeRect = CGRect(x: x, y: y, width: badgeTextSize.width + 8, height: metrics.lineHeights[1] + 3)
        context.fill(Path(roundedRect: badgeRect, cornerRadius: 2), with: .color(content.badgeColor))
        context.draw(badgeResolved, at: CGPoint(x: badgeRect.minX + 4, y: badgeRect.minY + 1.5), anchor: .topLeading)
        y += badgeRect.height + 2

        var lineIdx = 2
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
