/**
 * Frontend Guards
 * 
 * Exports all guard functions and utilities.
 */

export {
  guardTimelineGenerationRequiresBaseline,
  guardCommitRequiresDraft,
  guardProgressRequiresCommittedTimeline,
  guardAnalyticsRequiresCommittedTimeline,
  useStateGuards,
  checkGuards,
  GuardViolationError,
} from './stateGuards';

export { RouteGuard, useRouteAccessible } from './RouteGuard';
export { ProtectedRoute } from './ProtectedRoute';
export { RouteErrorBoundary } from './RouteErrorBoundary';
export { useNavigationGuard } from './useNavigationGuard';
export {
  RoleGuard,
  ResearcherOnly,
  SupervisorOnly,
  AdminOnly,
} from './RoleGuard';
