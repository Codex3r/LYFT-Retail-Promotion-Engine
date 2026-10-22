import pandas as pd
import numpy as np

TIMELINE_PATH = "sku_timeline_mart.parquet"
OUTPUT_SCORECARD_PATH = "sku_prescriptive_scorecard.parquet"

def generate_prescriptive_scorecard():
    print("--> Loading Scaled SKU Timeline Mart...")
    df = pd.read_parquet(TIMELINE_PATH)
    
    print(f"--> Ingested {df['PRODUCT_ID'].nunique()} unique SKUs. Processing prescriptive policies...")

    sku_metrics = []
    sku_volumes = df.groupby("PRODUCT_ID")["daily_units"].sum()
    volume_75th = sku_volumes.quantile(0.75)

    # Fast group iteration
    for product_id, group in df.groupby("PRODUCT_ID", sort=False):
        commodity = group["COMMODITY_DESC"].iloc[0]
        cohort = group["commodity_cohort"].iloc[0]
        
        tot_units = float(group["daily_units"].sum())
        tot_revenue = float(group["daily_revenue"].sum())
        
        promo_days = group[group["is_promo"] == 1]
        promo_units = float(promo_days["daily_units"].sum())
        non_promo_units = tot_units - promo_units
        promo_share = (promo_units / tot_units) if tot_units > 0 else 0.0

        avg_discount = float(group["discount_depth"].mean()) if "discount_depth" in group.columns else 0.15

        # 1. EMPIRICAL PCI (Cannibalization Propensity)
        group_sorted = group.sort_values("DAY")
        prev_was_promo = group_sorted["is_promo"].rolling(7, min_periods=1).max().shift(1).fillna(0)
        
        trough_mask = (
            (group_sorted["is_promo"] == 0) & 
            (prev_was_promo > 0) & 
            (group_sorted["daily_units"] < group_sorted["baseline_28d"])
        )
        trough_days = group_sorted[trough_mask]
        
        total_trough_deficit = float((trough_days["baseline_28d"] - trough_days["daily_units"]).sum())
        incremental_promo_lift = float(max(1.0, (promo_days["daily_units"] - promo_days["baseline_28d"]).sum()))
        
        raw_pci = total_trough_deficit / incremental_promo_lift
        
        if cohort == "STORABLE":
            pci = float(np.clip(raw_pci * 1.15, 0.42, 0.88))
            base_margin = 0.32
            base_repurchase_cycle = 30.0
        elif cohort == "EXPANDABLE":
            pci = float(np.clip(raw_pci * 0.85, 0.22, 0.52))
            base_margin = 0.36
            base_repurchase_cycle = 14.0
        else:  # PERISHABLE
            pci = float(np.clip(raw_pci * 0.45, 0.05, 0.28))
            base_margin = 0.26
            base_repurchase_cycle = 7.0

        # Calibrated Tier Thresholds (PCI >= 0.45 for RED)
        if pci >= 0.45:
            risk_tier = "RED"
        elif pci >= 0.20:
            risk_tier = "YELLOW"
        else:
            risk_tier = "GREEN"

        # 2. DYNAMIC DISCOUNT CEILING (d*)
        effective_elasticity = 1.3 + (0.7 * promo_share)
        optimal_discount = base_margin * (1.0 - (pci / (1.0 + effective_elasticity)))
        
        if risk_tier == "RED":
            d_star_ceiling = float(np.clip(optimal_discount, 0.10, 0.16))
        elif risk_tier == "YELLOW":
            d_star_ceiling = float(np.clip(optimal_discount, 0.17, 0.26))
        else:
            d_star_ceiling = float(np.clip(optimal_discount, 0.27, 0.38))

        # 3. INTER-PURCHASE REST COOLDOWN
        calculated_cooldown = base_repurchase_cycle * (1.0 + (pci * 0.8)) * (1.0 + (promo_share * 0.4))
        cooldown_days = int(np.clip(np.round(calculated_cooldown), 7, 56))

        # 4. ACTION SPECIFICATION
        is_high_velocity = tot_units >= volume_75th
        is_high_promo_share = promo_share >= 0.35

        if risk_tier == "RED":
            if is_high_promo_share:
                prescriptive_action = f"Pantry Exhaustion Protocol: Restrict deal to ≤{int(d_star_ceiling*100)}%, enforce {cooldown_days}d rest to drain household stock; reallocate trade to endcap display."
            else:
                prescriptive_action = f"Basket Value Defense: Cap deal at {int(d_star_ceiling*100)}%; mandate multi-pack purchases (Buy 2+) to offset post-promo volume deficit."
        elif risk_tier == "YELLOW":
            if is_high_promo_share:
                prescriptive_action = f"Subsidized Demand Taper: Taper promo depth down to {int(d_star_ceiling*100)}% over 2 cycles; evaluate EDLP (Everyday Low Price) transition."
            else:
                prescriptive_action = f"Controlled Profit Pulse: Standard promotional cadence with {int(d_star_ceiling*100)}% cap; cross-merchandise with high-margin non-deal complements."
        else:
            if is_high_velocity:
                prescriptive_action = f"Front-Page Traffic Driver: Zero forward-buying risk. Deploy up to {int(d_star_ceiling*100)}% circular front-page feature to maximize store-wide basket size."
            else:
                prescriptive_action = f"Aggressive Volume Capture: Highly elastic. Increase promotional frequency; safe to discount up to {int(d_star_ceiling*100)}% to seize category market share."

        sku_metrics.append({
            "PRODUCT_ID": int(product_id),
            "COMMODITY_DESC": commodity,
            "commodity_cohort": cohort,
            "total_units": float(tot_units),
            "total_revenue": float(tot_revenue),
            "promo_volume": float(promo_units),
            "non_promo_volume": float(non_promo_units),
            "promo_share": float(round(promo_share * 100, 1)),
            "avg_discount": float(round(avg_discount * 100, 1)),
            "PCI": float(round(pci, 3)),
            "risk_tier": risk_tier,
            "d_star_ceiling": float(round(d_star_ceiling, 3)),
            "cooldown_rest_days": int(cooldown_days),
            "prescriptive_action": prescriptive_action
        })

    scorecard_df = pd.DataFrame(sku_metrics)
    scorecard_df.to_parquet(OUTPUT_SCORECARD_PATH, index=False)
    print(f"\nSUCCESS: Saved calibrated scorecard to {OUTPUT_SCORECARD_PATH} ({len(scorecard_df)} SKUs).")
    print("\nRisk Tier Distribution Across Scaled Catalog:")
    print((scorecard_df["risk_tier"].value_counts(normalize=True).round(3) * 100).to_string())

if __name__ == "__main__":
    generate_prescriptive_scorecard()
