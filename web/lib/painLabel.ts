// Display names for pain slot keys (the keys themselves are stored answer
// identifiers and never change). Overrides replace jargon; everything else
// prettifies mechanically ("pain.manual_hours" -> "manual hours").
const OVERRIDES: Record<string, string> = { "pain.bus_factor": "key-person risk" };

export function painLabel(slotKey: string): string {
  return OVERRIDES[slotKey] ?? slotKey.replace("pain.", "").replaceAll("_", " ");
}
