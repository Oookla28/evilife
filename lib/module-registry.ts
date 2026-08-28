import { ComponentType } from "react";
import * as Stubs from "../components/modules/stubs";
import { EvidenceAnswer } from "../components/evidence/EvidenceAnswer";
import { EvidenceFlow } from "../components/evidence/EvidenceFlow";
import { MealAnalyzer } from "../components/modules/MealAnalyzer";
import { DocumentSummary } from "../components/modules/DocumentSummary";
import { PassbookShredder } from "../components/evidence/PassbookShredder";
import { PolaroidPrinterFlow } from "../components/evidence/PolaroidPrinterFlow";
import { AppleInteractiveDemo } from "../components/evidence/AppleInteractiveDemo";
import { FastingTimer } from "../components/lifestyle/FastingTimer";
import { HealthRecordDraft } from "../components/modules/HealthRecordDraft";
import { ChatFeaturePanel } from "../components/modules/ChatFeaturePanel";

import { 
  ConfirmationCard, 
  SafetyCard, 
  GeneralAnswerCard,
  CrisisSupportCard,
  ExtremeCrisisCareCard,
  LoadingModule, 
  UnsupportedModule, 
  ClarificationCard, 
  ErrorRecovery 
} from "../components/modules/SystemModules";

export type ModuleComponent = ComponentType<Record<string, unknown>>;
export type ModuleRegistryType = Record<string, ModuleComponent>;

export const moduleRegistry = {
  EvidenceAnswer: EvidenceAnswer,
  EvidenceFlow: EvidenceFlow,
  PassbookShredder: PassbookShredder,
  PolaroidPrinterFlow: PolaroidPrinterFlow,
  AppleInteractiveDemo: AppleInteractiveDemo,
  MealAnalyzer: MealAnalyzer,
  NutritionPanel: Stubs.NutritionPanel,
  FastingTimer: FastingTimer,
  HealthRecordDraft: HealthRecordDraft,
  ChatFeaturePanel: ChatFeaturePanel,
  DailyReview: Stubs.DailyReview,
  DocumentSummary: DocumentSummary,
  EvidenceCompare: Stubs.EvidenceCompare,
  ClarificationCard: ClarificationCard,
  SafetyCard: SafetyCard,
  GeneralAnswerCard: GeneralAnswerCard,
  CrisisSupportCard: CrisisSupportCard,
  ExtremeCrisisCareCard: ExtremeCrisisCareCard,
  ConfirmationCard: ConfirmationCard,
  LoadingModule: LoadingModule,
  ErrorRecovery: ErrorRecovery,
} as unknown as ModuleRegistryType;

export function getModuleComponent(type: string): ModuleComponent {
  const Component = moduleRegistry[type];
  if (!Component) {
    if (process.env.NODE_ENV === "development") {
      console.warn(`[ModuleRegistry] Unknown module type: ${type}`);
    }
    return UnsupportedModule;
  }
  return Component;
}
