"use client";

import { useState, useCallback } from "react";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Heart, Shield, Lock, Eye } from "lucide-react";
import { AdaptiveQuestionnaire } from "./adaptive-questionnaire";
import { ConfidenceScoreOutput } from "./confidence-score-output";
import { BurnoutIndicator } from "./burnout-indicator";
import { StageContextualMessaging } from "./stage-contextual-messaging";
import { SupervisorDiscussionPrompts } from "./supervisor-discussion-prompts";
import { RiskTrajectoryChart } from "./risk-trajectory-chart";
import type { HealthAssessmentData, QuestionResponse } from "@/lib/types/health";

interface HealthAssessmentViewProps {
  data: HealthAssessmentData;
  className?: string;
}

export function HealthAssessmentView({ data, className }: HealthAssessmentViewProps) {
  const [isAnonymous, setIsAnonymous] = useState(data.isAnonymous);

  const handleComplete = useCallback((responses: QuestionResponse[]) => {
    // Future: POST to backend with { responses, isAnonymous }
    void responses;
  }, []);

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString("en-US", {
      month: "long",
      day: "numeric",
      year: "numeric",
    });

  return (
    <div className={className}>
      {/* Header */}
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <Heart className="h-5 w-5 text-rose-400" />
            <h2 className="text-2xl font-bold tracking-tight">Wellness Check-in</h2>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            A private space to reflect on how you're doing — your responses guide support, not judgement
          </p>
          <p className="mt-0.5 text-[11px] text-muted-foreground/60">
            Last check-in: {formatDate(data.lastAssessmentDate)}
          </p>
        </div>

        <div className="flex items-center gap-3 self-start">
          {/* Anonymous mode toggle */}
          <div className="flex items-center gap-2.5 rounded-lg border border-dashed px-3 py-2">
            {isAnonymous ? (
              <Lock className="h-3.5 w-3.5 text-muted-foreground" />
            ) : (
              <Eye className="h-3.5 w-3.5 text-muted-foreground" />
            )}
            <Label htmlFor="anon-toggle" className="text-xs cursor-pointer">
              {isAnonymous ? "Anonymous" : "Identified"}
            </Label>
            <Switch
              id="anon-toggle"
              checked={isAnonymous}
              onCheckedChange={setIsAnonymous}
            />
          </div>
          <Badge
            variant="outline"
            className="flex items-center gap-1.5 border-dashed text-xs text-muted-foreground"
          >
            <Shield className="h-3 w-3" />
            Ethical
          </Badge>
        </div>
      </div>

      {/* Privacy notice */}
      {isAnonymous && (
        <div className="mb-4 flex items-start gap-2.5 rounded-lg border border-dashed border-blue-500/30 bg-blue-500/5 px-4 py-3">
          <Lock className="mt-0.5 h-4 w-4 shrink-0 text-blue-600 dark:text-blue-400" />
          <div>
            <p className="text-xs font-medium text-blue-700 dark:text-blue-300">
              Anonymous mode is active
            </p>
            <p className="mt-0.5 text-[11px] text-muted-foreground leading-relaxed">
              Your responses will be recorded without any personally identifiable information.
              They contribute to aggregate well-being reporting but cannot be traced back to you.
            </p>
          </div>
        </div>
      )}

      <Separator className="mb-6" />

      {/* Main layout */}
      <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
        {/* Left column — questionnaire + context */}
        <div className="space-y-6">
          <AdaptiveQuestionnaire
            questions={data.questions}
            currentStage={data.currentStage}
            existingResponses={data.responses}
            isAnonymous={isAnonymous}
            onComplete={handleComplete}
          />
          <StageContextualMessaging stageMessage={data.stageMessage} />
          <SupervisorDiscussionPrompts prompts={data.discussionPrompts} />
        </div>

        {/* Right column — scores, burnout, trajectory */}
        <div className="space-y-6">
          <ConfidenceScoreOutput confidence={data.confidence} />
          <BurnoutIndicator burnout={data.burnout} />
          <RiskTrajectoryChart data={data.riskTrajectory} />
        </div>
      </div>
    </div>
  );
}
