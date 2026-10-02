import SwiftUI
import VisionKit

/// Scans a radar's pairing QR code with the camera. VisionKit's scanner needs
/// iOS 16 and an A12 or newer; where it isn't available (the simulator, older
/// phones) the iPhone Camera app does the same job via the stratoscan:// link.
struct PairingScannerView: UIViewControllerRepresentable {
    let onFound: (URL) -> Void

    static var isAvailable: Bool {
        DataScannerViewController.isSupported && DataScannerViewController.isAvailable
    }

    func makeUIViewController(context: Context) -> DataScannerViewController {
        let vc = DataScannerViewController(recognizedDataTypes: [.barcode(symbologies: [.qr])],
                                           qualityLevel: .balanced,
                                           isHighlightingEnabled: true)
        vc.delegate = context.coordinator
        return vc
    }

    // Started here, not in make: until the view is in a window the camera
    // doesn't start, and the attempt fails silently.
    func updateUIViewController(_ vc: DataScannerViewController, context: Context) {
        if !vc.isScanning && !context.coordinator.done { try? vc.startScanning() }
    }

    func makeCoordinator() -> Coordinator { Coordinator(onFound: onFound) }

    final class Coordinator: NSObject, DataScannerViewControllerDelegate {
        let onFound: (URL) -> Void
        fileprivate(set) var done = false
        init(onFound: @escaping (URL) -> Void) { self.onFound = onFound }

        func dataScanner(_ scanner: DataScannerViewController, didAdd items: [RecognizedItem],
                         allItems: [RecognizedItem]) {
            guard !done else { return }
            for case .barcode(let code) in items {
                if let s = code.payloadStringValue, let url = URL(string: s),
                   PairingStore.parse(url) != nil || RadarSetup.parse(url) != nil {
                    done = true
                    scanner.stopScanning()
                    onFound(url)
                    return
                }
            }
        }
    }
}
