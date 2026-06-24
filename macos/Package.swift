// swift-tools-version: 6.0
import PackageDescription

// OpenMy macOS 原生前端：Swift 壳通过 localhost HTTP 对接现有 Python 后端
let package = Package(
    name: "OpenMy",
    platforms: [.macOS(.v14)],
    targets: [
        // 可测核心：模型 + APIClient + 视图模型状态机
        .target(name: "OpenMyKit"),
        // SwiftUI 壳
        .executableTarget(name: "OpenMyApp", dependencies: ["OpenMyKit"]),
        // TDD 主战场
        .testTarget(name: "OpenMyKitTests", dependencies: ["OpenMyKit"]),
    ]
)
