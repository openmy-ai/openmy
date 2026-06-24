import Foundation
import Observation

/// 驱动首次配置（选 STT 引擎）的状态机。
@MainActor
@Observable
public final class OnboardingViewModel {
    public private(set) var state: OnboardingState?
    public private(set) var errorMessage: String?
    public private(set) var isWorking = false

    private let client: APIClient

    public init(client: APIClient) {
        self.client = client
    }

    public var providers: [ProviderChoice] { state?.allProviders ?? [] }
    public var completed: Bool { state?.completed ?? false }

    /// 拉取 onboarding 状态。
    public func load() async {
        errorMessage = nil
        do {
            state = try await client.onboarding()
        } catch {
            errorMessage = String(describing: error)
        }
    }

    /// 选择引擎后重新拉取状态。
    public func select(_ provider: String) async {
        errorMessage = nil
        isWorking = true
        defer { isWorking = false }
        do {
            _ = try await client.selectProvider(provider)
            state = try await client.onboarding()
        } catch {
            errorMessage = String(describing: error)
        }
    }
}
