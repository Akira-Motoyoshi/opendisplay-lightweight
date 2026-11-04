import AppKit
import QuartzCore

final class ComparisonScene: NSView {
    override init(frame: NSRect) {
        super.init(frame: frame)
        wantsLayer = true
        layer?.backgroundColor = NSColor(calibratedRed: 0.08, green: 0.12, blue: 0.19, alpha: 1).cgColor
        let bar = CALayer()
        bar.backgroundColor = NSColor(calibratedRed: 0.2, green: 0.8, blue: 0.9, alpha: 1).cgColor
        bar.bounds = CGRect(x: 0, y: 0, width: 100, height: 22)
        bar.position = CGPoint(x: 80, y: frame.height / 2)
        layer?.addSublayer(bar)
        let motion = CABasicAnimation(keyPath: "position.x")
        motion.fromValue = 80
        motion.toValue = max(100, frame.width - 80)
        motion.duration = 2
        motion.autoreverses = true
        motion.repeatCount = .infinity
        motion.timingFunction = CAMediaTimingFunction(name: .linear)
        bar.add(motion, forKey: "fixedComparisonMotion")
        let label = NSTextField(labelWithString: "OpenDisplay A/B comparison\nSame resolution / same moving scene\nPlease leave the pointer still")
        label.textColor = .white
        label.font = .monospacedSystemFont(ofSize: 16, weight: .regular)
        label.frame = NSRect(x: 30, y: frame.height - 140, width: max(200, frame.width - 60), height: 100)
        addSubview(label)
    }
    required init?(coder: NSCoder) { fatalError("not used") }
}

final class SceneDelegate: NSObject, NSApplicationDelegate {
    let targetDisplay: UInt32
    var window: NSWindow?
    var screenID: UInt32?
    var timer: Timer?
    init(targetDisplay: UInt32) { self.targetDisplay = targetDisplay }
    func applicationDidFinishLaunching(_ notification: Notification) {
        updateScreen()
        timer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in self?.updateScreen() }
    }
    func updateScreen() {
        guard let screen = NSScreen.screens.first(where: {
            ($0.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? NSNumber)?.uint32Value == targetDisplay
        }) else {
            window?.orderOut(nil)
            screenID = nil
            return
        }
        guard screenID != targetDisplay || window?.frame != screen.frame else { return }
        if window == nil {
            window = NSWindow(contentRect: screen.frame, styleMask: .borderless, backing: .buffered, defer: false)
            window?.isReleasedWhenClosed = false
            window?.ignoresMouseEvents = true
            window?.level = .floating
            window?.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        }
        window?.setFrame(screen.frame, display: true)
        window?.contentView = ComparisonScene(frame: NSRect(origin: .zero, size: screen.frame.size))
        window?.orderFrontRegardless()
        screenID = targetDisplay
        print("SCENE_READY display=\(targetDisplay) size=\(screen.frame.size)")
        fflush(stdout)
    }
}

let displayID = CommandLine.arguments.dropFirst().first.flatMap(UInt32.init) ?? 4128835
let app = NSApplication.shared
let delegate = SceneDelegate(targetDisplay: displayID)
app.setActivationPolicy(.accessory)
app.delegate = delegate
app.run()
