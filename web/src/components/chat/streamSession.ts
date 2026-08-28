export const SLOW_HINT_FIRST_DELAY_MS = 4000;
export const SLOW_HINT_SECOND_DELAY_MS = 10000;
export const SLOW_HINT_THIRD_DELAY_MS = 20000;
export const ENABLE_SUBMIT_DELAY_MS = 400;

export const sleep = (ms: number): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, ms));

export interface ScheduledSession {
  timers: Set<number>;
  finish: () => void;
  onContent: () => void;
}

export const scheduleSession = (
  setIsLoading: (loading: boolean) => void,
  setIsSlow: (stage: "first" | "second" | "third" | false) => void,
  clearInFlight: () => void
): ScheduledSession => {
  const timers = new Set<number>();
  const scheduleSlowHint = (
    stage: "first" | "second" | "third",
    delay: number
  ) => {
    const timer = window.setTimeout(() => {
      timers.delete(timer);
      setIsSlow(stage);
    }, delay);
    timers.add(timer);
    return timer;
  };

  const slowTimers = [
    scheduleSlowHint("first", SLOW_HINT_FIRST_DELAY_MS),
    scheduleSlowHint("second", SLOW_HINT_SECOND_DELAY_MS),
    scheduleSlowHint("third", SLOW_HINT_THIRD_DELAY_MS),
  ];
  let enableSubmitTimer: number | undefined;

  const clearTimer = (timer: number) => {
    window.clearTimeout(timer);
    timers.delete(timer);
  };

  return {
    timers,
    onContent: () => {
      if (enableSubmitTimer !== undefined) window.clearTimeout(enableSubmitTimer);
      enableSubmitTimer = window.setTimeout(() => {
        setIsLoading(false);
      }, ENABLE_SUBMIT_DELAY_MS);
    },
    finish: () => {
      slowTimers.forEach(clearTimer);
      if (enableSubmitTimer !== undefined) {
        window.clearTimeout(enableSubmitTimer);
      }
      setIsLoading(false);
      setIsSlow(false);
      clearInFlight();
    },
  };
};
