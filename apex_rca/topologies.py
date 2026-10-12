"""Canonical caller-to-callee graphs for well-documented demo systems.

These edges are *not* extracted from RCAEval labels. They follow the public
application architectures:

- Online Boutique: GoogleCloudPlatform/microservices-demo (hipster shop).
- Sock Shop: microservices-demo/microservices-demo (Weaveworks).

Train Ticket has a large, version-dependent graph. This module does not
invent a complete Train Ticket topology; cases without traces fall back to
anomaly-only ranking for that system.

Metric column prefixes use ``frontend`` (Online Boutique) and ``front-end``
(Sock Shop). Trace spans may use ``frontendservice``; aliases live in
``config.SERVICE_ALIASES``.
"""

from __future__ import annotations

CANONICAL_GRAPHS: dict[str, tuple[tuple[str, str], ...]] = {
    "Online Boutique": (
        ("frontend", "adservice"),
        ("frontend", "cartservice"),
        ("frontend", "checkoutservice"),
        ("frontend", "currencyservice"),
        ("frontend", "productcatalogservice"),
        ("frontend", "recommendationservice"),
        ("frontend", "shippingservice"),
        ("checkoutservice", "cartservice"),
        ("checkoutservice", "currencyservice"),
        ("checkoutservice", "emailservice"),
        ("checkoutservice", "paymentservice"),
        ("checkoutservice", "productcatalogservice"),
        ("checkoutservice", "shippingservice"),
        ("recommendationservice", "productcatalogservice"),
        ("cartservice", "redis"),
    ),
    "Sock Shop": (
        ("front-end", "catalogue"),
        ("front-end", "carts"),
        ("front-end", "orders"),
        ("front-end", "user"),
        ("orders", "carts"),
        ("orders", "payment"),
        ("orders", "shipping"),
        ("orders", "user"),
        ("catalogue", "catalogue-db"),
        ("carts", "carts-db"),
        ("orders", "orders-db"),
        ("user", "user-db"),
        ("user", "session-db"),
        ("shipping", "queue-master"),
        ("queue-master", "rabbitmq"),
        ("payment", "rabbitmq"),
    ),
}


def canonical_edges(system_name: str) -> list[tuple[str, str]]:
    return list(CANONICAL_GRAPHS.get(system_name, ()))
