# 「是非题」前端动效与固件逆向 — 交接文档

| 字段 | 内容 |
|------|------|
| 项目 | 「是非题」循证健康查验平台 · Frontend |
| 技术栈 | Next.js 16 (App Router) + React 19 + TypeScript + Tailwind + Framer Motion |
| 固件依据 | iPhone 5 (iPhone5,1) · iOS **6.1.4** Build **10B350** (BrightonMaps) |
| IPSW | `D:\i4Tools9\Firmware\iPhone5,1_6.1.4_10B350_Restore.ipsw` |
| 工程路径 | `F:\刘子驿\002大学\4.线下\26暑线下\summer3\frontend` |
| 实验台 | `http://localhost:3000/lab` |
| 交接日期 | 2026-08-11 |

---

## 1. 你需要先知道的三件事

1. **动效不是纯拍脑袋**：CoverFlow / 碎纸机参数与类名对照过 iOS 6.1.4 静态分析（`dyld_shared_cache_armv7s` + PassKit / iPodUI 资源）。
2. **真正生效的页面是 `/lab`**：`app/lab/page.tsx` 内联了完整实验逻辑；改 `AppleInteractiveDemo.tsx`  alone 不会改变 lab 表现（首页 mock 模块才会用到后者）。
3. **添加卡片是两段式**：  
   - ① **慢速拍立得出纸**（留给后续「等模型流式输出」）  
   - ② **`transitionIn:fromFrame:` 落入 CoverFlow**（苹果风入库，不是二次飞入、也不是硬切）

---

## 2. 本地怎么跑

```bash
cd "F:\刘子驿\002大学\4.线下\26暑线下\summer3\frontend"
npm install
npm run dev
# 浏览器打开
# http://localhost:3000/lab      ← 动效实验台（优先看这个）
# http://localhost:3000          ← 主对话 + mock 场景
```

Mock 场景：侧边栏开发环境可切换 scenario（localStorage `evilife_mock_scenario`）。

---

## 3. 目录与职责

```text
frontend/
├── app/
│   ├── lab/page.tsx              # ★ 动效实验台（主战场）
│   ├── page.tsx                  # 首页多轮对话
│   ├── layout.tsx                # 字体 + suppressHydrationWarning
│   └── globals.css
├── components/
│   ├── evidence/
│   │   ├── PassbookShredScene.tsx    # ★ 碎纸场景（唯一实现）
│   │   ├── AppleInteractiveDemo.tsx  # 首页/mock 用的整合组件（与 lab 逻辑对齐）
│   │   ├── PassbookShredder.tsx      # 独立碎纸模块（复用 PassbookShredScene）
│   │   └── PolaroidPrinterFlow.tsx   # 另一套拍立得+Flow（较旧，非 lab 主路径）
│   ├── composer/ / settings/ / ui/
│   └── providers/MockProvider.tsx    # MSW，始终渲染 children
├── lib/
│   ├── module-registry.ts        # JSON 模块类型 → 组件
│   └── api/                      # SSE / orchestrate
├── mocks/handlers.ts             # 开发 SSE mock
├── public/shredder/              # ★ 从 iOS 6 PassKit 抽出的贴图
│   ├── ShredderMetal.png
│   ├── ShredderMicroPerf.png
│   ├── ShredderShardBackground.png
│   └── ShredderShardColorMask.png
└── HANDOVER.md                   # 本文档
```

### 固件分析产物（本机）

```text
C:\Users\94232\ipsw-analysis\iPhone5,1_6.1.4_10B350\
├── ANALYSIS_CoverFlow_PassbookShredder.md   # 逆向报告
├── symbol_hits.txt                          # 符号扫描
├── 048-2939-001-decrypted.dmg               # 解密 RootFS
└── rootfs\BrightonMaps10B350.N41OS\         # 抽出的文件系统片段
    ├── Applications\Shoebox.app\            # Passbook（显示名）
    ├── Applications\Music~iphone.app\
    ├── System\Library\PrivateFrameworks\iPodUI.framework\   # CoverFlow 资源
    ├── System\Library\Frameworks\PassKit.framework\         # 碎纸资源 + passd
    └── System\Library\Caches\com.apple.dyld\dyld_shared_cache_armv7s
```

RootFS 解密 Key（The Apple Wiki / 10B350）：

```text
1ab23a9c9e6c04f64cb817f3340e34bfba08f1d600c95cf568c8af0d97e9f8d25dabd066
```

---

## 4. 逆向结论速查（给实现用）

### 4.1 Cover Flow

