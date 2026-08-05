/** Authority / status chip (neutral · warn · fail · ok). */

export type ChipTone = "neutral" | "warn" | "fail" | "ok";

export type AuthorityChipProps = {
  label: string;
  tone?: ChipTone;
  title?: string;
};

/** Map common packet statuses to the allowed tones. */
export function toneForStatus(status: unknown): ChipTone {
  const s = String(status ?? "").toUpperCase();
  if (
    s === "FAIL" ||
    s === "FAILED" ||
    s === "REJECTED" ||
    s === "BLOCKED" ||
    s === "NOT_COMPUTABLE" ||
    s === "ERROR"
  ) {
    return "fail";
  }
  if (
    s === "WARN" ||
    s === "WARNING" ||
    s === "WATCH" ||
    s === "PENDING" ||
    s === "REVIEW_ELIGIBLE"
  ) {
    return "warn";
  }
  if (
    s === "OK" ||
    s === "PASS" ||
    s === "PASSED" ||
    s === "RELIABLE" ||
    s === "HEALTHY" ||
    s === "SUCCESS" ||
    s === "TRAINED"
  ) {
    return "ok";
  }
  return "neutral";
}

export function AuthorityChip({
  label,
  tone = "neutral",
  title,
}: AuthorityChipProps) {
  return (
    <span className={`chip chip-${tone}`} title={title}>
      {label || "—"}
    </span>
  );
}
