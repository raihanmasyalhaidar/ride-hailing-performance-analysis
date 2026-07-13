"""
export_charts.py
----------------
Regenerate every figure referenced by README.md from the raw dataset.

Usage:
    python export_charts.py

Reads  : ncr_ride_bookings.csv  (same folder, or ./data/)
Writes : charts/funnel_pie.png
         charts/vehicle_revenue.png
         charts/temporal.png
         charts/locations.png
         charts/cancellation.png
         charts/dashboard_executive.png   (placeholder note — see bottom)

This script is self-contained: it re-applies the notebook's cleaning and
feature-engineering logic so the charts match the analysis exactly.
"""

from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import seaborn as sns

warnings.filterwarnings("ignore")
sns.set_theme(style="whitegrid")
plt.rcParams["figure.dpi"] = 120
plt.rcParams["savefig.dpi"] = 150
plt.rcParams["savefig.bbox"] = "tight"
plt.rcParams["font.size"] = 11

# --- Brand palette (matches the notebook) ---
C = {
    "primary": "#2563EB", "success": "#05A357", "warning": "#F6B000",
    "danger": "#E32934", "driver": "#DC2626", "customer": "#EA580C",
    "purple": "#7C3AED", "teal": "#0D9488", "neutral": "#8A8A8A",
}
VEHICLE_ORDER_COLOR = C["primary"]

OUT = Path("charts")
OUT.mkdir(exist_ok=True)


# ----------------------------------------------------------------------
# 1. Load
# ----------------------------------------------------------------------
def find_csv():
    for p in ["ncr_ride_bookings.csv", "data/ncr_ride_bookings.csv",
              "/kaggle/input/uber-ride-analytics-dashboard/ncr_ride_bookings.csv"]:
        if Path(p).exists():
            return p
    raise FileNotFoundError(
        "ncr_ride_bookings.csv not found. Place it in this folder or ./data/."
    )


print("Loading dataset ...")
df = pd.read_csv(find_csv())

# ----------------------------------------------------------------------
# 2. Clean (mirrors the notebook)
# ----------------------------------------------------------------------
print("Cleaning ...")
for col in ["Booking ID", "Customer ID"]:
    df[col] = df[col].astype(str).str.replace('"', "", regex=False).str.strip()

df.replace("null", np.nan, inplace=True)

num_cols = ["Avg VTAT", "Avg CTAT", "Booking Value",
            "Ride Distance", "Driver Ratings", "Customer Rating"]
for col in num_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")

df["Datetime"] = pd.to_datetime(df["Date"] + " " + df["Time"], errors="coerce")

# ----------------------------------------------------------------------
# 3. Feature engineering (subset needed for the charts)
# ----------------------------------------------------------------------
print("Engineering features ...")
df["Hour"] = df["Datetime"].dt.hour
df["Weekday"] = df["Datetime"].dt.day_name()
df["is_completed"] = df["Booking Status"].str.lower().eq("completed")
df["Route"] = df["Pickup Location"] + " -> " + df["Drop Location"]

status_category = {
    "Completed": "Success",
    "Incomplete": "Failed - Mid-Ride",
    "Cancelled by Driver": "Failed - Supply",
    "No Driver Found": "Failed - Supply",
    "Cancelled by Customer": "Failed - Demand",
}
df["StatusCategory"] = df["Booking Status"].map(status_category)

comp = df[df["is_completed"]].copy()
n = len(df)


# ----------------------------------------------------------------------
# CHART 1 — Booking funnel / status breakdown (donut)
# ----------------------------------------------------------------------
def chart_funnel():
    print("  -> funnel_pie.png")
    order = ["Completed", "Cancelled by Driver", "No Driver Found",
             "Cancelled by Customer", "Incomplete"]
    counts = df["Booking Status"].value_counts().reindex(order).fillna(0)
    colors = [C["primary"], C["driver"], C["purple"], C["customer"], C["neutral"]]

    fig, ax = plt.subplots(figsize=(9, 7))
    wedges, _, autotexts = ax.pie(
        counts.values, colors=colors, startangle=90,
        wedgeprops=dict(width=0.42, edgecolor="white"),
        autopct=lambda p: f"{p:.0f}%", pctdistance=0.79,
    )
    for t in autotexts:
        t.set_color("white"); t.set_fontweight("bold"); t.set_fontsize(11)
    ax.legend(wedges, [f"{s}  ({int(c):,})" for s, c in counts.items()],
              loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False)
    ax.set_title("Booking Funnel — Status Breakdown\n"
                 f"Completion Rate: {df['is_completed'].mean()*100:.0f}%",
                 fontweight="bold", fontsize=14)
    fig.savefig(OUT / "funnel_pie.png")
    plt.close(fig)


# ----------------------------------------------------------------------
# CHART 2 — Revenue by vehicle type (horizontal bar)
# ----------------------------------------------------------------------
def chart_vehicle_revenue():
    print("  -> vehicle_revenue.png")
    rev = (comp.groupby("Vehicle Type")["Booking Value"].sum()
           .sort_values(ascending=True) / 1e6)

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(rev.index, rev.values, color=C["primary"])
    for b, v in zip(bars, rev.values):
        ax.text(v + 0.1, b.get_y() + b.get_height() / 2,
                f"Rs {v:.2f}M", va="center", fontweight="bold", fontsize=10)
    ax.set_xlabel("Total Revenue (Rs, millions)")
    ax.set_title("Revenue by Vehicle Type — Volume, Not Margin\n"
                 "Average fare (~Rs 508) and Rs/km (~19.5) are nearly identical across types",
                 fontweight="bold", fontsize=13)
    ax.set_xlim(0, rev.max() * 1.15)
    fig.savefig(OUT / "vehicle_revenue.png")
    plt.close(fig)


