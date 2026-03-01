import type { ContinuityIndexData } from "@/lib/types/continuity";

/** Generate dummy momentum data for 3-4 year PhD timeline */
function generateMomentumSeries(): ContinuityIndexData["momentumSeries"] {
  const points: ContinuityIndexData["momentumSeries"] = [];
  const start = new Date("2022-09-01");
  const end = new Date("2026-06-01");
  let value = 45;

  for (let d = new Date(start); d <= end; d.setMonth(d.getMonth() + 1)) {
    value += (Math.random() - 0.45) * 8;
    value = Math.max(20, Math.min(95, value));
    points.push({
      date: d.toISOString().slice(0, 7),
      value: Math.round(value * 10) / 10,
    });
  }

  return points;
}

export const continuityDummyData: ContinuityIndexData = {
  score: 72,
  riskLevel: "medium",
  writingVelocity: 2400,
  milestoneCompletionPercent: 68,
  supervisionLatencyDays: 12,
  opportunityEngagementScore: 58,
  healthTrajectory: 0.12,
  momentumSeries: generateMomentumSeries(),
  totalMilestones: 24,
  completedMilestones: 16,
  opportunitiesActedOn: 7,
  opportunitiesTotal: 12,
};
