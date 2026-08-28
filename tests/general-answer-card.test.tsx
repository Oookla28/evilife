import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { GeneralAnswerCard } from "@/components/modules/SystemModules";

describe("GeneralAnswerCard", () => {
  it("makes the non-medical and ethics boundaries explicit", () => {
    render(
      <GeneralAnswerCard
        answer="力等于质量乘以加速度。"
        classification_reason="这是普通物理知识问题"
        key_points={["F = ma"]}
        search_status="ok"
        search_query="牛顿第二定律"
        search_results={[
          { title: "Newton's laws of motion", url: "https://example.org/newton", source: "example.org", snippet: "基础物理介绍", published_at: "Sat, 04 Jul 2026 07:00:00 GMT" },
        ]}
      />,
    );

    expect(screen.getByText("非医学通用回答")).toBeInTheDocument();
    expect(screen.getByText("伦理边界开启")).toBeInTheDocument();
    expect(screen.getByText("这不是医疗证据结论")).toBeInTheDocument();
    expect(screen.getByText("F = ma")).toBeInTheDocument();
    expect(screen.getByText("联网搜索来源")).toBeInTheDocument();
    expect(screen.getByText("2026-07-04")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Newton's laws of motion/ })).toHaveAttribute("href", "https://example.org/newton");
  });

  it("shows a clear prohibited state for operational harm", () => {
    render(
      <GeneralAnswerCard
        title="这部分不能提供操作性帮助"
        answer="不能协助骗取验证码。"
        boundary_status="blocked"
        boundary_label="伦理边界禁止"
      />,
    );

    expect(screen.getByText("伦理边界禁止")).toBeInTheDocument();
    expect(screen.getByText("禁止边界")).toBeInTheDocument();
  });
});
