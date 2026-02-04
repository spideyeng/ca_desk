# LNG deal economics

#!/usr/bin/env python3
"""
LNG Cargo Economics & P&L Model

Covers:
- FOB vs DES economics
- Shipping days, speed, distance
- Fuel consumption & LNG as fuel
- Time charter equivalent (TCE) / freight cost
- Regas fees, pipeline tariffs
- Simple hedge P&L (flat price hedge)
- CLI-ready structure via main()
"""

from dataclasses import dataclass, asdict
from typing import Literal, Dict, Any
import argparse


# -----------------------------
# Core data structures
# -----------------------------

@dataclass
class CargoParams:
    deal_type: Literal["FOB", "DES"]
    cargo_mmbtu: float                 # Total energy of cargo
    sales_price_des: float             # DES sales price (if DES) in USD/MMBtu
    purchase_price_fob: float          # FOB purchase price (if DES) or sales price (if FOB) in USD/MMBtu
    boiloff_rate_voyage: float         # Fraction of cargo lost on voyage (e.g. 0.001 = 0.1%)
    fuel_use_fraction_of_cargo: float  # Fraction of cargo used as fuel (e.g. 0.02 = 2%)
    freight_deduct_usd_per_mmbtu: float  # For FOB netback or internal freight assumption
    regas_fee_usd_per_mmbtu: float     # Regasification fee
    pipeline_tariff_usd_per_mmbtu: float  # Downstream pipeline tariff
    hedge_price_usd_per_mmbtu: float   # Flat price hedge level
    hedge_volume_mmbtu: float          # Volume hedged


@dataclass
class ShippingParams:
    distance_nm: float                 # Nautical miles
    speed_knots: float                 # Knots
    daily_charter_rate_usd: float      # USD/day
    boiloff_rate_sea_daily: float      # Daily boil-off fraction (e.g. 0.001 = 0.1%/day)


# -----------------------------
# Helper functions
# -----------------------------

def calc_shipping_days(distance_nm: float, speed_knots: float) -> float:
    """
    Shipping days = distance (nm) / (speed (knots) * 24 hours/day)
    """
    if speed_knots <= 0:
        raise ValueError("Speed must be positive.")
    return distance_nm / (speed_knots * 24.0)


def calc_voyage_boiloff(cargo_mmbtu: float, shipping_days: float, daily_boiloff_rate: float) -> float:
    """
    Approximate voyage boil-off using simple linear approximation:
    boiloff = cargo * daily_rate * days
    (You can swap to exponential if you want more realism.)
    """
    return cargo_mmbtu * daily_boiloff_rate * shipping_days


def calc_fuel_use(cargo_mmbtu: float, fuel_use_fraction: float) -> float:
    """
    Fuel use as a fraction of cargo.
    """
    return cargo_mmbtu * fuel_use_fraction


def calc_freight_cost(daily_charter_rate_usd: float, shipping_days: float) -> float:
    """
    Freight cost = daily charter * days.
    """
    return daily_charter_rate_usd * shipping_days


def calc_hedge_pnl(
    hedge_price: float,
    physical_price: float,
    hedge_volume: float
) -> float:
    """
    Simple flat price hedge P&L:
    - Long physical, short paper at hedge_price.
    - P&L = (physical_price - hedge_price) * hedge_volume
    """
    return (physical_price - hedge_price) * hedge_volume


# -----------------------------
# Main economics function
# -----------------------------

