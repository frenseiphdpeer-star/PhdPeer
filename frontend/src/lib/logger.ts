/**
 * Structured logger with levels, context tags, and environment awareness.
 *
 * - In development: all levels go to console with colored prefixes.
 * - In production: debug/info are suppressed; warn/error emit structured JSON
 *   that can be shipped to an external service (Sentry, Datadog, etc.).
 */

type LogLevel = "debug" | "info" | "warn" | "error";

interface LogEntry {
  level: LogLevel;
  message: string;
  context?: string;
  data?: Record<string, unknown>;
  timestamp: string;
}

const IS_DEV = process.env.NODE_ENV === "development";
const IS_SERVER = typeof window === "undefined";

const LEVEL_PRIORITY: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

const MIN_LEVEL: LogLevel = IS_DEV ? "debug" : "warn";

function shouldLog(level: LogLevel): boolean {
  return LEVEL_PRIORITY[level] >= LEVEL_PRIORITY[MIN_LEVEL];
}

function emit(entry: LogEntry) {
  if (!shouldLog(entry.level)) return;

  if (IS_DEV) {
    const tag = entry.context ? `[${entry.context}]` : "";
    const fn = entry.level === "error" ? console.error
      : entry.level === "warn" ? console.warn
      : entry.level === "debug" ? console.debug
      : console.info;
    fn(`${entry.level.toUpperCase()} ${tag}`, entry.message, entry.data ?? "");
    return;
  }

  // Production: structured JSON for log ingestion
  const payload = {
    ...entry,
    env: IS_SERVER ? "server" : "client",
    url: IS_SERVER ? undefined : window.location.pathname,
  };
  // eslint-disable-next-line no-console
  console.log(JSON.stringify(payload));
}

function createLogMethod(level: LogLevel) {
  return (message: string, data?: Record<string, unknown>, context?: string) => {
    emit({
      level,
      message,
      context,
      data,
      timestamp: new Date().toISOString(),
    });
  };
}

export const logger = {
  debug: createLogMethod("debug"),
  info: createLogMethod("info"),
  warn: createLogMethod("warn"),
  error: createLogMethod("error"),

  /** Create a child logger pre-bound to a context tag. */
  child(context: string) {
    return {
      debug: (msg: string, data?: Record<string, unknown>) =>
        logger.debug(msg, data, context),
      info: (msg: string, data?: Record<string, unknown>) =>
        logger.info(msg, data, context),
      warn: (msg: string, data?: Record<string, unknown>) =>
        logger.warn(msg, data, context),
      error: (msg: string, data?: Record<string, unknown>) =>
        logger.error(msg, data, context),
    };
  },
};
