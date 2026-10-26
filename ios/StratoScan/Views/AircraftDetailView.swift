import SwiftUI

/// Details for one aircraft, opened by tapping it on the radar. Refreshes
/// every second from the live plane state, like the kiosk's detail panel.
struct AircraftDetailView: View {
    @ObservedObject private var logos = AirlineLogoStore.shared
    @ObservedObject var viewModel: RadarViewModel
    @ObservedObject var location: PhoneLocation
    let hex: String
    /// "Find in the sky": opens Sky view on this aircraft (from the radar only).
    var findInSky: (() -> Void)? = nil
    @State private var photo: Photo?
    @State private var photoImage: UIImage?
    @State private var showCompass = false
    @Environment(\.dismiss) private var dismiss

    struct Photo: Decodable {
        let found: Bool
        let thumb: String?
        let thumbLarge: String?
        let photographer: String?
        let link: String?
    }

    var body: some View {
        TimelineView(.periodic(from: .now, by: 1)) { _ in
            let p = viewModel.plane(hex)
            ScrollView {
                // The kiosk's detail panel, field for field and in its order
                // (#77, docs/aircraft-fields.md): photo, callsign, operator,
                // type · registration, owner, route, then the figures. The
                // buttons are the phone's own.
                VStack(alignment: .leading, spacing: 16) {
                    photoView
                    header(p)
                    actions(p)
                    if let p {
                        grid(p)
                    } else {
                        Text("Out of range now.").foregroundColor(.secondary)
                    }
                    footer(p)
                }
                .padding(20)
            }
        }
        .task(id: hex) { await loadPhoto() }
        .task { await NotablePeople.shared.load() }
        .sheet(isPresented: $showCompass) {
            CompassView(viewModel: viewModel, location: location, hex: hex)
                .preferredColorScheme(.dark)
        }
    }

    @ViewBuilder private func actions(_ p: PlaneState?) -> some View {
        HStack(spacing: 8) {
            if viewModel.planes[hex] != nil {   // not one only seen around the phone
                // Keep this aircraft in the middle of the radar and map,
                // zoomed in, to see exactly where it is (roadmap 2.9).
                Button(viewModel.followHex == hex ? "Stop following" : "Follow") {
                    if viewModel.followHex == hex {
                        viewModel.followHex = nil
                    } else {
                        viewModel.followHex = hex
                        if viewModel.rangeNm > 5 { viewModel.setRange(5) }
                        dismiss()
                    }
                }
                .buttonStyle(.bordered)
            }
            if p != nil {
                // Point the phone at it (roadmap 3.4).
                Button("Compass") { showCompass = true }
                    .buttonStyle(.bordered)
                if let findInSky {
                    Button { findInSky() } label: { Label("Find in the sky", systemImage: "binoculars") }
                        .buttonStyle(.bordered)
                }
            }
        }
    }

