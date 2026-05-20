"""
Pure calculation functions for settlement sheets.
No database access. All amounts in integer cents.
"""

def calculate_settlement(door_revenue_cents, expenses_cents, deal_type,
                         guarantee_cents, door_split_pct, promoter_fee_pct, tax_pct):
    """
    Calculate settlement amounts.

    Returns: dict with keys:
        musician_payout_cents (int)
        venue_share_cents (int)
        promoter_fee_cents (int)
        tax_amount_cents (int)

    Usage:
        result = calculate_settlement(50000, 5000, 'hybrid', 20000, 70, 10, 8)
        settlement_id = create_settlement(conn, booking_id, 50000, 5000,
            result['musician_payout_cents'], result['venue_share_cents'],
            result['promoter_fee_cents'], result['tax_amount_cents'],
            g.user['id'])
    """
    net_door = door_revenue_cents - expenses_cents
    if net_door < 0:
        net_door = 0

    # Promoter fee on gross door revenue
    promoter_fee_cents = door_revenue_cents * promoter_fee_pct // 100

    # Tax on gross door revenue
    tax_amount_cents = door_revenue_cents * tax_pct // 100

    # Musician payout based on deal type
    if deal_type == 'guarantee':
        musician_payout_cents = guarantee_cents
    elif deal_type == 'door_split':
        musician_payout_cents = net_door * door_split_pct // 100
    else:  # hybrid
        door_share = net_door * door_split_pct // 100
        musician_payout_cents = max(guarantee_cents, door_share)

    # Venue gets the remainder
    venue_share_cents = door_revenue_cents - musician_payout_cents - promoter_fee_cents - tax_amount_cents

    return {
        'musician_payout_cents': musician_payout_cents,
        'venue_share_cents': venue_share_cents,
        'promoter_fee_cents': promoter_fee_cents,
        'tax_amount_cents': tax_amount_cents,
    }
