"""Escrow and fee rules. Pure functions, no database, so they are easy to test and to change.

Money here is simulated. Nothing connects to a real payment provider.
"""


def compute_fee(price, rate, cap):
    """Platform fee = rate x price, never more than the cap. Returns (fee, net, capped)."""
    raw = round(price * rate, 2)
    fee = min(raw, cap)
    return fee, round(price - fee, 2), raw > cap


def preview(price, settings):
    fee, net, capped = compute_fee(price, settings["fee_rate"], settings["fee_cap"])
    return {
        "price": round(price, 2),
        "rate": settings["fee_rate"],
        "cap": settings["fee_cap"],
        "fee": fee,
        "net": net,
        "capped": capped,
    }


# Order lifecycle. Funds only move to the host from "ready_for_payout".
#   awaiting_payment -> in_escrow          sponsor pays the platform
#   in_escrow        -> under_review       photos came back unclear, a person checks
#   in_escrow        -> ready_for_payout   photos verified
#   under_review     -> ready_for_payout   reviewer approves (or back to in_escrow if rejected)
#   ready_for_payout -> released           platform confirms the transfer, fee is deducted
#   in_escrow / under_review / ready_for_payout -> refunded
STATUS_LABEL = {
    "awaiting_payment": "Awaiting payment",
    "in_escrow": "Held in escrow",
    "under_review": "Photos under review",
    "ready_for_payout": "Verified, ready for payout",
    "released": "Paid out",
    "refunded": "Refunded",
}
HELD = ("in_escrow", "under_review", "ready_for_payout")
