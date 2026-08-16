import SwiftUI

struct ContentView: View {
    @StateObject private var viewModel = RadarViewModel()
    @State private var showSettings = false

    var body: some View {
        GeometryReader { geo in
            let side = min(geo.size.width, geo.size.height) * 0.94

            ZStack {
                Color.black.ignoresSafeArea()

                ZStack {
                    if let home = viewModel.home {
                        MapBackgroundView(
                            center: home,
                            zoom: Geo.zoomForRange(rangeNm: viewModel.rangeNm, lat: home.lat, pixels: side * 0.44),
                            runwayGeoJSON: viewModel.runwayGeoJSON
                        )
                        .clipShape(Circle())
                    }
                    RadarView(viewModel: viewModel)
                        .frame(width: side, height: side)
                        .clipShape(Circle())
                        .overlay(Circle().stroke(Color(hex: "#14201f"), lineWidth: 2))
                        .shadow(color: .black.opacity(0.6), radius: 20)
                }
                .frame(width: side, height: side)
                .position(x: geo.size.width / 2, y: geo.size.height / 2)

                VStack {
                    hud
                    Spacer()
                    if viewModel.isStale {
                        Text("NO SIGNAL — CHECK RECEIVER")
                            .font(.system(size: 10, weight: .medium, design: .monospaced))
                            .tracking(2)
                            .foregroundColor(Color(hex: "#ff5d5d"))
                            .padding(.bottom, geo.size.height * 0.08)
                    }
                }
                .padding(.top, geo.safeAreaInsets.top + 8)

                VStack {
                    HStack {
                        Spacer()
                        Button {
                            showSettings = true
                        } label: {
                            Image(systemName: "gearshape")
                                .foregroundColor(Color(hex: "#5b7278"))
                                .padding(10)
                        }
                    }
                    Spacer()
                }
            }
        }
        .background(Color.black)
        .statusBarHidden(true)
        .onAppear { viewModel.start() }
        .onDisappear { viewModel.stop() }
        .sheet(isPresented: $showSettings) {
            SettingsView()
        }
    }

    private var hud: some View {
        VStack(spacing: 2) {
            Text(locationText)
                .font(.system(size: 10, design: .monospaced))
                .tracking(1.5)
                .foregroundColor(Color(hex: "#5b7278"))
                .textCase(.uppercase)
            Text("\(viewModel.aircraftCount) AIRCRAFT")
                .font(.system(size: 15, design: .monospaced))
                .tracking(1)
                .foregroundColor(Color(hex: "#cfe8ea"))
        }
    }

    private var locationText: String {
        guard let home = viewModel.home else { return "LOCATING…" }
        let ns = home.lat >= 0 ? "N" : "S"
        let ew = home.lon >= 0 ? "E" : "W"
        return String(format: "%.4f°%@ %.4f°%@ · %.0fNM", abs(home.lat), ns, abs(home.lon), ew, viewModel.rangeNm)
    }
}

#Preview {
    ContentView()
}
