import type { HealthAssessmentData } from "@/lib/types/health";

export const healthAssessmentDummy: HealthAssessmentData = {
  currentStage: "analysis",
  lastAssessmentDate: "2026-02-22",
  isAnonymous: false,

  questions: [
    {
      id: "q1",
      text: "How motivated do you feel about your research this week?",
      category: "motivation",
      stages: ["proposal", "coursework", "candidacy", "data_collection", "analysis", "writing", "defense_prep"],
      lowAnchor: "Not at all motivated",
      highAnchor: "Highly motivated",
    },
    {
      id: "q2",
      text: "How manageable does your current workload feel?",
      category: "workload",
      stages: ["proposal", "coursework", "candidacy", "data_collection", "analysis", "writing", "defense_prep"],
      lowAnchor: "Completely overwhelming",
      highAnchor: "Very manageable",
    },
    {
      id: "q3",
      text: "How connected do you feel to your research community?",
      category: "isolation",
      stages: ["proposal", "coursework", "candidacy", "data_collection", "analysis", "writing", "defense_prep"],
      lowAnchor: "Very isolated",
      highAnchor: "Well connected",
    },
    {
      id: "q4",
      text: "How satisfied are you with your progress on data analysis?",
      category: "progress_satisfaction",
      stages: ["analysis"],
      lowAnchor: "Very unsatisfied",
      highAnchor: "Very satisfied",
    },
    {
      id: "q5",
      text: "How supported do you feel by your supervision team?",
      category: "supervision_relationship",
      stages: ["proposal", "coursework", "candidacy", "data_collection", "analysis", "writing", "defense_prep"],
      lowAnchor: "Not supported",
      highAnchor: "Very supported",
    },
    {
      id: "q6",
      text: "Are you able to maintain boundaries between research and personal life?",
      category: "work_life_balance",
      stages: ["data_collection", "analysis", "writing", "defense_prep"],
      lowAnchor: "No boundaries at all",
      highAnchor: "Strong boundaries",
    },
    {
      id: "q7",
      text: "How often do you feel like you belong in your program?",
      category: "imposter_syndrome",
      stages: ["proposal", "coursework", "candidacy", "data_collection", "analysis", "writing", "defense_prep"],
      lowAnchor: "Rarely or never",
      highAnchor: "Almost always",
    },
    {
      id: "q8",
      text: "How would you rate your physical energy levels recently?",
      category: "physical_health",
      stages: ["data_collection", "analysis", "writing", "defense_prep"],
      lowAnchor: "Very low energy",
      highAnchor: "High energy",
    },
    {
      id: "q9",
      text: "How confident are you in interpreting your quantitative results?",
      category: "progress_satisfaction",
      stages: ["analysis"],
      lowAnchor: "Not confident",
      highAnchor: "Very confident",
    },
    {
      id: "q10",
      text: "Do you feel your analysis approach is well-defined and achievable?",
      category: "workload",
      stages: ["analysis"],
      lowAnchor: "Very unclear",
      highAnchor: "Crystal clear",
    },
  ],

  responses: [
    { questionId: "q1", value: 4 },
    { questionId: "q2", value: 3 },
    { questionId: "q3", value: 3 },
    { questionId: "q4", value: 4 },
    { questionId: "q5", value: 4 },
    { questionId: "q6", value: 2 },
    { questionId: "q7", value: 3 },
    { questionId: "q8", value: 3 },
    { questionId: "q9", value: 4 },
    { questionId: "q10", value: 3 },
  ],

  confidence: {
    overall: 68,
    trend: 4.5,
    dimensions: [
      { label: "Motivation", score: 76, category: "motivation" },
      { label: "Workload", score: 58, category: "workload" },
      { label: "Connectedness", score: 62, category: "isolation" },
      { label: "Progress", score: 74, category: "progress_satisfaction" },
      { label: "Supervision", score: 78, category: "supervision_relationship" },
      { label: "Work-life balance", score: 48, category: "work_life_balance" },
      { label: "Belonging", score: 60, category: "imposter_syndrome" },
      { label: "Energy", score: 56, category: "physical_health" },
    ],
  },

  burnout: {
    level: "managing",
    score: 38,
    emotionalExhaustion: 42,
    depersonalization: 28,
    personalAccomplishment: 72,
    trend: -3.2,
  },

  stageMessage: {
    stage: "analysis",
    stageLabel: "Data Analysis",
    normalizedChallenges: [
      "Feeling overwhelmed by the volume of data is extremely common at this stage",
      "Many researchers experience self-doubt when first engaging with complex analysis",
      "Work-life boundaries often become blurred during intensive analysis periods",
      "It's natural to question your methodology choices — this is part of rigorous research",
    ],
    encouragement:
      "You've reached a significant milestone — your data is collected and you're actively making sense of it. " +
      "This stage requires deep concentration, and it's okay to progress at a pace that feels sustainable. " +
      "Your supervision scores suggest a strong support system. Lean on it.",
    resources: [
      {
        title: "Managing Analysis Overwhelm",
        type: "article",
        description: "Strategies for breaking large datasets into manageable chunks",
      },
      {
        title: "5-Minute Grounding Exercise",
        type: "exercise",
        description: "A quick mindfulness practice for moments of research anxiety",
      },
      {
        title: "Graduate Peer Support Network",
        type: "community",
        description: "Weekly drop-in sessions with fellow doctoral researchers",
      },
      {
        title: "Counselling Services",
        type: "contact",
        description: "Free confidential support available to all registered researchers",
      },
    ],
  },

  discussionPrompts: [
    {
      id: "dp1",
      topic: "Workload pacing",
      prompt: "I'd like to discuss how to pace my analysis work more sustainably over the next few weeks.",
      context: "Your workload and work-life balance scores suggest you might benefit from discussing pacing strategies.",
      category: "workload",
    },
    {
      id: "dp2",
      topic: "Analysis approach",
      prompt: "Could we review my analysis plan together to make sure I'm on the right track?",
      context: "A brief review at this stage can build confidence and catch issues early.",
      category: "progress",
    },
    {
      id: "dp3",
      topic: "Well-being check-in",
      prompt: "I'd appreciate a few minutes to discuss how I'm feeling about the PhD more generally.",
      context: "Open conversations about well-being can strengthen the supervisory relationship.",
      category: "wellbeing",
    },
    {
      id: "dp4",
      topic: "Research community",
      prompt: "Are there any seminars, reading groups, or conferences you'd recommend I join?",
      context: "Your connectedness score suggests more peer engagement could be beneficial.",
      category: "relationship",
    },
    {
      id: "dp5",
      topic: "Career planning",
      prompt: "I'd like to start thinking about how this analysis chapter positions my broader career goals.",
      context: "Mid-program is a good time to align your research with longer-term aspirations.",
      category: "career",
    },
  ],

  riskTrajectory: [
    { date: "2025-06", risk: 32, confidence: 58 },
    { date: "2025-07", risk: 35, confidence: 55 },
    { date: "2025-08", risk: 40, confidence: 52 },
    { date: "2025-09", risk: 38, confidence: 56 },
    { date: "2025-10", risk: 42, confidence: 60 },
    { date: "2025-11", risk: 45, confidence: 58 },
    { date: "2025-12", risk: 43, confidence: 62 },
    { date: "2026-01", risk: 40, confidence: 65 },
    { date: "2026-02", risk: 38, confidence: 68 },
  ],
};
