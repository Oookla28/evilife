import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { MealAnalyzer } from "@/components/modules/MealAnalyzer";

describe("MealAnalyzer result states", () => {
  afterEach(cleanup);

  it("does not offer save when vision analysis failed", () => {
    render(
      <MealAnalyzer
        action_id="action-failed"
        items={[]}
        total_calories={[0, 0]}
        status="error"
        analysis_error="视觉识别暂时失败，没有生成餐食记录。"
      />
    );

    expect(screen.getByRole("alert")).toHaveTextContent("没有识别出有效餐食");
    expect(screen.queryByText("0–0 kcal")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "确认并保存" })).not.toBeInTheDocument();
  });

  it("renders recognized food and enables confirmation", () => {
    render(
      <MealAnalyzer
        action_id="action-ready"
        items={[
          {
            id: "food-1",
            name: "米饭",
            portion: "150g",
            portion_grams: [140, 160],
            estimated_calories: [180, 240],
            estimated_calories_center: 210,
            confidence: "medium",
            reference_basis: "按熟米饭估计重量与常见能量密度换算。",
            uncertainty: "分量为图片估算。",
          },
        ]}
        total_calories={[180, 240]}
        status="ready"
      />
    );

    expect(screen.getByText("米饭")).toBeInTheDocument();
    expect(screen.getAllByText("约 210 kcal")).toHaveLength(2);
    expect(screen.getAllByText("合理范围 180–240 kcal")).toHaveLength(2);
    expect(screen.getByText("中等置信")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /确认并保存/ })).toBeEnabled();

    fireEvent.click(screen.getByRole("button", { name: /150g/ }));
    const portionInput = screen.getByDisplayValue("150g");
    fireEvent.change(portionInput, { target: { value: "300g" } });
    fireEvent.keyDown(portionInput, { key: "Enter" });
    expect(screen.getAllByText("约 420 kcal")).toHaveLength(2);
    expect(screen.getAllByText("合理范围 360–480 kcal")).toHaveLength(2);
  });
});
