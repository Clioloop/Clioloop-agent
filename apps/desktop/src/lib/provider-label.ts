// Display-only provider labels. Mirrors the Python `provider_label` overrides
// (clio_cli/providers.py / clio_cli/models.py): the Omni Loop Portal
// subscription uses the internal slug `managed`, but users should see the
// product name. This maps slugs for *rendering only* — never mutate the stored
// `currentProvider` slug, which is round-tripped for model-switch routing.
export const OMNI_PROVIDER_SLUG = 'managed'
export const OMNI_PROVIDER_LABEL = 'Omni Loop Portal Subscription'
export const OMNI_PROVIDER_BADGE = 'Recommended'
export const OMNI_PROVIDER_DESCRIPTION =
  'Currently the only way to use Model Fusion · one login · no API keys · includes Tool Gateway'

const PROVIDER_LABELS: Record<string, string> = {
  [OMNI_PROVIDER_SLUG]: OMNI_PROVIDER_LABEL
}

export function providerLabel(slug: string): string {
  return PROVIDER_LABELS[slug] ?? slug
}

export function isOmniProvider(slug: string | null | undefined): boolean {
  return String(slug ?? '').toLowerCase() === OMNI_PROVIDER_SLUG
}

export function compareOmniFirst<T extends { slug?: string }>(a: T, b: T): number {
  const aOmni = isOmniProvider(a.slug)
  const bOmni = isOmniProvider(b.slug)

  if (aOmni === bOmni) {
    return 0
  }

  return aOmni ? -1 : 1
}
