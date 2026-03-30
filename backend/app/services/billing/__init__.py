"""Payments & Usage Metering.

Owns Stripe integration, webhook processing, LLM usage metering
(reserve/settle/release), and background sweep for stale reservations.
Reads pricing configuration from ``admin/``.
"""
