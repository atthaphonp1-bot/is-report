// useCountUp.js
// React 18 hook that animates a number from 0 → to (or down to a negative value)
// using an exponential ease‑out curve.
//
// Only the `react` package is imported; all other code is pure JavaScript
// and safe to run in a Node environment (e.g. for unit tests).

import { useState, useEffect, useRef } from "react";

/**
 * Exponential ease‑out curve.
 *
 * @param {number} t - Normalised time in the range [0, 1].
 * @returns {number} A value in the range [0, 1] where 0 → 0 and 1 → 1.
 */
export function easeOutExpo(t) {
  if (t <= 0) return 0;
  if (t >= 1) return 1;
  // 1 - 2^(−10·t) is the classic ease‑out‑expo formula.
  return 1 - Math.pow(2, -10 * t);
}

/**
 * Compute the integer value that should be displayed at a given point in an
 * animated count‑up.
 *
 * @param {number} to          - Target value (may be negative).
 * @param {number} elapsedMs   - Milliseconds elapsed since the animation started.
 * @param {number} durationMs  - Desired animation length in milliseconds.
 * @returns {number} The value to render now.
 */
export function valueAt(to, elapsedMs, durationMs) {
  // Guard against degenerate cases.
  if (durationMs <= 0 || !Number.isFinite(to)) return to;
  if (elapsedMs >= durationMs) return to;
  if (elapsedMs <= 0) return 0;

  const progress = elapsedMs / durationMs;
  const eased = easeOutExpo(progress);
  return Math.round(to * eased);
}

/**
 * React hook that returns the current animated number.
 *
 * @param {number} to - Desired final value.
 * @param {object} [options] - Optional configuration.
 * @param {number} [options.durationMs=900] - Animation duration.
 * @param {boolean} [options.enabled=true] - If `false`, the hook returns `to` immediately.
 * @param {number} [options.delayMs=0] - Wait this long before the value starts moving.
 *   ใช้ไล่หลั่นแถบกราฟทีละแถว ให้เข้ามาเป็นระลอกแทนที่จะวิ่งพร้อมกันหมด
 * @returns {number} The number that should be rendered at this moment.
 */
export function useCountUp(to, options = {}) {
  const {
    durationMs = 900,
    enabled = true,
    delayMs = 0,
  } = options;

  // Detect reduced‑motion preference safely (works in Node too).
  const prefersReducedMotion =
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // If animation is disabled, just return the final value.
  const immediate = !enabled || prefersReducedMotion;

  const [value, setValue] = useState(() => (immediate ? to : 0));

  const frameIdRef = useRef(null);
  const startRef = useRef(null);

  useEffect(() => {
    // Clean up any previous animation frame.
    if (frameIdRef.current !== null) {
      cancelAnimationFrame(frameIdRef.current);
      frameIdRef.current = null;
    }
    // ต้องล้างจุดเริ่มด้วย ไม่งั้นรอบถัดไป (เช่น to เปลี่ยน) จะนับเวลาต่อจากรอบแรก
    // แล้วกระโดดถึงค่าสุดท้ายทันทีเพราะ elapsed เลย durationMs ไปแล้ว
    startRef.current = null;

    // Short‑circuit: no animation needed.
    if (immediate) {
      setValue(to);
      return;
    }

    // Guard against impossible animation parameters.
    if (durationMs <= 0 || !Number.isFinite(to)) {
      setValue(to);
      return;
    }

    // Helper that runs on every RAF tick.
    const step = (timestamp) => {
      if (startRef.current === null) {
        startRef.current = timestamp;
      }
      const elapsed = timestamp - startRef.current - delayMs;
      const next = valueAt(to, elapsed, durationMs);
      setValue(next);

      if (elapsed < durationMs && next !== to) {
        // Continue animating.
        frameIdRef.current = requestAnimationFrame(step);
      } else {
        // Ensure the final value is exact.
        setValue(to);
        frameIdRef.current = null;
      }
    };

    // Only start the animation if requestAnimationFrame exists.
    if (typeof requestAnimationFrame === "function") {
      startRef.current = null;
      frameIdRef.current = requestAnimationFrame(step);
    } else {
      // Fallback for environments without RAF (e.g., Node tests).
      setValue(to);
    }

    // Cleanup on unmount or when deps change.
    return () => {
      if (frameIdRef.current !== null) {
        cancelAnimationFrame(frameIdRef.current);
        frameIdRef.current = null;
      }
    };
    // Dependencies that restart the animation when they change.
  }, [to, durationMs, delayMs, enabled, prefersReducedMotion, immediate]);

  return value;
}