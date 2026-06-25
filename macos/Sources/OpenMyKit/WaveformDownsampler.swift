import Foundation

/// 波形降采样：把原始 PCM 采样压缩成 N 个柱状峰值，供波形绘制。
///
/// 对齐 app/static/modules/waveform.js：把采样分成 N 个桶，
/// 每个桶取绝对值峰值作为该柱高度。空输入或 buckets<=0 时安全返回 []。
public enum WaveformDownsampler {

    /// 把 samples 降采样成 buckets 个峰值。
    /// - 桶内取 |sample| 的最大值。
    /// - samples 数量不足 buckets 时，空桶补 0。
    /// - 边界：samples 为空或 buckets <= 0 → []。
    public static func downsample(_ samples: [Float], buckets: Int) -> [Float] {
        guard buckets > 0, !samples.isEmpty else { return [] }

        var peaks = [Float](repeating: 0, count: buckets)
        let n = samples.count
        for i in 0..<buckets {
            // 用浮点比例切桶，避免整除丢尾。桶区间 [lo, hi)；空桶（buckets>采样数时）保持 0。
            let lo = Int((Double(i) * Double(n)) / Double(buckets))
            let hi = Int((Double(i + 1) * Double(n)) / Double(buckets))
            var peak: Float = 0
            var idx = lo
            while idx < hi && idx < n {
                let v = abs(samples[idx])
                if v > peak { peak = v }
                idx += 1
            }
            peaks[i] = peak
        }
        return peaks
    }
}