| 项 | 内容 |
|----|------|
| 宿主 | `Music~iphone.app`（`com.apple.mobileipod`） |
| 资源 Framework | `iPodUI.framework`（`CoverFlow*.png` / `.s551`） |
| 3D 引擎 | **UIKit 私有** `UICoverFlowLayer`（代码在 dyld cache） |
| 业务包装 | `IUMusicCoverFlowView` / `IUMusicCoverFlowController` / `IUCoverFlowViewController` |
| 转场 | `transitionIn:` / **`transitionIn:fromFrame:`** / `transitionOut:toFrame:` |
| 控制器 | `IUCoverFlowTransitionController` · `performTransition:` |
| 前端映射 | 中心 0°、侧卡 **±70°**、z 前推、镜面倒影；入库用 `transitionIn` 阶段 |

### 4.2 Passbook 碎纸机

| 项 | 内容 |
|----|------|
| 宿主 | **Shoebox.app**（显示名 Passbook，`com.apple.Shoebox`） |
| Framework | `PassKit.framework` |
| 核心类 | **`PKPassShredderSheet`** |
| 堆栈宿主 | `PKPassGroupStackView` · `shredderSheet:didCompleteWithCancelled:` |
| 状态机 | `CAStateController` + `CAState`：`upOnBack → shred → finished → offscreen` |
| 网格变形 | `_meshTransformForInitialStrikeAtTime:` / `CAMeshTransform` |
| 粒子 | `CAEmitterLayer`（`shardEmitterLayer`） |
| 资源包 | **`ShredderSheet.caar`**（~708KB）+ `ShredderMetal` / `MicroPerf` / `Shard*` |
| 前端映射 | 金属机身升起 → 卡片**向下喂入齿口** → 齿口下吐竖条 + 纸屑 |

> iOS 7+ 已去掉碎纸机；本实现锚定 **iOS 6.1.4**。

---

## 5. 前端动效状态机（lab）

```text
phase:
  idle
    ├─ 添加 ──► printing ──► transitionIn ──► idle
    └─ 删除 ──► shredding ──────────────────► idle
```

| phase | 时长常量 | 行为 |
|-------|----------|------|
| `printing` | `PRINT_MS = 2400` | 拍立得从顶部槽口缓出 + 轻显影；**不入队**；旧 CoverFlow 压暗 |
| `transitionIn` | `TRANSITION_IN_MS = 620` | 对照 `transitionIn:fromFrame:`：平面卡 → z 前推到中心、侧卡 ±70° 弹簧让位、倒影淡入 |
| `shredding` | `SHRED_TOTAL_MS = 1700` | `PassbookShredScene` 全屏盖住；结束后从数组删卡 |
| `idle` | — | 可翻转居中卡、左右切换 |

### 弹簧参数（Framer Motion）

| 用途 | 配置 |
|------|------|
| CoverFlow 日常滑动 | `SPRING_FLOW` · stiffness 200 / damping 28 |
| 卡面翻转 | `SPRING_CARD` · 260 / 28 |
| **transitionIn 入库** | `SPRING_TRANSITION_IN` · 170 / 22 / mass 0.95（与碎纸同系 CASpring 手感） |
| 出纸 | **不用 spring**，用 `duration: PRINT_MS` + ease `[0.22, 0.61, 0.36, 1]`（可预期的等待窗） |

### 明确不要做的事（踩过的坑）

| 反模式 | 原因 |
|--------|------|
| 改组件却只看 lab | lab 不 import 组件时等于没改 |
| `layoutId` 做入库 | 与 3D `rotateY/z` 冲突，变形很丑 |
| 出纸结束再 spring 飞一次 | 和「慢速等待」叠床架屋 |
| 入队 `duration: 0` 硬切 | 丢苹果感；应使用 `transitionIn` |
| 碎纸 = 细金属条扫过整卡 + 整卡 scaleY | 不像 Passbook；应「机身 + 喂入齿口 + 下吐条」 |

---

## 6. 关键代码入口

### `app/lab/page.tsx`

- 状态：`cards` / `sel` / `phase` / `pendingCard` / `shredCard` / `enteringId`
- `handleAdd`：printing 定时器 → 写入 `cards` + `transitionIn` 定时器
- `handleDelete`：挂起 `shredCard` → `PassbookShredScene` → 删数组
- CoverFlow：`isEntering` 时 `initial` 为 fromFrame（`z:6, scale:0.97`）→ animate 到中心 3D 位

### `components/evidence/PassbookShredScene.tsx`

