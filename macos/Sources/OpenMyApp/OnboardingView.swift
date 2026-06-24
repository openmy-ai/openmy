import SwiftUI
import OpenMyKit

/// 首次配置：选 STT 引擎。这是唯一需要用户决定的一步。
struct OnboardingView: View {
    @Bindable var vm: OnboardingViewModel
    var onDone: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text(vm.state?.headline ?? "选择转写引擎")
                .font(.largeTitle).bold()
            if let next = vm.state?.nextStep, !next.isEmpty {
                Text(next).foregroundStyle(.secondary)
            }

            ScrollView {
                VStack(spacing: 12) {
                    ForEach(vm.providers) { provider in
                        ProviderRow(provider: provider, isWorking: vm.isWorking) {
                            Task {
                                await vm.select(provider.name)
                                if vm.completed { onDone() }
                            }
                        }
                    }
                }
            }

            if let err = vm.errorMessage {
                Text(err).font(.footnote).foregroundStyle(.red)
            }
        }
        .padding(28)
        .task { if vm.state == nil { await vm.load() } }
    }
}

private struct ProviderRow: View {
    let provider: ProviderChoice
    let isWorking: Bool
    let onSelect: () -> Void

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 8) {
                    Text(provider.label).font(.headline)
                    if provider.isRecommended {
                        Text("推荐").font(.caption2).padding(.horizontal, 6).padding(.vertical, 2)
                            .background(.tint.opacity(0.18)).clipShape(Capsule())
                    }
                    Text(provider.type == "local" ? "本地" : "云端")
                        .font(.caption2).foregroundStyle(.secondary)
                }
                Text(provider.description).font(.subheadline).foregroundStyle(.secondary)
                if provider.needsApiKey {
                    Text("需要 API Key").font(.caption).foregroundStyle(.orange)
                }
            }
            Spacer()
            Button(action: onSelect) {
                Text(provider.isActive ? "已选" : "选这个")
            }
            .disabled(isWorking || provider.isActive)
            .buttonStyle(.borderedProminent)
        }
        .padding(14)
        .background(.quaternary.opacity(0.4))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}
