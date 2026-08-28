import { http, HttpResponse, delay } from 'msw';

type MockFast = {
  id: string;
  start_at: string;
  end_at: string | null;
  goal_hours: number;
  status: "active" | "completed";
};

let mockActiveFast: MockFast | null = null;
const mockFastHistory: MockFast[] = [];
const mockMeals: Array<{
  id: string;
  action_id: string;
  created_at: string;
  estimated_total_calories: [number, number];
  status: "confirmed";
}> = [];
type MockObservation = {
  id: string;
  kind: string;
  value: number | null;
  note: string | null;
  source: "self_report" | "device" | "ai_estimate";
  observed_at: string;
};
const mockObservations: MockObservation[] = [];

const getScenario = () => {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('evilife_mock_scenario') || 'evidence-normal';
  }
  return 'evidence-normal';
};

const getModulePlanForScenario = (scenario: string) => {
  switch (scenario) {
    case 'apple-interactive':
      return [{
        module_id: "apple-demo-001",
        type: "AppleInteractiveDemo",
        status: "ready",
        props: {}
      }];

    case 'polaroid-printer':
      return [{
        module_id: "polaroid-001",
        type: "PolaroidPrinterFlow",
        status: "ready",
        props: {}
      }];

    case 'passbook-shredder':
      return [{
        module_id: "shredder-001",
        type: "PassbookShredder",
        status: "ready",
        props: {
          title: "今日午餐记录与卡路里风险分析",
          subtitle: "热量: 680 kcal · 包含反式脂肪酸警示",
          details: "RECORD ID: PASS-20260811-009"
        }
      }];

    case 'meal-estimated':
      return [{
        module_id: "meal-001",
        type: "MealAnalyzer",
        status: "ready",
        props: {
          action_id: "action-meal-1",
          image_url: "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=800&q=80",
          items: [
            { id: "item-1", name: "香煎鸡胸肉", portion: "150g", estimated_calories: [240, 280] },
            { id: "item-2", name: "水煮西兰花", portion: "100g", estimated_calories: [30, 45] },
            { id: "item-3", name: "蒸糙米饭", portion: "120g", estimated_calories: [130, 160] }
          ],
          total_calories: [400, 485],
          status: "pending_confirmation"
        }
      }];

    case 'document-summary':
      return [{
        module_id: "doc-001",
        type: "DocumentSummary",
        status: "ready",
        props: {
          document_name: "NEJM_Mediterranean_Diet_Cardiovascular_Risk.pdf",
          one_sentence_summary: "研究表明，补充初榨橄榄油或坚果的地中海饮食可将高危人群重大心血管事件风险降低约 30%。",
          key_points: [
            { title: "样本量与实验设计", description: "纳入 7447 名 55-80 岁无心血管疾病但属于高危风险的参与者，进行随机对照临床试验。" },
            { title: "干预组与对照组区别", description: "干预组分别每日补充 50ml 特级初榨橄榄油或 30g 混合坚果，对照组仅接受低脂饮食指导。" },
            { title: "核心终点分析", description: "中位随访 4.8 年，地中海饮食组显著降低心肌梗死、卒中及心血管死亡复合发生率。" }
          ],
          detailed_claims: [
            { text: "补充初榨橄榄油组的 HR 风险比为 0.70 (95% CI, 0.53-0.91)，统计学意义显著。", page_number: 4 },
            { text: "在干预期间未观察到由于饮食干预引发的严重不良反应事件。", page_number: 7 }
          ]
        }
      }];

    case 'evidence-degraded':
      return [{
        module_id: "answer-deg-001",
        type: "EvidenceAnswer",
        status: "ready",
        props: {
          question: "某些草药治疗失眠效果如何？",
          conclusion: "现有证据质量较低或结果存在冲突，尚无法得出明确疗效结论。",
          gate_status: "degraded",
          strength: "Low",
          limitations: ["样本量较小", "缺少双盲随机对照试验", "各文献研究剂型与剂量差异较大"],
          sources: [
            { title: "Herbal Supplements for Insomnia: A Systematic Review", year: 2021, journal: "Sleep Med Rev", pmid: "34123456" }
          ]
        }
      }];

    case 'evidence-refused':
      return [{
        module_id: "general-001",
        type: "GeneralAnswerCard",
        status: "ready",
        props: { 
          title: "非医学通用回答",
          answer: "牛顿第二定律描述物体加速度与所受合力成正比、与质量成反比，常写作 F = ma。",
          classification_reason: "这是普通物理知识问题，不属于医疗健康证据范围。",
          key_points: ["F 表示合力，m 表示质量，a 表示加速度。"],
          limitations: [],
          boundary_status: "limited",
          boundary_label: "伦理边界开启",
          gate_status: "degraded"
        }
      }];

    case 'unsupported-module':
      return [{
        module_id: "unknown-001",
        type: "GenomicsVisualizer",
        status: "ready",
        props: {}
      }];

    case 'evidence-normal':
    default:
      return [
        {
          module_id: "answer-001",
          type: "EvidenceAnswer",
          status: "ready",
          props: {
            question: "地中海饮食对心血管风险有什么证据？",
            conclusion: "高质量临床证据表明，长期坚持地中海饮食模式可显著降低心血管疾病风险（约 30%）。",
            gate_status: "normal",
            strength: "High",
            target_audience: "中老年人群、高血压及高血脂高危风险者",
            limitations: ["干预试验主要在地中海地区人群中开展", "严格遵循成本相对较高"],
            sources: [
              { title: "Primary Prevention of Cardiovascular Disease with a Mediterranean Diet", year: 2018, journal: "N Engl J Med", pmid: "29897866", doi: "10.1056/NEJMoa1800389" },
              { title: "Mediterranean Diet and Cardiovascular Health", year: 2019, journal: "Circulation Res", pmid: "30843441" }
            ],
            claims: [
              { claim_id: "C1", claim: "地中海饮食可以降低心血管疾病风险", type: "effectiveness", original_text: "地中海饮食对心血管风险有什么证据？", span_start: 0, span_end: 16 }
            ],
            verdict: {
              verdict: "partly_true",
              confidence: 0.74,
              evidence_grade: "high",
              claim: "地中海饮食可以降低心血管疾病风险",
              short_reason: "存在支持证据，但同样存在边界、冲突或局限证据，只能部分成立。",
              applies_to: ["心血管高危人群"],
              does_not_apply_to: ["地中海饮食不能替代药物治疗"],
              supporting_evidence: [
                { evidence_id: "E1-S1", source_id: "PMID-29897866", title: "Primary Prevention of Cardiovascular Disease with a Mediterranean Diet", year: 2018, source_type: "rct", organization: "NEJM", direction: "support", finding: "主要心血管事件风险降低约 30%", url: "https://pubmed.ncbi.nlm.nih.gov/29897866/" }
              ],
              opposing_evidence: [
                { evidence_id: "E2-A1", source_id: "PMID-30864165", title: "Mediterranean diet Cochrane review", year: 2019, source_type: "systematic_review", organization: "Cochrane", direction: "against", finding: "部分结局证据质量较低", url: "https://pubmed.ncbi.nlm.nih.gov/30864165/" }
              ],
              uncertainty: ["研究结论不一致"],
              last_updated: "2026-08-12",
              verdict_detail: "MIXED_EVIDENCE",
              what_could_change_this_verdict: ["更长随访周期的高质量随机试验结果", "权威指南的更新版本"]
            },
            trace_steps: [
              { step: "claim.parse", action: "decompose", output_summary: "拆解出 1 条可证伪主张" },
              { step: "safety.route", action: "assess", output_summary: "安全门=normal / 类别=safe" },
              { step: "route.select", action: "route", output_summary: "模式=eviroute_gate / 路由=fast_path" },
              { step: "evidence.build", action: "verify", output_summary: "支持 1 反对 1" }
            ],
            dynamic_notes: [
              {
                evidence_id: "N-PMID-29897866", source_id: "PMID-29897866", title: "Primary Prevention of Cardiovascular Disease with a Mediterranean Diet", year: 2018, study_type: "rct", direction: "support", finding: "PREDIMED 试验显示地中海饮食组主要心血管事件风险显著降低。", supports: ["心血管事件风险降低约 30%"], does_not_support: [], limitations: ["研究主要在地中海地区人群开展"], url: "https://pubmed.ncbi.nlm.nih.gov/29897866/", retrieved_at: "2026-08-12"
              },
              {
                evidence_id: "N-PMID-30864165", source_id: "PMID-30864165", title: "Mediterranean diet for primary prevention of CVD: a Cochrane review", year: 2019, study_type: "systematic_review", direction: "against", finding: "部分危险因素有改善，但多数临床结局证据质量较低。", supports: [], does_not_support: ["许多结局证据质量较低或研究数量不足"], limitations: ["研究持续时间短"], url: "https://pubmed.ncbi.nlm.nih.gov/30864165/", retrieved_at: "2026-08-12"
              }
            ]
          }
        },
        {
          module_id: "flow-001",
          type: "EvidenceFlow",
          status: "ready",
          props: {
            items: [
              {
                title: "PREDIMED 大型 RCT 临床试验",
                type: "RCT 随机对照试验",
                evidence_strength: "高证据",
                sample_size: "N = 7,447",
                conclusion: "降低重大心血管事件风险 30%",
                source: "N Engl J Med (2018)"
              },
              {
                title: "前瞻性队列 Meta 分析",
                type: "Meta 分析",
                evidence_strength: "中高证据",
                sample_size: "N > 500,000",
                conclusion: "对心脑血管全因死亡率呈保护效应",
                source: "Circulation (2020)"
              },
              {
                title: "低脂饮食对照组对比研究",
                type: "对照观察研究",
                evidence_strength: "中等证据",
                sample_size: "N = 3,200",
                conclusion: "相较传统低脂饮食，依从性与持久性更优",
                source: "Am J Clin Nutr (2021)"
              }
            ]
          }
        }
      ];
  }
};

