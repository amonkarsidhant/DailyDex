#!/usr/bin/env python3
"""Create DailyDex Stripe products, monthly prices, and a webhook endpoint."""

import argparse
import os

import stripe


PLANS = {
    "creator": {"name": "DailyDex Creator", "amount": 1299},
    "studio": {"name": "DailyDex Studio", "amount": 3399},
}
EVENTS = [
    "checkout.session.completed",
    "checkout.session.expired",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.paid",
    "invoice.payment_failed",
]


def ensure_product(plan, config):
    products = stripe.Product.search(query=f"metadata['dailydex_plan']:'{plan}'", limit=1)
    if products.data:
        return products.data[0]
    return stripe.Product.create(
        name=config["name"], metadata={"dailydex_plan": plan}
    )


def ensure_price(plan, product, amount):
    lookup_key = f"dailydex_{plan}_monthly"
    prices = stripe.Price.list(lookup_keys=[lookup_key], active=True, limit=1)
    if prices.data:
        return prices.data[0]
    return stripe.Price.create(
        product=product.id,
        unit_amount=amount,
        currency="usd",
        recurring={"interval": "month"},
        lookup_key=lookup_key,
        metadata={"dailydex_plan": plan},
    )


def ensure_webhook(url):
    for endpoint in stripe.WebhookEndpoint.list(limit=100).auto_paging_iter():
        if endpoint.url == url and endpoint.status == "enabled":
            return endpoint, None
    endpoint = stripe.WebhookEndpoint.create(url=url, enabled_events=EVENTS)
    return endpoint, endpoint.secret


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--webhook-url", default="")
    args = parser.parse_args()
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not stripe.api_key:
        raise SystemExit("STRIPE_SECRET_KEY is required")

    for plan, config in PLANS.items():
        product = ensure_product(plan, config)
        price = ensure_price(plan, product, config["amount"])
        print(f"STRIPE_{plan.upper()}_PRICE_ID={price.id}")
    if args.webhook_url:
        endpoint, secret = ensure_webhook(args.webhook_url)
        print(f"STRIPE_WEBHOOK_ENDPOINT_ID={endpoint.id}")
        if secret:
            print(f"STRIPE_WEBHOOK_SECRET={secret}")
        else:
            print("Existing webhook reused; retain its previously issued signing secret.")


if __name__ == "__main__":
    main()
