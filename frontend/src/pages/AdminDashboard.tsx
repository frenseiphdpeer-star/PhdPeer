/**
 * Institution Admin dashboard: cohort aggregation (anonymized).
 * Route: /admin/dashboard — AdminOnly guard.
 */

import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";

const AdminDashboard = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      <div className="max-w-4xl w-full text-center space-y-8">
        <div className="space-y-4">
          <h1 className="text-4xl md:text-5xl font-bold text-white">
            Institution Admin Dashboard
          </h1>
          <p className="text-xl text-muted-foreground">
            Cohort-level metrics (aggregated, anonymized).
          </p>
        </div>
        <div className="card-frensei p-8 space-y-6">
          <p className="text-muted-foreground">
            Permission: cohort_aggregation. Use{" "}
            <code className="mx-1 text-sm">GET /api/v1/admin/cohort</code>
            with admin auth headers for aggregated data.
          </p>
          <Button onClick={() => navigate("/home")} variant="outline">
            Back to Home
          </Button>
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;
