"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { FileUp, Loader2, Sparkles } from "lucide-react";
import { uploadDocument, getStageSuggestion } from "@/services/documents.service";
import { createBaselineFromDocument } from "@/services/baseline.service";
import { generateTimeline } from "@/services/timeline.service";
import { useAuthStore } from "@/lib/store";
import { timelineQueryKey } from "@/lib/hooks/use-timeline";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const ACCEPTED_TYPES = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"];
const MAX_SIZE_MB = 20;

const schema = z.object({
  file: z.any().refine(
    (val) => val instanceof FileList && val.length === 1,
    "Select a file"
  ).refine(
    (val) => {
      const file = val?.[0];
      return file && ACCEPTED_TYPES.includes(file.type);
    },
    "PDF or DOCX only"
  ).refine(
    (val) => {
      const file = val?.[0];
      return file && file.size <= MAX_SIZE_MB * 1024 * 1024;
    },
    `Max ${MAX_SIZE_MB}MB`
  ),
});

type FormValues = z.infer<typeof schema>;

type Step = "upload" | "parsing" | "creating" | "generating" | "success" | "error";

export default function NewTimelinePage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const [step, setStep] = useState<Step>("upload");
  const [uploadProgress, setUploadProgress] = useState(0);
  const [detectedStages, setDetectedStages] = useState<string[]>([]);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { file: undefined as unknown as FileList },
  });

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      if (!user?.id) throw new Error("Not authenticated");
      setStep("parsing");
      setUploadProgress(5);
      const result = await uploadDocument({
        file,
        userId: user.id,
        title: file.name,
        documentType: "research_proposal",
        onUploadProgress: (pct) => setUploadProgress(Math.min(90, pct + 5)),
      });
      setUploadProgress(95);
      return result.document_id;
    },
    onSuccess: async (documentId) => {
      setUploadProgress(100);
      toast.success("Document uploaded");
      try {
        const suggestion = await getStageSuggestion(documentId);
        setDetectedStages(suggestion.suggested_stage ? [suggestion.suggested_stage] : []);
      } catch {
        // Non-blocking
      }
      createBaselineMutation.mutate({ documentId });
    },
    onError: (err: Error) => {
      setStep("error");
      toast.error(err.message ?? "Upload failed");
    },
  });

  const createBaselineMutation = useMutation({
    mutationFn: async ({ documentId }: { documentId: string }) => {
      setStep("creating");
      const result = await createBaselineFromDocument({ documentId });
      return result.baseline_id;
    },
    onSuccess: (id) => {
      toast.success("Baseline created");
      generateMutation.mutate({ baselineId: id });
    },
    onError: (err: Error) => {
      setStep("error");
      toast.error(err.message ?? "Baseline creation failed");
    },
  });

  const generateMutation = useMutation({
    mutationFn: async ({ baselineId }: { baselineId: string }) => {
      setStep("generating");
      const result = await generateTimeline({ baselineId });
      return result;
    },
    onSuccess: (data) => {
      setStep("success");
      toast.success("Timeline generated");
      queryClient.invalidateQueries({ queryKey: timelineQueryKey(data.baseline_id) });
      setTimeout(() => router.push(`/dashboard/timeline?baseline=${data.baseline_id}`), 1200);
    },
    onError: (err: Error) => {
      setStep("error");
      toast.error(err.message ?? "Timeline generation failed");
    },
  });

  const [isDragging, setIsDragging] = useState(false);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file && ACCEPTED_TYPES.includes(file.type)) {
        form.setValue("file", e.dataTransfer.files as unknown as FileList, {
          shouldValidate: true,
        });
      }
    },
    [form]
  );

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const onSubmit = (values: FormValues) => {
    const file = values.file[0];
    if (file) uploadMutation.mutate(file);
  };

  const selectedFile = form.watch("file")?.[0];
  const isProcessing = ["parsing", "creating", "generating"].includes(step);

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Create timeline</h2>
        <p className="text-muted-foreground">
          Upload your research proposal or program requirements to generate a PhD timeline
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Upload document</CardTitle>
          <CardDescription>
            PDF or DOCX, max {MAX_SIZE_MB}MB. We&apos;ll extract milestones and stages.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {step === "upload" && (
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <div
                onDrop={onDrop}
                onDragOver={onDragOver}
                onDragLeave={onDragLeave}
                className={cn(
                  "flex min-h-[200px] flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors",
                  isDragging && "border-primary bg-primary/5",
                  selectedFile && "border-primary/50 bg-primary/5",
                  !selectedFile && !isDragging && "border-muted-foreground/25"
                )}
              >
                <FileUp className="mb-4 h-12 w-12 text-muted-foreground" />
                <p className="mb-2 text-sm font-medium text-foreground">
                  {selectedFile ? selectedFile.name : "Drag and drop your file here"}
                </p>
                <p className="mb-4 text-xs text-muted-foreground">
                  or click to browse
                </p>
                <input
                  type="file"
                  accept=".pdf,.docx"
                  className="hidden"
                  id="file-upload"
                  {...form.register("file", {
                    onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
                      const files = e.target.files;
                      if (files?.length)
                        form.setValue("file", files, { shouldValidate: true });
                    },
                  })}
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => document.getElementById("file-upload")?.click()}
                >
                  Choose file
                </Button>
                {form.formState.errors.file && (
                  <p className="mt-2 text-sm text-destructive">
                    {String(form.formState.errors.file.message ?? "")}
                  </p>
                )}
              </div>
              <Button type="submit" disabled={!selectedFile || uploadMutation.isPending}>
                {uploadMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Uploading...
                  </>
                ) : (
                  "Generate timeline"
                )}
              </Button>
            </form>
          )}

          {isProcessing && (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <Loader2 className="h-5 w-5 animate-spin text-primary" />
                <div>
                  <p className="text-sm font-medium">
                    {step === "parsing" && "Parsing document..."}
                    {step === "creating" && "Creating baseline..."}
                    {step === "generating" && "AI generating timeline..."}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {step === "generating" &&
                      "Detecting stages and milestones from your document"}
                  </p>
                </div>
              </div>
              <Progress
                value={
                  step === "parsing"
                    ? uploadProgress
                    : step === "creating"
                      ? 50
                      : 85
                }
                className="h-2"
              />
              {step === "generating" && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 rounded-md bg-muted/50 px-3 py-2">
                    <Sparkles className="h-4 w-4 shrink-0 text-amber-500" />
                    <span className="text-sm text-muted-foreground">
                      Analyzing structure, extracting milestones, estimating durations...
                    </span>
                  </div>
                  {detectedStages.length > 0 && (
                    <div className="rounded-md border border-border/60 bg-muted/30 px-3 py-2">
                      <p className="mb-1 text-xs font-medium text-muted-foreground">
                        Detected stage
                      </p>
                      <p className="text-sm text-foreground">{detectedStages[0]}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {step === "success" && (
            <div className="flex flex-col items-center py-8 text-center">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/20">
                <Sparkles className="h-6 w-6 text-emerald-600" />
              </div>
              <p className="font-medium text-foreground">Timeline ready</p>
              <p className="text-sm text-muted-foreground">
                Redirecting to your timeline...
              </p>
            </div>
          )}

          {step === "error" && (
            <div className="space-y-4">
              <p className="text-sm text-destructive">Something went wrong.</p>
              <Button
                variant="outline"
                onClick={() => {
                  setStep("upload");
                  form.reset();
                }}
              >
                Try again
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
