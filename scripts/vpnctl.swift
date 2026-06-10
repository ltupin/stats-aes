import NetworkExtension
import Foundation

func sstr(_ s: NEVPNStatus) -> String {
    switch s {
    case .invalid: return "invalid"; case .disconnected: return "disconnected"
    case .connecting: return "connecting"; case .connected: return "connected"
    case .reasserting: return "reasserting"; case .disconnecting: return "disconnecting"
    @unknown default: return "unknown" }
}
let action = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "status"
let mgr = NEVPNManager.shared()
mgr.loadFromPreferences { err in
    if let err = err { FileHandle.standardError.write("load error: \(err)\n".data(using:.utf8)!); exit(2) }
    if action == "status" { print(sstr(mgr.connection.status)); exit(0) }
    let want: NEVPNStatus = (action == "down") ? .disconnected : .connected
    func check() { let s = mgr.connection.status; if s == want { print(sstr(s)); exit(0) } }
    NotificationCenter.default.addObserver(forName: .NEVPNStatusDidChange,
        object: mgr.connection, queue: .main) { _ in check() }
    do {
        if action == "up" { try mgr.connection.startVPNTunnel() }
        else if action == "down" { mgr.connection.stopVPNTunnel() }
    } catch { FileHandle.standardError.write("error: \(error)\n".data(using:.utf8)!); exit(3) }
    var ticks = 0
    Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { _ in
        ticks += 1; check()
        if ticks >= 30 { print("timeout:" + sstr(mgr.connection.status)); exit(1) }
    }
}
RunLoop.main.run()
