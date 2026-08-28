"use client";

import { FileText, ChevronRight, BookOpen } from "lucide-react";
import { useState } from "react";

export interface KeyPoint {
  title: string;
  description: string;
}

export interface DetailedClaim {
  text: string;
  page_number: number;
}

export interface DocumentSummaryProps {
  document_name: string;
  one_sentence_summary: string;
  key_points: KeyPoint[];
  detailed_claims: DetailedClaim[];
}

export function DocumentSummary({ document_name, one_sentence_summary, key_points, detailed_claims }: DocumentSummaryProps) {
  const [activeTab, setActiveTab] = useState<"key_points" | "detailed_claims">("key_points");

  const handlePageClick = (pageNumber: number) => {
    // In a real app, this would open a PDF viewer drawer
    alert(`打开 PDF 预览并跳转至第 ${pageNumber} 页`);
  };

  return (
    <div className="bg-white border border-border-divider rounded-2xl shadow-sm overflow-hidden">
      <div className="p-4 border-b border-border-divider bg-bg-page/50 flex items-center gap-3">
        <FileText className="text-brand" size={20} />
        <div>
          <h3 className="font-semibold text-text-primary text-sm leading-tight line-clamp-1">{document_name}</h3>
          <span className="text-xs text-text-secondary">文档摘要</span>
        </div>
      </div>

      <div className="p-5 flex flex-col gap-5">
        <div className="bg-brand/5 border border-brand/20 p-4 rounded-xl text-text-primary font-medium">
          {one_sentence_summary}
        </div>

        <div className="flex gap-4 border-b border-border-divider pb-2 mt-2">
          <button 
            className={`text-sm font-medium transition-colors pb-2 -mb-2 border-b-2 ${activeTab === "key_points" ? "border-brand text-brand" : "border-transparent text-text-secondary hover:text-text-primary"}`}
            onClick={() => setActiveTab("key_points")}
          >
            结构化要点
          </button>
          <button 
            className={`text-sm font-medium transition-colors pb-2 -mb-2 border-b-2 ${activeTab === "detailed_claims" ? "border-brand text-brand" : "border-transparent text-text-secondary hover:text-text-primary"}`}
            onClick={() => setActiveTab("detailed_claims")}
          >
            详细主张与引用
          </button>
        </div>

        <div>
          {activeTab === "key_points" && (
            <div className="flex flex-col gap-4 animate-in fade-in">
              {key_points?.map((point, idx) => (
                <div key={idx} className="flex flex-col gap-1">
                  <h4 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-brand" />
                    {point.title}
                  </h4>
                  <p className="text-sm text-text-secondary pl-3.5 leading-relaxed">
                    {point.description}
                  </p>
                </div>
              ))}
            </div>
          )}

          {activeTab === "detailed_claims" && (
            <div className="flex flex-col gap-3 animate-in fade-in">
              {detailed_claims?.map((claim, idx) => (
                <div key={idx} className="p-3 border border-border-divider rounded-xl hover:border-brand/30 transition-colors bg-bg-page">
                  <p className="text-sm text-text-primary mb-2 leading-relaxed">
                    {claim.text}
                  </p>
                  <button 
                    onClick={() => handlePageClick(claim.page_number)}
                    className="inline-flex items-center gap-1 text-xs text-brand bg-brand/10 hover:bg-brand/20 px-2 py-1 rounded transition-colors"
                  >
                    <BookOpen size={12} />
                    P.{claim.page_number}
                    <ChevronRight size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
