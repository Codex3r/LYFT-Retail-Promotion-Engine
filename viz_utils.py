import numpy as np
import pandas as pd
import plotly.graph_objects as go


def resample_timeline(df: pd.DataFrame, granularity: str) -> pd.DataFrame:
  """Aggregates daily SKU timeline data into cleaner granularities to avoid chart clutter."""
  df_temp = df.copy()

  # Ensure chronological order
  df_temp = df_temp.sort_values("DAY")

  # Synthesize a calendar date sequence from DAY if not explicitly present
  # Dunnhumby DAY starts at 1 (representing sequential days)
  if "DATE" not in df_temp.columns:
    base_date = pd.Timestamp("2024-01-01")
    df_temp["DATE"] = base_date + pd.to_timedelta(df_temp["DAY"] - 1, unit="D")
  else:
    df_temp["DATE"] = pd.to_datetime(df_temp["DATE"])

  if granularity == "Daily":
    return df_temp

  df_temp = df_temp.set_index("DATE")

  if granularity == "Weekly":
    rule = "W"
  elif granularity == "Monthly":
    rule = "ME"
  elif granularity == "All-Time Smoothed":
    # 14-day rolling window smooths out day-of-week spikes while retaining macro cycle
    smoothed = df_temp.copy()
    smoothed["daily_units"] = (
        smoothed["daily_units"].rolling(14, min_periods=1).mean()
    )
    smoothed["baseline_28d"] = (
        smoothed["baseline_28d"].rolling(14, min_periods=1).mean()
    )
    smoothed["daily_revenue"] = (
        smoothed["daily_revenue"].rolling(14, min_periods=1).mean()
    )
    return smoothed.reset_index()
  else:
    return df_temp

  resampled = (
      df_temp.resample(rule)
      .agg({
          "PRODUCT_ID": "first",
          "COMMODITY_DESC": "first",
          "commodity_cohort": "first",
          "daily_units": "sum",
          "daily_revenue": "sum",
          "baseline_28d": "mean",
          "trough_21d": "mean",
          "is_promo": "max",
          "avg_discount": "mean",
          "DAY": "first",
      })
      .dropna(subset=["daily_units"])
      .reset_index()
  )

  return resampled


def build_interactive_timeline_chart(
    df: pd.DataFrame, sku_id: int, granularity: str
) -> go.Figure:
  """Builds a high-clarity Plotly figure with range selectors, volume bars, and baseline curves."""
  chart_df = resample_timeline(df, granularity)

  fig = go.Figure()

  # 1. Non-promotional Baseline Volume (Smooth dotted guidance line)
  fig.add_trace(
      go.Scatter(
          x=chart_df["DATE"],
          y=chart_df["baseline_28d"],
          name="28-Day Uncontaminated Baseline",
          line=dict(color="#94A3B8", width=2, dash="dash"),
          mode="lines",
          hovertemplate=(
              "Baseline: %{y:.1f} units<extra></extra>"
              if granularity == "Daily"
              else "Avg Baseline: %{y:.1f} units<extra></extra>"
          ),
      )
  )

  # 2. Actual Sales Volume (Color-coded bars: Teal for regular, Orange/Red for Promo)
  colors = [
      "#F97316" if promo > 0 else "#38BDF8" for promo in chart_df["is_promo"]
  ]

  fig.add_trace(
      go.Bar(
          x=chart_df["DATE"],
          y=chart_df["daily_units"],
          name="Actual Volume",
          marker=dict(color=colors, opacity=0.85),
          hovertemplate=(
              "<b>%{x|%b %d, %Y}</b><br>Volume: %{y:,.0f} units<br>Promo:"
              " %{text}<extra></extra>"
          ),
          text=[
              "Active (>=20% off)" if p > 0 else "Off Deal"
              for p in chart_df["is_promo"]
          ],
      )
  )

  # Chart Layout & Time Period Controls
  fig.update_layout(
      template="plotly_dark",
      paper_bgcolor="rgba(0,0,0,0)",
      plot_bgcolor="rgba(15,23,42,0.6)",
      margin=dict(l=20, r=20, t=50, b=20),
      height=460,
      legend=dict(
          orientation="h",
          yanchor="bottom",
          y=1.02,
          xanchor="right",
          x=1,
          font=dict(size=11),
      ),
      hovermode="x unified",
      xaxis=dict(
          showgrid=True,
          gridcolor="rgba(255,255,255,0.06)",
          # Built-in Range Selector Buttons (1M, 3M, 6M, 1Y, All)
          rangeselector=dict(
              buttons=list([
                  dict(count=1, label="1M", step="month", stepmode="backward"),
                  dict(count=3, label="3M", step="month", stepmode="backward"),
                  dict(count=6, label="6M", step="month", stepmode="backward"),
                  dict(count=1, label="1Y", step="year", stepmode="backward"),
                  dict(step="all", label="All"),
              ]),
              bgcolor="#1E293B",
              activecolor="#3B82F6",
              font=dict(color="#F8FAFC", size=11),
          ),
          rangeslider=dict(visible=True, thickness=0.06, bgcolor="#0F172A"),
          type="date",
      ),
      yaxis=dict(
          title="Units Sold",
          showgrid=True,
          gridcolor="rgba(255,255,255,0.08)",
          zeroline=False,
      ),
  )

  return fig
