import SwiftUI

/// The StratoScan mark ("Climb"), drawn with shapes so it is sharp at any
/// size, on the phone and the Watch. The same geometry as
/// assets/brand/make.py, in the same 100x100 box: a scope ring, the sweep,
/// and three blips climbing toward it, green, cyan and white with height.
/// Below about 32 pt the small version: two larger blips and a heavier ring.
struct StratoScanMark: View {
    var small = false

    static let sky = Color(red: 0x0a / 255, green: 0x1a / 255, blue: 0x3a / 255)
    private static let ring = Color(red: 0x27 / 255, green: 0x4a / 255, blue: 0x86 / 255)
    private static let sweep = Color(red: 0x5e / 255, green: 0xe7 / 255, blue: 0xff / 255)
    private static let low = Color(red: 0x3d / 255, green: 0xdc / 255, blue: 0x97 / 255)

    var body: some View {
        Canvas { ctx, size in
            let s = min(size.width, size.height) / 100
            ctx.translateBy(x: (size.width - 100 * s) / 2, y: (size.height - 100 * s) / 2)
            ctx.scaleBy(x: s, y: s)
            let r: CGFloat = small ? 38 : 36
            let tip = CGPoint(x: 50 + r * cos(-.pi / 6), y: 50 + r * sin(-.pi / 6))
            ctx.stroke(Path(ellipseIn: CGRect(x: 50 - r, y: 50 - r, width: 2 * r, height: 2 * r)),
                       with: .color(Self.ring), lineWidth: small ? 7 : 4)
            var wedge = Path()
            wedge.move(to: CGPoint(x: 50, y: 50))
            wedge.addArc(center: CGPoint(x: 50, y: 50), radius: r,
                         startAngle: .degrees(-90), endAngle: .degrees(-30), clockwise: false)
            wedge.closeSubpath()
            ctx.fill(wedge, with: .color(Self.sweep.opacity(small ? 0.35 : 0.32)))
            var line = Path()
            line.move(to: CGPoint(x: 50, y: 50))
            line.addLine(to: tip)
            ctx.stroke(line, with: .color(Self.sweep), style: StrokeStyle(lineWidth: small ? 8 : 4.5, lineCap: .round))
            func dot(_ x: CGFloat, _ y: CGFloat, _ radius: CGFloat, _ c: Color) {
                ctx.fill(Path(ellipseIn: CGRect(x: x - radius, y: y - radius, width: 2 * radius, height: 2 * radius)), with: .color(c))
            }
            if small {
                dot(30, 64, 7, Self.low)
                dot(45, 36, 8.5, .white)
            } else {
                dot(50, 50, 3.4, Self.sweep)
                dot(27, 67, 3.4, Self.low)
                dot(35, 53, 4.2, Self.sweep)
                dot(46, 36, 5, .white)
            }
        }
        .aspectRatio(1, contentMode: .fit)
        .accessibilityHidden(true)
    }
}

/// The mark on its sky tile, with the wordmark beside it ("Wordmark" and
/// "WordmarkLight", from assets/brand/wordmark-on-dark.svg and -on-light.svg).
struct StratoScanLogo: View {
    var height: CGFloat = 24
    /// Dark letters for a light background (the app's Daylight theme). Left
    /// out, it follows the screen's light or dark appearance.
    var onLight: Bool? = nil
    @Environment(\.colorScheme) private var scheme

    var body: some View {
        HStack(spacing: height * 0.16) {
            StratoScanMark(small: height <= 32)
                .padding(height * 0.1)
                .frame(width: height, height: height)
                .background(StratoScanMark.sky, in: RoundedRectangle(cornerRadius: height * 0.22, style: .continuous))
            Image((onLight ?? (scheme == .light)) ? "WordmarkLight" : "Wordmark")
                .resizable()
                .scaledToFit()
                .frame(height: height * 0.42)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("StratoScan")
    }
}
