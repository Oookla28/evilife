import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { CrisisSupportCard, ExtremeCrisisCareCard } from "@/components/modules/SystemModules";

afterEach(cleanup);

describe("CrisisSupportCard", () => {
  it("优先展示安全询问、现实支持和可拨打电话", () => {
    render(
      <CrisisSupportCard
        crisis_level="imminent"
        title="先让你安全下来"
        message="请先停下危险动作。"
        check_in_question="你现在已经采取行动了吗？"
        immediate_steps={["联系一个可信任的人。", "不要独处。"]}
        reply_options={["现在安全", "有危险"]}
        reach_out_message="我现在一个人撑不住，你能给我打电话吗？"
        emergency_contacts={[
          { label: "医疗急救", number: "120" },
          { label: "报警求助", number: "110" },
          { label: "全国统一心理援助热线", number: "12356" },
        ]}
      />
    );

    expect(screen.getByRole("heading", { name: "先让你安全下来" })).toBeTruthy();
    expect(screen.getByText("你现在已经采取行动了吗？")).toBeTruthy();
    expect(screen.getByText("现在安全")).toBeTruthy();
    expect(screen.getByText("有危险")).toBeTruthy();
    expect(screen.getByText(/我现在一个人撑不住/)).toBeTruthy();
    expect(screen.getByRole("link", { name: /医疗急救/ })).toHaveAttribute("href", "tel:120");
    expect(screen.getByRole("link", { name: /全国统一心理援助热线/ })).toHaveAttribute("href", "tel:12356");
  });

  it("极端倾向使用独立关怀卡，不显示证据裁决", () => {
    render(
      <ExtremeCrisisCareCard
        title="我认真看到了这句话"
        check_in_question="已经有危险，还是现在暂时安全？"
        immediate_steps={["让一个人来到你身边。", "移开危险物品。", "立即联系急救。"]}
        emergency_contacts={[
          { label: "医疗急救", number: "120" },
          { label: "报警求助", number: "110" },
          { label: "全国统一心理援助热线", number: "12356" },
        ]}
      />
    );

    expect(screen.getByRole("heading", { name: "我认真看到了这句话" })).toBeTruthy();
    expect(screen.getByText("现在先不讨论证据")).toBeTruthy();
    expect(screen.getByRole("link", { name: /医疗急救/ })).toHaveAttribute("href", "tel:120");
    expect(screen.queryByText("证据不足")).not.toBeInTheDocument();
  });
});
