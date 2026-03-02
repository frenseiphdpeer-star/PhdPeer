"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { logger } from "@/lib/logger";

interface Props {
  children: ReactNode;
  /** Optional custom fallback – receives error + reset callback. */
  fallback?: (props: { error: Error; reset: () => void }) => ReactNode;
  /** Human-readable section name for logs. */
  section?: string;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    logger.error("Unhandled render error", {
      message: error.message,
      stack: error.stack,
      componentStack: info.componentStack ?? undefined,
      section: this.props.section,
    }, "ErrorBoundary");
  }

  reset = () => this.setState({ error: null });

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    if (this.props.fallback) {
      return this.props.fallback({ error, reset: this.reset });
    }

    return <DefaultFallback error={error} reset={this.reset} section={this.props.section} />;
  }
}

function DefaultFallback({
  error,
  reset,
  section,
}: {
  error: Error;
  reset: () => void;
  section?: string;
}) {
  return (
    <Card className="border-destructive/30 bg-destructive/5">
      <CardContent className="flex flex-col items-center gap-4 py-12 text-center">
        <AlertTriangle className="h-10 w-10 text-destructive" />
        <div className="space-y-1">
          <h3 className="text-lg font-semibold">
            {section ? `Something went wrong in ${section}` : "Something went wrong"}
          </h3>
          <p className="text-sm text-muted-foreground max-w-md">
            {process.env.NODE_ENV === "development"
              ? error.message
              : "An unexpected error occurred. Please try again."}
          </p>
        </div>
        <Button variant="outline" onClick={reset} className="gap-2">
          <RefreshCw className="h-4 w-4" />
          Try again
        </Button>
      </CardContent>
    </Card>
  );
}
