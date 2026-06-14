// Display-only provider labels. Mirrors the Python `provider_label` overrides
// (clio_cli/providers.py / clio_cli/models.py): the managed Omni Loop Portal
// subscription uses the internal slug `managed`, but users should see the
// product name. This maps slugs for *rendering only* — never mutate the stored
// `currentProvider` slug, which is round-tripped for model-switch routing.
const PROVIDER_LABELS: Record<string, string> = {
  managed: 'Omni Loop Portal'
}

export function providerLabel(slug: string): string {
  return PROVIDER_LABELS[slug] ?? slug
}