export const handlers = [
  http.get('*/api/v1/health', () => {
    return HttpResponse.json({
      status: "ok",
      version: "0.1.0",
      timestamp: new Date().toISOString()
    });
  }),

  http.post('*/api/v1/orchestrate', async () => {
    const scenario = getScenario();
    await delay(600); // Simulate processing

    if (scenario === 'api-error') {
      return HttpResponse.json({
        error: {
          code: "VALIDATION_ERROR",
          message: "提交的输入无效，请重新尝试。",
          request_id: "req-err-001",
          retryable: true
        }
      }, { status: 400 });
    }

    if (scenario === 'network-timeout') {
      return HttpResponse.error();
    }

    const module_plan = getModulePlanForScenario(scenario);

    return HttpResponse.json({
      request_id: "req-" + Date.now(),
      session_id: "session-mock",
      run_id: "run-mock-123",
      intent: "evidence_query",
      risk_level: "low",
      gate_status: scenario === 'evidence-degraded' || scenario === 'evidence-refused' ? 'degraded' : 'normal',
      status: "accepted",
      module_plan,
      actions: [],
      timing_ms: { orchestrate: 120 }
    });
  }),

  // SSE Event Stream handler
  http.get('*/api/v1/runs/:runId/events', async ({ params }) => {
    const scenario = getScenario();
    const module_plan = getModulePlanForScenario(scenario);
    const runId = String(params.runId);
    const requestId = "req-mock-stream";
    let eventIndex = 0;
    const streamEvent = (type: string, payload: Record<string, unknown> = {}) => ({
      event_id: `evt-mock-${++eventIndex}`,
      request_id: requestId,
      run_id: runId,
      type,
      timestamp: new Date().toISOString(),
      payload,
    });

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        // Send initial heartbeat / started
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(streamEvent("run.started"))}\n\n`));

        await new Promise(r => setTimeout(r, 300));

        controller.enqueue(encoder.encode(`data: ${JSON.stringify(streamEvent("route.selected", { route: "mock" }))}\n\n`));
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(streamEvent("evidence.snapshot", { status: "ready" }))}\n\n`));

        await new Promise(r => setTimeout(r, 250));

        // Send module.ready with full plan
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(streamEvent("module.ready", { module_plan }))}\n\n`));

        await new Promise(r => setTimeout(r, 400));

        // Send run.completed
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(streamEvent("run.completed"))}\n\n`));

        controller.close();
      }
    });

    return new HttpResponse(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      },
    });
  }),

  http.get('*/api/v1/fasts/active', () => HttpResponse.json(mockActiveFast)),

  http.get('*/api/v1/fasts', () =>
    HttpResponse.json([...(mockActiveFast ? [mockActiveFast] : []), ...mockFastHistory])
  ),

  http.post('*/api/v1/fasts/start', async ({ request }) => {
    if (mockActiveFast) {
      return HttpResponse.json({ detail: 'an active timer already exists' }, { status: 409 });
    }
    const body = await request.json() as { goal_hours?: number };
    mockActiveFast = {
      id: `fast-${Date.now()}`,
      start_at: new Date().toISOString(),
      end_at: null,
      goal_hours: body.goal_hours ?? 16,
      status: 'active',
    };
    return HttpResponse.json(mockActiveFast);
  }),

  http.post('*/api/v1/fasts/:fastId/end', ({ params }) => {
    if (!mockActiveFast || mockActiveFast.id !== params.fastId) {
      return HttpResponse.json({ detail: 'active timer not found' }, { status: 404 });
    }
    const completed: MockFast = {
      ...mockActiveFast,
      end_at: new Date().toISOString(),
      status: 'completed',
    };
    mockFastHistory.unshift(completed);
    mockActiveFast = null;
    return HttpResponse.json(completed);
  }),

  http.get('*/api/v1/today', ({ request }) => {
    const date = new URL(request.url).searchParams.get('date') ?? new Date().toISOString().slice(0, 10);
    return HttpResponse.json({ date, fasts: mockFastHistory, meals: mockMeals, observations: mockObservations });
  }),

  http.get('*/api/v1/observations', ({ request }) => {
    const kind = new URL(request.url).searchParams.get('kind');
    return HttpResponse.json(kind ? mockObservations.filter((item) => item.kind === kind) : mockObservations);
  }),

  http.post('*/api/v1/observations', async ({ request }) => {
    const body = await request.json() as Omit<MockObservation, 'id' | 'observed_at'>;
    const record: MockObservation = {
      id: `obs-${Date.now()}`,
      kind: body.kind,
      value: body.value ?? null,
      note: body.note ?? null,
      source: body.source ?? 'self_report',
      observed_at: new Date().toISOString(),
    };
    mockObservations.unshift(record);
    return HttpResponse.json(record);
  }),

  // Action confirmation mock
  http.post('*/api/v1/actions/:actionId/confirm', async ({ params, request }) => {
    await delay(400);
    const body = await request.json() as {
      confirmed?: boolean;
      estimated_total_calories?: [number, number];
    };
    const actionId = String(params.actionId);
    if (body.confirmed !== false) {
      mockMeals.unshift({
        id: `meal-${Date.now()}`,
        action_id: actionId,
        created_at: new Date().toISOString(),
        estimated_total_calories: body.estimated_total_calories ?? [0, 0],
        status: 'confirmed',
      });
    }
    return HttpResponse.json({
      action_id: actionId,
      status: body.confirmed === false ? "cancelled" : "completed",
      affected_resource: body.confirmed === false ? undefined : {
        type: "meal_record",
        id: mockMeals[0]?.id,
      },
    });
  })
];
