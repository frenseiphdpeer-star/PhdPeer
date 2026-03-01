"use client";

import { useState, useMemo, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { ClipboardList, ChevronRight, ChevronLeft, Check, Lock } from "lucide-react";
import { cn } from "@/lib/utils";
import type { HealthQuestion, QuestionResponse, PhDStage } from "@/lib/types/health";

interface AdaptiveQuestionnaireProps {
  questions: HealthQuestion[];
  currentStage: PhDStage;
  existingResponses: QuestionResponse[];
  isAnonymous: boolean;
  className?: string;
  onComplete?: (responses: QuestionResponse[]) => void;
}

const stageLabels: Record<PhDStage, string> = {
  proposal: "Proposal",
  coursework: "Coursework",
  candidacy: "Candidacy",
  data_collection: "Data Collection",
  analysis: "Data Analysis",
  writing: "Writing Up",
  defense_prep: "Defense Prep",
};

const scaleLabels = [
  { value: 1, emoji: "1" },
  { value: 2, emoji: "2" },
  { value: 3, emoji: "3" },
  { value: 4, emoji: "4" },
  { value: 5, emoji: "5" },
];

export function AdaptiveQuestionnaire({
  questions,
  currentStage,
  existingResponses,
  isAnonymous,
  className,
  onComplete,
}: AdaptiveQuestionnaireProps) {
  const stageQuestions = useMemo(
    () => questions.filter((q) => q.stages.includes(currentStage)),
    [questions, currentStage]
  );

  const [currentIdx, setCurrentIdx] = useState(0);
  const [responses, setResponses] = useState<Map<string, number>>(() => {
    const m = new Map<string, number>();
    existingResponses.forEach((r) => m.set(r.questionId, r.value));
    return m;
  });
  const [submitted, setSubmitted] = useState(false);

  const current = stageQuestions[currentIdx];
  const total = stageQuestions.length;
  const answered = responses.size;
  const progressPct = total > 0 ? (answered / total) * 100 : 0;
  const allAnswered = stageQuestions.every((q) => responses.has(q.id));

  const handleSelect = useCallback((questionId: string, value: number) => {
    setResponses((prev) => {
      const next = new Map(prev);
      next.set(questionId, value);
      return next;
    });
  }, []);

  const handleSubmit = useCallback(() => {
    const result: QuestionResponse[] = [];
    responses.forEach((value, questionId) => {
      result.push({ questionId, value });
    });
    setSubmitted(true);
    onComplete?.(result);
  }, [responses, onComplete]);

  if (submitted) {
    return (
      <Card className={cn("overflow-hidden", className)}>
        <CardContent className="flex flex-col items-center py-12 text-center">
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/10">
            <Check className="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
          </div>
          <h3 className="text-lg font-semibold">Thank you for checking in</h3>
          <p className="mt-1 max-w-sm text-sm text-muted-foreground">
            Your responses have been recorded{isAnonymous ? " anonymously" : ""}. Your well-being matters,
            and these check-ins help build a picture of support over time.
          </p>
          <Button
            variant="outline"
            size="sm"
            className="mt-4"
            onClick={() => setSubmitted(false)}
          >
            Review responses
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ClipboardList className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Well-being Check-in</CardTitle>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-[10px]">
              {stageLabels[currentStage]} stage
            </Badge>
            {isAnonymous && (
              <Badge variant="secondary" className="text-[10px] gap-1">
                <Lock className="h-2.5 w-2.5" />
                Anonymous
              </Badge>
            )}
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          {total} questions tailored to your current stage · Take your time
        </p>
        <Progress value={progressPct} className="mt-2 h-1.5" />
        <p className="mt-1 text-[10px] text-muted-foreground tabular-nums">
          {answered} of {total} answered
        </p>
      </CardHeader>

      <CardContent className="space-y-5 pb-5">
        {current && (
          <div className="space-y-4">
            {/* Question */}
            <div className="rounded-xl bg-muted/40 p-4">
              <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-1.5">
                Question {currentIdx + 1} of {total}
              </p>
              <p className="text-sm font-medium leading-relaxed">{current.text}</p>
            </div>

            {/* Likert scale */}
            <div className="space-y-2">
              <div className="flex justify-between text-[10px] text-muted-foreground px-1">
                <span>{current.lowAnchor}</span>
                <span>{current.highAnchor}</span>
              </div>
              <div className="flex gap-2">
                {scaleLabels.map(({ value }) => {
                  const selected = responses.get(current.id) === value;
                  return (
                    <button
                      key={value}
                      onClick={() => handleSelect(current.id, value)}
                      className={cn(
                        "flex-1 rounded-lg border-2 py-3 text-sm font-semibold transition-all",
                        selected
                          ? "border-primary bg-primary/10 text-primary"
                          : "border-transparent bg-muted/60 text-muted-foreground hover:bg-muted hover:text-foreground"
                      )}
                    >
                      {value}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Navigation */}
        <div className="flex items-center justify-between pt-1">
          <Button
            variant="ghost"
            size="sm"
            disabled={currentIdx === 0}
            onClick={() => setCurrentIdx((i) => i - 1)}
            className="gap-1"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
            Previous
          </Button>

          {currentIdx < total - 1 ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setCurrentIdx((i) => i + 1)}
              className="gap-1"
            >
              Next
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          ) : (
            <Button
              size="sm"
              disabled={!allAnswered}
              onClick={handleSubmit}
              className="gap-1"
            >
              <Check className="h-3.5 w-3.5" />
              Submit check-in
            </Button>
          )}
        </div>

        {/* Quick nav dots */}
        <div className="flex justify-center gap-1.5 pt-1">
          {stageQuestions.map((q, i) => (
            <button
              key={q.id}
              onClick={() => setCurrentIdx(i)}
              className={cn(
                "h-2 w-2 rounded-full transition-all",
                i === currentIdx
                  ? "bg-primary scale-125"
                  : responses.has(q.id)
                    ? "bg-primary/40"
                    : "bg-muted-foreground/20"
              )}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
