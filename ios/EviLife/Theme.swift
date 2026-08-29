import SwiftUI

enum EvilifeTheme {
    // Brand (evidence-based health, teal/green)
    static let brand = Color(red: 0.13, green: 0.62, blue: 0.55)
    static let brandLight = Color(red: 0.90, green: 0.97, blue: 0.95)
    static let brandDark = Color(red: 0.08, green: 0.42, blue: 0.38)

    // Evidence / verdict colors
    static let supported = Color(red: 0.13, green: 0.62, blue: 0.55)   // 是
    static let partly = Color(red: 0.93, green: 0.62, blue: 0.14)      // 部分正确
    static let against = Color(red: 0.85, green: 0.32, blue: 0.28)     // 否
    static let insufficient = Color(red: 0.45, green: 0.50, blue: 0.58) // 证据不足

    static let riskRefused = Color(red: 0.85, green: 0.32, blue: 0.28)
    static let boundary = Color(red: 0.93, green: 0.62, blue: 0.14)
    static let crisis = Color(red: 0.13, green: 0.62, blue: 0.55)

    static let pageBg = Color(.systemGroupedBackground)
    static let cardBg = Color(.secondarySystemGroupedBackground)
    static let divider = Color(.separator)
    static let textPrimary = Color(.label)
    static let textSecondary = Color(.secondaryLabel)
    static let textTertiary = Color(.tertiaryLabel)
}

func verdictColor(_ verdict: String) -> Color {
    switch verdict {
    case "true", "SUPPORTED", "MOSTLY_SUPPORTED": return EvilifeTheme.supported
    case "partly_true", "CONTEXT_DEPENDENT", "MIXED_EVIDENCE": return EvilifeTheme.partly
    case "false", "NOT_SUPPORTED": return EvilifeTheme.against
    default: return EvilifeTheme.insufficient
    }
}

func verdictLabel(_ verdict: String) -> String {
    switch verdict {
    case "true", "SUPPORTED": return "是"
    case "MOSTLY_SUPPORTED": return "基本支持"
    case "partly_true", "CONTEXT_DEPENDENT": return "部分正确"
    case "MIXED_EVIDENCE": return "证据不一"
    case "false", "NOT_SUPPORTED": return "否"
    case "INSUFFICIENT_EVIDENCE": return "证据不足"
    default: return "证据不足"
    }
}

func strengthLabel(_ strength: String) -> String {
    switch strength {
    case "high": return "证据 高"
    case "medium", "moderate": return "证据 中"
    case "low": return "证据 低"
    default: return "证据不足"
    }
}

func observationKindLabel(_ kind: String) -> String {
    switch kind {
    case "water_ml": return "饮水"
    case "steps": return "步数"
    case "sleep_minutes": return "睡眠"
    case "weight_kg": return "体重"
    case "waist_cm": return "腰围"
    case "resting_heart_rate": return "静息心率"
    case "mood_score": return "心情"
    case "note": return "备注"
    default: return kind
    }
}

func observationUnit(_ kind: String) -> String {
    switch kind {
    case "water_ml": return "ml"
    case "steps": return "步"
    case "sleep_minutes": return "分钟"
    case "weight_kg": return "kg"
    case "waist_cm": return "cm"
    case "resting_heart_rate": return "次/分"
    case "mood_score": return "/ 5"
    default: return ""
    }
}