    private func header(_ p: PlaneState?) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(p?.cs ?? hex.uppercased())
                .font(.system(size: 28, weight: .semibold, design: .monospaced))
                .foregroundColor(p?.color ?? .primary)
            if let p {
                // The operator as a badge, as on the tag and the kiosk.
                HStack(spacing: 5) {
                    if let mark = logos.mark(for: p.airlineIcao) {
                        Image(uiImage: mark).resizable().scaledToFit().frame(width: 16, height: 16)
                            .background(Color.white, in: RoundedRectangle(cornerRadius: 3))
                    }
                    Text(p.airlineLabel).font(.system(.caption, design: .monospaced).weight(.bold)).foregroundColor(.white)
                }
                .padding(.horizontal, 6).padding(.vertical, 3)
                .background(p.badgeColor, in: RoundedRectangle(cornerRadius: 3))
                Text([p.typeLabel ?? "Unknown type", p.reg].compactMap { $0 }.joined(separator: " · "))
                    .foregroundColor(.secondary)
                if let o = p.owner {
                    Text("Registered to \(o.name)\(o.country.map { " (\($0))" } ?? "")")
                        .font(.caption).foregroundColor(.secondary)
                }
                if let r = viewModel.routeClient.route(for: p) {
                    Text(r.text).font(.callout).foregroundColor(r.plausible ? .primary : Palette.current.bad)
                }
                if p.isNetwork {
                    // Said plainly: this came from the network, not the antenna.
                    // adsb.lol's data is ODbL, which asks for this credit.
                    Text(viewModel.planes[hex] == nil
                         ? "Near you, reported by adsb.lol. Network data © ADSB.lol contributors (ODbL)."
                         : "Reported by adsb.lol, not heard by this radar. Network data © ADSB.lol contributors (ODbL).")
                        .font(.caption).foregroundColor(.orange)
                }
            }
        }
    }

    @ViewBuilder private var photoView: some View {
        if let photo, photo.found {
            VStack(alignment: .leading, spacing: 4) {
                Group {
                    if let photoImage {
                        Image(uiImage: photoImage).resizable().scaledToFit()
                    } else {
                        Color.gray.opacity(0.15).frame(height: 180)
                    }
                }
                .clipShape(RoundedRectangle(cornerRadius: 8))
                // planespotters.net requires the credit and a link back.
                if let link = photo.link.flatMap(URL.init(string:)) {
                    Link("© \(photo.photographer ?? "Unknown") · planespotters.net", destination: link)
                        .font(.caption)
                } else {
                    Text("© \(photo.photographer ?? "Unknown") · planespotters.net").font(.caption)
                }
            }
        } else if photo != nil {
            // None to be had: the kiosk's stand-in for a viewer that isn't the
            // kiosk itself (its stock photo by type is the unit's own lookup).
            ZStack {
                RoundedRectangle(cornerRadius: 8).fill(Color(white: 0.07))
                ForEach([90.0, 55.0, 20.0], id: \.self) { r in
                    Circle().stroke(Palette.current.ring, lineWidth: 1).frame(width: r * 2 * 0.8, height: r * 2 * 0.8)
                }
                Image(systemName: "airplane").font(.system(size: 40)).foregroundColor(Palette.current.textDim)
                VStack { Spacer(); Text("No photo available").font(.caption).foregroundColor(.secondary).padding(6) }
            }
            .frame(height: 180)
        }
    }

    /// The kiosk's figures, in its order and with its labels and formats.
    private func grid(_ p: PlaneState) -> some View {
        var rows: [(String, String)] = [
            ("Altitude", PlaneState.altLabel(p.alt)),
            ("Speed", p.speed.map { "\(Int($0.rounded())) kt" } ?? "—"),
            ("Heading", p.realHdg.map { "\(Int($0.rounded()) % 360)°" } ?? "—"),
            ("Vert. rate", Self.vrateLabel(p.vrate)),
            ("Squawk", p.squawk ?? "—"),
            ("Distance", String(format: "%.1f nm · %d°", p.targetRange, Int(p.targetBearing.rounded()) % 360)),
        ]
        if let b = p.band {
            rows.append(("Heard on", b == "1090" ? "1090 MHz" : b == "978" ? "978 MHz (UAT)" : "978 MHz, re-sent on 1090"))
        }
        if let r = p.rare {
            // A well-known person's name only at home, from the radar's own
            // list (never on its public address), as on the kiosk.
            let who = r.operatorName ?? (r.kind == "notable" ? NotablePeople.shared.name(for: p.hex) : nil)
            rows.append(("Notable", who.map { "\(r.label) · \($0)" } ?? r.label))
        }
        if let s = p.sightings {
            rows.append(("Sightings", "\(s.total)"))
            rows.append(("Within 2 mi", "\(s.nearby)"))
        }
        return VStack(spacing: 10) {
            ForEach(rows, id: \.0) { row in
                HStack {
                    Text(row.0).foregroundColor(.secondary)
                    Spacer()
                    Text(row.1).font(.system(.body, design: .monospaced)).multilineTextAlignment(.trailing)
                }
            }
        }
    }

    @ViewBuilder private func footer(_ p: PlaneState?) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("ICAO \(hex.uppercased())")
                .font(.system(.caption, design: .monospaced)).foregroundColor(.secondary)
            if p?.rare?.kind == "notable" {
                Text("Notable list: plane-alert-db (ODbL)").font(.caption2).foregroundColor(.secondary)
            }
        }
    }

    /// The kiosk's vrateLabel (index.html).
    static func vrateLabel(_ v: Double?) -> String {
        guard let v else { return "—" }
        if abs(v) < 100 { return "Level" }
        return (v > 0 ? "↑ " : "↓ ") + "\(Int(abs(v.rounded()))) ft/min"
    }

    /// planespotters.net's photo API, asked by the phone itself with the
    /// descriptive User-Agent their terms require of a device (2026-10-09),
    /// never through the radar: their terms forbid re-exposing their data
    /// through another API. The image then loads from their CDN unchanged,
    /// and the credit links to the photo's page. One answer per aircraft is
    /// kept for a day, their stated maximum.
    private static var cache: [String: (at: Date, photo: Photo)] = [:]
    private func loadPhoto() async {
        photoImage = nil
        if let hit = Self.cache[hex], Date().timeIntervalSince(hit.at) < 24 * 3600 {
            photo = hit.photo
        } else {
            guard let url = URL(string: "https://api.planespotters.net/pub/photos/hex/\(hex)") else { return }
            var req = URLRequest(url: url, timeoutInterval: 8)
            req.setValue("StratoScan/1.0 (iOS app; +https://github.com/mferris/StratoScan)", forHTTPHeaderField: "User-Agent")
            guard let (data, resp) = try? await URLSession.bounded.data(for: req),
                  (resp as? HTTPURLResponse)?.statusCode == 200,
                  let answer = try? JSONDecoder().decode(Answer.self, from: data) else { return }
            let p = answer.photos?.first
            let got = Photo(found: p != nil, thumb: p?.thumbnail?.src, thumbLarge: p?.thumbnail_large?.src,
                            photographer: p?.photographer, link: p?.link)
            Self.cache[hex] = (Date(), got)
            photo = got
        }
        // The picture itself, with a time limit (#86, 2026-10-26): AsyncImage
        // has none of its own, and the grey box could wait a minute on the
        // CDN. One that doesn't come is the "No photo available" box.
        guard let p = photo, p.found else { return }
        if let s = p.thumbLarge ?? p.thumb, let url = URL(string: s),
           let (data, resp) = try? await URLSession.bounded.data(for: URLRequest(url: url, timeoutInterval: 10)),
           (resp as? HTTPURLResponse)?.statusCode == 200, let img = UIImage(data: data) {
            photoImage = img
        } else if !Task.isCancelled {
            photo = Photo(found: false, thumb: nil, thumbLarge: nil, photographer: nil, link: nil)
        }
    }
    private struct Answer: Decodable {
        struct Src: Decodable { let src: String? }
        struct Item: Decodable { let thumbnail: Src?; let thumbnail_large: Src?; let link: String?; let photographer: String? }
        let photos: [Item]?
    }
}

/// Well-known people's names for their aircraft, from the radar's own list
/// (/data/notable-people.json), which only its home address serves: the
/// public address refuses it, so away from home there are none, exactly as on
/// the kiosk's public page (#77). Asked once, and again ten minutes after a
/// miss.
@MainActor
final class NotablePeople {
    static let shared = NotablePeople()
    private var names: [String: String] = [:]
    private var askedAt: Date?

    func name(for hex: String) -> String? { names[hex.lowercased()] }

    func load() async {
        if !names.isEmpty { return }
        if let t = askedAt, Date().timeIntervalSince(t) < 600 { return }
        askedAt = Date()
        struct Doc: Decodable { let names: [String: String]? }
        let base = await Endpoint.shared.resolve()
        guard let url = URL(string: base.trimmingCharacters(in: CharacterSet(charactersIn: "/")) + "/data/notable-people.json"),
              let (data, resp) = try? await URLSession.radar.data(for: URLRequest(url: url, timeoutInterval: 6)),
              (resp as? HTTPURLResponse)?.statusCode == 200,
              let doc = try? JSONDecoder().decode(Doc.self, from: data) else { return }
        names = (doc.names ?? [:]).reduce(into: [:]) { $0[$1.key.lowercased()] = $1.value }
    }
}
