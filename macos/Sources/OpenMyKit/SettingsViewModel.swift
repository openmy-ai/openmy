import Foundation
import Observation

/// 设置面板状态机：持有屏幕上下文设置，负责加载与更新。
///
/// 对接 GET/POST /api/settings/screen-context。所有写操作走"部分字段合并"：
/// 只把改动字段 POST 给后端，拿回合并后的完整设置再覆盖本地，保证与后端一致。
///
/// 外观（主题/强调色）与个人资料（名字/emoji）在 Web 是纯 localStorage、无后端接口，
/// 因此不在本 VM 内，由视图层用 @AppStorage（键见 PreferenceKeys）直接读写。
@MainActor
@Observable
public final class SettingsViewModel {
    /// 当前屏幕上下文设置。加载前为 nil。
    public private(set) var settings: ScreenContextSettings?
    /// 错误信息（加载/更新异常）。
    public private(set) var errorMessage: String?
    /// 是否正在请求（供视图禁用按钮 / 显示进度）。
    public private(set) var isLoading = false

    private let client: APIClient

    public init(client: APIClient) {
        self.client = client
    }

    /// 加载屏幕上下文设置。失败时 errorMessage 置位，settings 保持原值。
    public func load() async {
        errorMessage = nil
        isLoading = true
        defer { isLoading = false }
        do {
            settings = try await client.screenContextSettings()
        } catch {
            errorMessage = String(describing: error)
        }
    }

    /// 切换是否启用。off 由后端联动（mode==off 时强制 enabled=false）。
    /// 这里仅把 enabled 作为部分字段提交；若要关到 off 应改用 setMode(.off)。
    @discardableResult
    public func setEnabled(_ enabled: Bool) async -> Bool {
        await update(["enabled": enabled])
    }

    /// 更新参与模式（off / summary_only / full）。
    /// 同时联动 enabled，对齐 Web（updateScreenContextMode 同发 enabled: mode!=='off'）。
    /// 否则后端把旧 enabled=false 合并下来，会出现「切回完整但实际仍不参与」的静默卡死。
    @discardableResult
    public func setMode(_ mode: ScreenContextSettings.Mode) async -> Bool {
        await update([
            "participation_mode": mode.rawValue,
            "enabled": mode != .off,
        ])
    }

    /// 保存排除项（按需只传非 nil 的字段，做部分合并）。
    @discardableResult
    public func saveExclusions(
        apps: [String]? = nil,
        domains: [String]? = nil,
        windowKeywords: [String]? = nil
    ) async -> Bool {
        var partial: [String: Any] = [:]
        if let apps { partial["exclude_apps"] = apps }
        if let domains { partial["exclude_domains"] = domains }
        if let windowKeywords { partial["exclude_window_keywords"] = windowKeywords }
        guard !partial.isEmpty else { return true }
        return await update(partial)
    }

    /// 通用部分字段更新：POST 合并后用返回值覆盖本地 settings。
    /// 失败时 errorMessage 置位、settings 不变，返回 false。
    @discardableResult
    public func update(_ partial: sending [String: Any]) async -> Bool {
        errorMessage = nil
        isLoading = true
        defer { isLoading = false }
        do {
            settings = try await client.updateScreenContextSettings(partial)
            return true
        } catch {
            errorMessage = String(describing: error)
            return false
        }
    }
}
