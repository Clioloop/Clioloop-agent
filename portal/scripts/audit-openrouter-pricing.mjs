#!/usr/bin/env node

const OPENROUTER_MODELS_URL =
  process.env.OPENROUTER_MODELS_URL || "https://openrouter.ai/api/v1/models";
const PORTAL_BASE_URL = (process.env.PORTAL_BASE_URL || "https://portal.clioloop.com").replace(/\/+$/, "");
const PORTAL_TOKEN = process.env.PORTAL_AUDIT_TOKEN || process.env.OMNI_PORTAL_TOKEN || "";

const PRICING_KEYS = [
  "prompt",
  "completion",
  "request",
  "image",
  "web_search",
  "internal_reasoning",
  "input_cache_read",
  "input_cache_write",
];

function normalizePrice(value) {
  if (value === undefined || value === null || value === "") return "0";
  const num = Number(value);
  if (!Number.isFinite(num)) return String(value);
  return num.toPrecision(16).replace(/(?:\.0+|(\.\d*?)0+)$/, "$1");
}

function isTextOutput(model) {
  const output = model?.architecture?.output_modalities;
  return !Array.isArray(output) || output.includes("text");
}

async function fetchJson(url, headers = {}) {
  const res = await fetch(url, { headers });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`${url} failed with ${res.status}: ${text.slice(0, 300)}`);
  }
  try {
    return JSON.parse(text);
  } catch (err) {
    throw new Error(`${url} did not return JSON: ${err}`);
  }
}

function comparePricing(portalModel, upstreamModel, errors) {
  const portalPricing = portalModel.pricing || {};
  const upstreamPricing = upstreamModel.pricing || {};
  for (const key of PRICING_KEYS) {
    const portalValue = normalizePrice(portalPricing[key]);
    const upstreamValue = normalizePrice(upstreamPricing[key]);
    if (portalValue !== upstreamValue) {
      errors.push(
        `${portalModel.id}: pricing.${key} mismatch portal=${portalValue} openrouter=${upstreamValue}`,
      );
    }
  }
}

async function main() {
  if (!PORTAL_TOKEN) {
    throw new Error("Set PORTAL_AUDIT_TOKEN to a paid Omni Loop Portal bearer token.");
  }

  const [openrouterPayload, portalPayload] = await Promise.all([
    fetchJson(OPENROUTER_MODELS_URL),
    fetchJson(`${PORTAL_BASE_URL}/api/v1/models`, {
      Authorization: `Bearer ${PORTAL_TOKEN}`,
    }),
  ]);

  const openrouterModels = Array.isArray(openrouterPayload.data) ? openrouterPayload.data : [];
  const portalModels = Array.isArray(portalPayload.data) ? portalPayload.data : [];
  const openrouterById = new Map(openrouterModels.map((model) => [model.id, model]));
  const errors = [];

  for (const model of portalModels) {
    const upstream = openrouterById.get(model.id);
    if (!upstream) {
      errors.push(`${model.id}: exposed by portal but missing from OpenRouter`);
      continue;
    }
    if (!isTextOutput(upstream)) {
      errors.push(`${model.id}: exposed by portal but OpenRouter does not advertise text output`);
    }
    if (!model.pricing || typeof model.pricing !== "object") {
      errors.push(`${model.id}: portal response is missing pricing`);
      continue;
    }
    comparePricing(model, upstream, errors);
  }

  const upstreamTextCount = openrouterModels.filter(isTextOutput).length;
  if (portalModels.length > upstreamTextCount) {
    errors.push(
      `portal exposes ${portalModels.length} models, more than OpenRouter text-output count ${upstreamTextCount}`,
    );
  }

  if (errors.length) {
    console.error(`OpenRouter pricing audit failed with ${errors.length} issue(s):`);
    for (const line of errors.slice(0, 50)) console.error(`- ${line}`);
    if (errors.length > 50) console.error(`...and ${errors.length - 50} more`);
    process.exitCode = 1;
    return;
  }

  console.log(
    `OpenRouter pricing audit passed: ${portalModels.length} portal model(s), ${upstreamTextCount} OpenRouter text-output model(s).`,
  );
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : err);
  process.exitCode = 1;
});