def lng_cargo_economics(
    cargo: CargoParams,
    shipping: ShippingParams
) -> Dict[str, Any]:
    """
    Compute LNG cargo P&L for FOB or DES structure.
    Returns a dict with detailed components.
    """

    # 1) Shipping days and freight
    shipping_days = calc_shipping_days(shipping.distance_nm, shipping.speed_knots)
    freight_cost_total = calc_freight_cost(shipping.daily_charter_rate_usd, shipping_days)

    # 2) Boil-off and fuel use
    voyage_boiloff_mmbtu = calc_voyage_boiloff(
        cargo.cargo_mmbtu,
        shipping_days,
        shipping.boiloff_rate_sea_daily
    )
    fuel_use_mmbtu = calc_fuel_use(cargo.cargo_mmbtu, cargo.fuel_use_fraction_of_cargo)

    total_losses_mmbtu = voyage_boiloff_mmbtu + fuel_use_mmbtu
    net_delivered_mmbtu = max(cargo.cargo_mmbtu - total_losses_mmbtu, 0.0)

    # 3) Regas + pipeline costs (applied on delivered volume)
    regas_cost_total = net_delivered_mmbtu * cargo.regas_fee_usd_per_mmbtu
    pipeline_cost_total = net_delivered_mmbtu * cargo.pipeline_tariff_usd_per_mmbtu

    # 4) Revenue and cost depending on deal type
    if cargo.deal_type == "DES":
        # Buy FOB, sell DES
        fob_cost_total = cargo.cargo_mmbtu * cargo.purchase_price_fob
        des_revenue_total = net_delivered_mmbtu * cargo.sales_price_des

        # Freight cost is explicit
        # Optional freight deduct notionally embedded in DES price can be tracked separately if desired
        gross_margin = des_revenue_total - fob_cost_total - freight_cost_total
        downstream_costs = regas_cost_total + pipeline_cost_total
        net_margin = gross_margin - downstream_costs

        physical_price_for_hedge = cargo.sales_price_des  # hedge vs DES price

    elif cargo.deal_type == "FOB":
        # Sell FOB, buyer lifts and pays freight
        # Here freight_deduct_usd_per_mmbtu is used as a notional freight to compute netback
        fob_revenue_total = cargo.cargo_mmbtu * cargo.purchase_price_fob
        freight_deduct_total = cargo.cargo_mmbtu * cargo.freight_deduct_usd_per_mmbtu
        netback_total = fob_revenue_total - freight_deduct_total

        # If you still want to model shipping yourself (e.g. portfolio shipping),
        # you can treat freight_cost_total as your actual freight and compare vs deduct.
        gross_margin = netback_total - freight_cost_total
        downstream_costs = regas_cost_total + pipeline_cost_total
        net_margin = gross_margin - downstream_costs

        physical_price_for_hedge = cargo.purchase_price_fob - cargo.freight_deduct_usd_per_mmbtu

    else:
        raise ValueError("deal_type must be 'FOB' or 'DES'.")

    # 5) Hedge P&L
    hedge_pnl = calc_hedge_pnl(
        hedge_price=cargo.hedge_price_usd_per_mmbtu,
        physical_price=physical_price_for_hedge,
        hedge_volume=cargo.hedge_volume_mmbtu
    )

    total_pnl = net_margin + hedge_pnl

    return {
        "inputs": {
            "cargo": asdict(cargo),
            "shipping": asdict(shipping),
        },
        "shipping_days": round(shipping_days, 3),
        "voyage_boiloff_mmbtu": round(voyage_boiloff_mmbtu, 2),
        "fuel_use_mmbtu": round(fuel_use_mmbtu, 2),
        "total_losses_mmbtu": round(total_losses_mmbtu, 2),
        "net_delivered_mmbtu": round(net_delivered_mmbtu, 2),
        "freight_cost_total_usd": round(freight_cost_total, 2),
        "regas_cost_total_usd": round(regas_cost_total, 2),
        "pipeline_cost_total_usd": round(pipeline_cost_total, 2),
        "gross_margin_usd": round(gross_margin, 2),
        "downstream_costs_usd": round(downstream_costs, 2),
        "net_margin_usd": round(net_margin, 2),
        "hedge_pnl_usd": round(hedge_pnl, 2),
        "total_pnl_usd": round(total_pnl, 2),
    }


# -----------------------------
# CLI wrapper
# -----------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="LNG Cargo Economics & P&L Model")

    # Deal / cargo
    p.add_argument("--deal_type", choices=["FOB", "DES"], required=True)
    p.add_argument("--cargo_mmbtu", type=float, required=True)
    p.add_argument("--sales_price_des", type=float, default=12.0)
    p.add_argument("--purchase_price_fob", type=float, default=10.0)
    p.add_argument("--boiloff_rate_voyage", type=float, default=0.001)
    p.add_argument("--fuel_use_fraction_of_cargo", type=float, default=0.02)
    p.add_argument("--freight_deduct_usd_per_mmbtu", type=float, default=0.20)
    p.add_argument("--regas_fee_usd_per_mmbtu", type=float, default=0.30)
    p.add_argument("--pipeline_tariff_usd_per_mmbtu", type=float, default=0.20)
    p.add_argument("--hedge_price_usd_per_mmbtu", type=float, default=11.0)
    p.add_argument("--hedge_volume_mmbtu", type=float, default=0.0)

    # Shipping
    p.add_argument("--distance_nm", type=float, required=True)
    p.add_argument("--speed_knots", type=float, default=15.0)
    p.add_argument("--daily_charter_rate_usd", type=float, default=80_000.0)
    p.add_argument("--boiloff_rate_sea_daily", type=float, default=0.001)

    return p


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    cargo = CargoParams(
        deal_type=args.deal_type,
        cargo_mmbtu=args.cargo_mmbtu,
        sales_price_des=args.sales_price_des,
        purchase_price_fob=args.purchase_price_fob,
        boiloff_rate_voyage=args.boiloff_rate_voyage,
        fuel_use_fraction_of_cargo=args.fuel_use_fraction_of_cargo,
        freight_deduct_usd_per_mmbtu=args.freight_deduct_usd_per_mmbtu,
        regas_fee_usd_per_mmbtu=args.regas_fee_usd_per_mmbtu,
        pipeline_tariff_usd_per_mmbtu=args.pipeline_tariff_usd_per_mmbtu,
        hedge_price_usd_per_mmbtu=args.hedge_price_usd_per_mmbtu,
        hedge_volume_mmbtu=args.hedge_volume_mmbtu,
    )

    shipping = ShippingParams(
        distance_nm=args.distance_nm,
        speed_knots=args.speed_knots,
        daily_charter_rate_usd=args.daily_charter_rate_usd,
        boiloff_rate_sea_daily=args.boiloff_rate_sea_daily,
    )

    result = lng_cargo_economics(cargo, shipping)

    print("=== LNG Cargo Economics & P&L ===")
    for k, v in result.items():
        if isinstance(v, dict):
            continue
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()


### to run in bash

# python lng_pnl.py \
#  --deal_type DES \
#  --cargo_mmbtu 3_000_000 \
#  --distance_nm 9000 \
#  --sales_price_des 12 \
#  --purchase_price_fob 9.5 \
#  --hedge_price_usd_per_mmbtu 11 \
#  --hedge_volume_mmbtu 2_000_000