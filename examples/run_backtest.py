#!/usr/bin/env python3
"""
Example: Running the Scorer-Under Gate backtest

This script demonstrates how to:
1. Load your historical prop legs from CSV
2. Configure the gate parameters
3. Run the backtest
4. Analyze the results
5. Export detailed gate decisions
"""

import sys
from pathlib import Path

# Add parent directory to path to import abraxas
sys.path.insert(0, str(Path(__file__).parent.parent))

from abraxas.modules.scorer_under_gate import backtest, GateConfig
import json


def main():
    # Configuration
    csv_path = "legs_template.csv"  # Replace with your actual legs CSV
    output_path = "legs_with_gate.csv"

    # Option 1: Use default configuration
    cfg = GateConfig()

    # Option 2: Customize configuration
    # cfg = GateConfig(
    #     blowout_spread_abs=10.0,          # Require ±10 spread for blowout signal
    #     min_signals_required=3,            # Require 3+ signals (more conservative)
    #     arena_elasticity_low_quantile=0.25 # Bottom 25% of arenas
    # )

    print("Running Scorer-Under Gate Backtest...")
    print(f"Config hash: {json.dumps(cfg.__dict__, indent=2)}")
    print()

    # Run backtest
    df_with_gate, report = backtest(csv_path, cfg)

    # Print report
    print("=" * 60)
    print("BACKTEST REPORT")
    print("=" * 60)
    print(f"Total legs analyzed:           {report['rows_total']}")
    print(f"PTS-UNDER legs (subject):      {report['pts_lower_rows']}")
    print()
    print(f"BASELINE (no gate):")
    print(f"  Hit rate:                    {report['baseline_pts_lower_hit_rate']:.1%}")
    print()
    print(f"FILTERED (gate applied):")
    print(f"  Legs allowed through:        {report['filtered_pts_lower_rows']}")
    print(f"  Legs blocked:                {report['blocked_pts_lower_rows']}")
    print(f"  Volume retained:             {report['volume_retained']:.1%}")
    print(f"  Hit rate:                    {report['filtered_pts_lower_hit_rate']:.1%}")
    print()

    delta = report['filtered_pts_lower_hit_rate'] - report['baseline_pts_lower_hit_rate']
    print(f"IMPROVEMENT:")
    print(f"  Hit rate delta:              {delta:+.1%}")
    print()

    print(f"QUANTILE CUTS (computed from data):")
    print(f"  Arena low cut:               {report['cuts']['arena_low']:.3f}")
    print(f"  Coach low dist cut:          {report['cuts']['coach_low_dist']:.3f}")
    print(f"  Opp compression high cut:    {report['cuts']['opp_comp_high']:.3f}")
    print()

    print(f"Config provenance:             {report['cfg_hash']}")
    print("=" * 60)
    print()

    # Save detailed results
    df_with_gate.to_csv(output_path, index=False)
    print(f"Detailed results saved to: {output_path}")
    print()

    # Show example gate decisions for PTS lowers
    pts_lowers = df_with_gate[
        (df_with_gate['prop_type'] == 'PTS') &
        (df_with_gate['pick'] == 'lower')
    ]

    if not pts_lowers.empty:
        print("Example gate decisions:")
        for idx, row in pts_lowers.head(3).iterrows():
            print(f"\n  {row['player']} @ {row['arena']}")
            print(f"    Line: {row['line']} | Result: {row['result']} | Hit: {row['hit']}")
            print(f"    Gate: {'✓ ELIGIBLE' if row['gate_eligible'] else '✗ BLOCKED'}")
            print(f"    Signals: {row['gate_signals']}/5")
            reasons = json.loads(row['gate_reasons'])
            for signal, fired in reasons.items():
                status = "✓" if fired else "✗"
                print(f"      {status} {signal}")


if __name__ == "__main__":
    main()
