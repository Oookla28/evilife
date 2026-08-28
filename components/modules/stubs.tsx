interface StubProps {
  message?: string;
}

function StubModule({ name, message }: { name: string; message: string }) {
  return (
    <div className="mb-4 rounded-xl border border-border-divider bg-white p-4 shadow-sm">
      <h4 className="font-medium text-text-primary">{name}</h4>
      <p className="mt-2 text-sm text-text-secondary">{message}</p>
    </div>
  );
}

export function FastingTimer({ message }: StubProps) {
  return <StubModule name="进食窗口计时" message={message ?? "计时功能等待确认后启动。"} />;
}

export function NutritionPanel({ message }: StubProps) {
  return <StubModule name="营养面板" message={message ?? "营养数据尚未生成。"} />;
}

export function DailyReview({ message }: StubProps) {
  return <StubModule name="每日回顾" message={message ?? "今天还没有可汇总的生活记录。"} />;
}

export function EvidenceCompare({ message }: StubProps) {
  return <StubModule name="证据对比" message={message ?? "正在等待可比较的证据结果。"} />;
}
