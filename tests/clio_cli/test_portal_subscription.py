"""Tests for clio_cli.portal_subscription resilience."""

import clio_cli.portal_subscription as ps


def test_items_skips_missing_feature_keys():
    """items() must not KeyError when the features dict is missing a canonical
    key (e.g. an older portal bundle without ``music_gen``). A bare
    self.features[key] would blank the /api/portal feature list."""
    partial = {
        "web": ps.ManagedFeatureState(
            "web", "Web tools", True, True, True, True, "Omni Loop Portal Subscription"
        ),
        # Deliberately omit music_gen (and others) to simulate a partial bundle.
    }
    feats = ps.ManagedSubscriptionFeatures(features=partial)

    items = feats.items()  # must not raise

    labels = [s.label for s in items]
    assert "Web tools" in labels
    # The omitted features are simply absent, not a crash.
    assert all(getattr(s, "key", None) in partial for s in items)
