import SwiftUI
import UIKit

/// An invisible view whose UIView is handed over once it is on screen, so
/// motion and heading can be measured relative to it (#101).
///
/// On iOS 27 CoreMotion (`CMMotionManager.deviceMotionBody`) and CoreLocation
/// (`CLLocationManager.headingBody`) take a view as the "body" to measure
/// from: readings then arrive turned to that view's screen, whichever
/// display it is on and whichever way that display is turned. That matters
/// on the iPhone Duo, whose inner display ignores the app's portrait-only
/// setting, so held sideways "up the screen" is no longer "up the phone".
/// Before iOS 27, and whenever the app is not full screen, readings come in
/// the phone's own axes as before.
struct BodyAnchor: UIViewRepresentable {
    let attach: (UIView) -> Void

    final class AnchorView: UIView {
        var onWindow: ((UIView) -> Void)?
        override func didMoveToWindow() {
            super.didMoveToWindow()
            if window != nil { onWindow?(self) }
        }
    }

    func makeUIView(context: Context) -> AnchorView {
        let v = AnchorView()
        v.isUserInteractionEnabled = false
        v.backgroundColor = .clear
        v.onWindow = attach
        return v
    }

    func updateUIView(_ uiView: AnchorView, context: Context) {
        uiView.onWindow = attach
    }
}
