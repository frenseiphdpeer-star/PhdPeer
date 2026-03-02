"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { authService, type OAuthProvider } from "@/services/auth.service";
import { useAuthStore } from "@/lib/store";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const VALID_PROVIDERS = new Set<OAuthProvider>(["google", "microsoft"]);

export default function OAuthCallbackPage() {
  const params = useParams<{ provider: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [error, setError] = useState("");
  const exchanged = useRef(false);

  useEffect(() => {
    if (exchanged.current) return;
    exchanged.current = true;

    const provider = params.provider as OAuthProvider;
    const code = searchParams.get("code");

    if (!VALID_PROVIDERS.has(provider) || !code) {
      setError("Invalid OAuth callback");
      return;
    }

    authService
      .oauthCallback(provider, code)
      .then((res) => {
        setAuth(res.user, res.access_token, res.refresh_token);
        router.push("/dashboard");
        router.refresh();
      })
      .catch(() => {
        setError("Authentication failed. Please try again.");
      });
  }, [params.provider, searchParams, router, setAuth]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/30 p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <CardTitle className="text-destructive">Sign-in failed</CardTitle>
          </CardHeader>
          <CardContent className="text-center">
            <p className="mb-4 text-sm text-muted-foreground">{error}</p>
            <a href="/login" className="text-primary underline-offset-4 hover:underline">
              Back to login
            </a>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 p-4">
      <Card className="w-full max-w-md">
        <CardContent className="flex flex-col items-center gap-3 py-10">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">Completing sign-in...</p>
        </CardContent>
      </Card>
    </div>
  );
}
