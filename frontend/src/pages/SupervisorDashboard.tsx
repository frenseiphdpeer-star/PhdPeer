/**
 * Supervisor dashboard: assigned students and risk visibility.
 * Route: /supervisor/dashboard — SupervisorOnly guard.
 */

import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";

const SupervisorDashboard = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      <div className="max-w-4xl w-full text-center space-y-8">
        <div className="space-y-4">
          <h1 className="text-4xl md:text-5xl font-bold text-white">
            Supervisor Dashboard
          </h1>
          <p className="text-xl text-muted-foreground">
            View assigned students and risk indicators.
          </p>
        </div>
        <div className="card-frensei p-8 space-y-6">
          <p className="text-muted-foreground">
            Data visibility: you see only your assigned students. Use the API{" "}
            <code className="mx-1 text-sm">GET /api/v1/supervisor/students</code>
            with your auth headers.
          </p>
          <Button onClick={() => navigate("/home")} variant="outline">
            Back to Home
          </Button>
        </div>
      </div>
    </div>
  );
};

export default SupervisorDashboard;
