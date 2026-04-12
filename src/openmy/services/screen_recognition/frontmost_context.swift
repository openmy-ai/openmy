import AppKit
import CoreGraphics
import Foundation

struct ContextPayload: Codable {
    let app_name: String
    let window_name: String
}

let workspace = NSWorkspace.shared
let app = workspace.frontmostApplication
let appName = app?.localizedName ?? ""
let processId = app?.processIdentifier ?? 0
var windowName = ""

if let windows = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] {
    for info in windows {
        let ownerPid = info[kCGWindowOwnerPID as String] as? pid_t ?? 0
        let layer = info[kCGWindowLayer as String] as? Int ?? 0
        if ownerPid == processId && layer == 0 {
            windowName = info[kCGWindowName as String] as? String ?? ""
            if !windowName.isEmpty {
                break
            }
        }
    }
}

let payload = ContextPayload(app_name: appName, window_name: windowName)
let encoder = JSONEncoder()
encoder.outputFormatting = [.withoutEscapingSlashes]
let data = try encoder.encode(payload)
print(String(data: data, encoding: .utf8) ?? "{}")