# ----------------------------------------------------------------------
# CHART 3 — Temporal demand (hourly volume + completion overlay)
# ----------------------------------------------------------------------
def chart_temporal():
    print("  -> temporal.png")
    hourly = df.groupby("Hour").size()
    hourly_comp = df.groupby("Hour")["is_completed"].mean() * 100

    fig, axes = plt.subplots(1, 2, figsize=(18, 6))

    ax1 = axes[0]
    ax1.fill_between(hourly.index, hourly.values, color=C["primary"], alpha=0.25)
    ax1.plot(hourly.index, hourly.values, color=C["primary"], marker="o", linewidth=2)
    peak = hourly.idxmax()
    ax1.axvline(peak, color=C["danger"], linestyle="--", alpha=0.7)
    ax1.annotate(f"Peak ~{peak}:00", xy=(peak, hourly.max()),
                 xytext=(peak - 6, hourly.max() * 0.95),
                 color=C["danger"], fontweight="bold")
    ax1.set_title("Booking Volume by Hour", fontweight="bold", fontsize=13)
    ax1.set_xlabel("Hour of Day"); ax1.set_ylabel("Total Bookings")
    ax1.set_xticks(range(0, 24, 2))

    ax2 = axes[1]
    ax2.plot(hourly_comp.index, hourly_comp.values, color=C["success"],
             marker="o", linewidth=2)
    ax2.axhline(df["is_completed"].mean() * 100, color=C["neutral"],
                linestyle="--", label=f"Overall {df['is_completed'].mean()*100:.0f}%")
    ax2.set_ylim(55, 70)
    ax2.set_title("Completion Rate by Hour — Strikingly Flat",
                  fontweight="bold", fontsize=13)
    ax2.set_xlabel("Hour of Day"); ax2.set_ylabel("Completion Rate (%)")
    ax2.set_xticks(range(0, 24, 2))
    ax2.legend()

    fig.savefig(OUT / "temporal.png")
    plt.close(fig)


# ----------------------------------------------------------------------
# CHART 4 — Location & route intelligence (pickup / drop / route)
# ----------------------------------------------------------------------
def chart_locations():
    print("  -> locations.png")
    top_pickup = df["Pickup Location"].value_counts().head(8).sort_values()
    top_drop = df["Drop Location"].value_counts().head(8).sort_values()
    top_route = df["Route"].value_counts().head(8).sort_values()

    fig, axes = plt.subplots(1, 3, figsize=(21, 6))

    for ax, data, title, color in [
        (axes[0], top_pickup, "Top Pickup Locations", C["warning"]),
        (axes[1], top_drop, "Top Drop Locations", C["customer"]),
        (axes[2], top_route, "Top Routes (busiest ~17 trips)", C["primary"]),
    ]:
        bars = ax.barh(range(len(data)), data.values, color=color)
        ax.set_yticks(range(len(data)))
        labels = [l if len(l) <= 22 else l[:20] + "..." for l in data.index]
        ax.set_yticklabels(labels, fontsize=9)
        for b, v in zip(bars, data.values):
            ax.text(v, b.get_y() + b.get_height() / 2, f" {int(v)}",
                    va="center", fontsize=9, fontweight="bold")
        ax.set_title(title, fontweight="bold", fontsize=12)
        ax.set_xlabel("Bookings")

    fig.suptitle("Location & Route Intelligence — Demand Is Geographically Dispersed",
                 fontweight="bold", fontsize=14, y=1.02)
    fig.savefig(OUT / "locations.png")
    plt.close(fig)


# ----------------------------------------------------------------------
# CHART 5 — Cancellation root causes (driver + customer)
# ----------------------------------------------------------------------
def chart_cancellation():
    print("  -> cancellation.png")
    drv = df["Driver Cancellation Reason"].value_counts()
    cus = df["Reason for cancelling by Customer"].value_counts()

    fig, axes = plt.subplots(1, 2, figsize=(18, 6))

    for ax, data, title, color in [
        (axes[0], drv.sort_values(), "Driver Cancellation Reasons", C["driver"]),
        (axes[1], cus.sort_values(), "Customer Cancellation Reasons", C["customer"]),
    ]:
        bars = ax.barh(range(len(data)), data.values, color=color)
        ax.set_yticks(range(len(data)))
        labels = [l if len(l) <= 34 else l[:32] + "..." for l in data.index]
        ax.set_yticklabels(labels, fontsize=9)
        for b, v in zip(bars, data.values):
            ax.text(v, b.get_y() + b.get_height() / 2, f" {int(v):,}",
                    va="center", fontsize=9, fontweight="bold")
        ax.set_title(title, fontweight="bold", fontsize=12)
        ax.set_xlabel("Cancellations")

    fig.suptitle("Cancellation Root Causes", fontweight="bold", fontsize=14, y=1.02)
    fig.savefig(OUT / "cancellation.png")
    plt.close(fig)


# ----------------------------------------------------------------------
# Run all
# ----------------------------------------------------------------------
if __name__ == "__main__":
    chart_funnel()
    chart_vehicle_revenue()
    chart_temporal()
    chart_locations()
    chart_cancellation()

    print("\nDone. Charts written to ./charts/")
    print("\nNOTE: dashboard_executive.png is a SCREENSHOT of your Power BI")
    print("dashboard, not a matplotlib figure. Export it manually from Power BI")
    print("Desktop (File > Export > or a screen capture of the Executive Summary")
    print("page) and save it to charts/dashboard_executive.png so the README embed")
    print("resolves.")
