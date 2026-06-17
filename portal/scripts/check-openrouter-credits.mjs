#!/usr/bin/env node

const OPENROUTER_KEY = process.env.OPENROUTER_API_KEY?.trim() || "";
const CREDITS_URL = process.env.OPENROUTER_CREDITS_URL || "https://openrouter.ai/api/v1/credits";

async function main() {
  if (!OPENROUTER_KEY) {
    throw new Error("Set OPENROUTER_API_KEY to check OpenRouter credit usage.");
  }
  const res = await fetch(CREDITS_URL, {
    headers: { Authorization: `Bearer ${OPENROUTER_KEY}` },
  });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`OpenRouter credits check failed with ${res.status}: ${text.slice(0, 300)}`);
  }
  const payload = JSON.parse(text);
  const data = payload.data || {};
  const totalCredits = Number(data.total_credits);
  const totalUsage = Number(data.total_usage);
  if (!Number.isFinite(totalCredits) || !Number.isFinite(totalUsage)) {
    throw new Error("OpenRouter credits response did not include numeric total_credits and total_usage.");
  }
  const remaining = totalCredits - totalUsage;
  console.log(
    JSON.stringify(
      {
        total_credits: totalCredits,
        total_usage: totalUsage,
        remaining_credits: Number(remaining.toFixed(6)),
      },
      null,
      2,
    ),
  );
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : err);
  process.exitCode = 1;
});