- 导出：`PassbookShredScene`、`SHRED_TOTAL_MS`
- 时间轴：升起 `RISE_MS` → 喂入 `FEED_MS`（delay `FEED_DELAY_MS`）→ 吐条/粒子
- 贴图：`/shredder/ShredderMetal.png` 等

### `lib/module-registry.ts`

注册名（mock JSON `type` 字段）：

- `AppleInteractiveDemo`
- `PassbookShredder`
- `PolaroidPrinterFlow`
- …

---

## 7. Hydration 说明

`app/layout.tsx` 已对 `<html>` / `<body>` 使用 `suppressHydrationWarning`，并稳定 `next/font` 配置。  
`MockProvider` **始终渲染 children**，MSW 在 `useEffect` 里启动，避免 SSR 返回 null。

若仍见 hydration 警告：先排除浏览器扩展改 `<html class>`。

---

## 8. 产品对接约定（给后端 / 模型同事）

### 首页真实对话卡片流（已接通）

- `EvidenceAnswer` 会把中文结构化回答交给 `MedicalEvidenceCardFlow`。
- 卡片按「核心结论 → 适用人群 → 证据边界 → 行动建议」生成；没有内容的类别不会生成空卡。
- 自动状态机为 `printing → transitionIn → printing(next) → idle`，上一张完成落位后才会开始下一张。
- CoverFlow 支持方向键、触控板横滑和鼠标/触摸拖拽；删除当前卡会调用 `PassbookShredScene`。
- 两份黄金 Evidence Packet 的用户可见字段已经中文化；未命中主题时由 Luna/Terra 按简体中文输出。

| 阶段 | 前端行为 | 建议后端/编排 |
|------|----------|----------------|
| 开始生成证据卡 | 进入 `printing`，拍立得慢出 | 此时跑模型 / SSE 推流 |
| 内容就绪 | 出纸动画可提前用 skeleton/占位文案 | 流式更新 `pendingCard` 字段（待实现） |
| 输出结束 | 进入 `transitionIn` 入库 | 可发 `card.ready` 事件对齐结束时机 |
| 用户删除 | `shredding` 后本地移除 | 调删除 API；动画不必等网络（乐观更新） |

**待办（建议 P1）**：把 `PRINT_MS` 从写死定时器改为「模型流结束信号 + 最短出纸时间 max(minPrint, streamDone)」。

---

## 9. 建议验收清单

- [ ] `/lab` 硬刷新后控制台有「transitionIn:fromFrame」相关日志
- [ ] **添加**：慢速出纸（约 2.4s）→ 卡片「吸入」CoverFlow 中心、侧卡让开、倒影出现
- [ ] **再添加**：旧卡弹簧到侧面 ±70°，无 layout 扭曲
- [ ] **删除**：金属机升起 → 卡往下进齿口 → 下方吐条/纸屑
- [ ] 首页 mock 选「苹果设计互动测试」与 lab 手感大致一致
- [ ] `public/shredder/*.png` 能 200 加载（碎纸机金属贴图）

---

## 10. 后续工作建议

| 优先级 | 项 |
|--------|----|
| P0 | 出纸与真实 SSE/模型流对齐（最短出纸 + 流结束） |
| P1 | 删除确认后接 `PKPassLibrary.removePass` 语义的真实 API |
| P1 | 移动端 CoverFlow `dragFlow:atPoint:`（`onPan` / `drag="x"`） |
| P2 | 解析 `ShredderSheet.caar` 状态名，精调碎纸 timing |
| P2 | 收敛 `PolaroidPrinterFlow` 与 lab 主路径，避免三套逻辑 |
| P3 | 从 cache 抽出 `UICoverFlowLayer` 镜像做更深反编译（可选） |

---

## 11. 联系与资产索引

| 资产 | 路径 |
|------|------|
| 本交接文档 | `frontend/HANDOVER.md` |
| 逆向完整报告 | `C:\Users\94232\ipsw-analysis\iPhone5,1_6.1.4_10B350\ANALYSIS_CoverFlow_PassbookShredder.md` |
| 符号全文 | `...\symbol_hits.txt` |
| 早期产品交接草稿 | `C:\Users\94232\是非题\frontend-docs\HANDOVER.md` |

有问题优先：

1. 打开 `/lab` 看 phase 日志  
2. 对照本文 §5 状态机  
3. 再查 `ANALYSIS_CoverFlow_PassbookShredder.md` 类/方法表  

祝接手顺利。有卡点把 phase 日志 + 录屏丢回来即可继续改。
