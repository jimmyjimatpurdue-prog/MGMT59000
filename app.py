"""
NovaRetail Customer Intelligence Dashboard
Built for: Sophia Martinez, Director of Customer Intelligence, NovaRetail
Purpose: explore revenue, segment health, and growth/decline signals across
region, product category, and sales channel.
"""

import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(
    page_title="NovaRetail Customer Intelligence",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Data cleaning
# ---------------------------------------------------------------------------
# The raw ProductCategory column has 34 near-duplicate labels (e.g. "Clothing",
# "Fashion", "Fashion & Apparel" are all separate values). This map consolidates
# them into 9 business-meaningful groups so charts stay readable.
CATEGORY_MAP = {
    "Electronics": "Electronics", "Gaming": "Electronics",
    "Clothing": "Clothing & Fashion", "Fashion & Apparel": "Clothing & Fashion",
    "Fashion": "Clothing & Fashion", "Fashion Accessories": "Clothing & Fashion",
    "Children's Clothing": "Clothing & Fashion", "Sportswear": "Clothing & Fashion",
    "Books": "Books & Media", "Books & Magazines": "Books & Media",
    "Groceries": "Groceries & Food", "Food & Beverages": "Groceries & Food",
    "Grocery": "Groceries & Food", "Grocery Items": "Groceries & Food",
    "Home Appliances": "Home & Furniture", "Home Decor": "Home & Furniture",
    "Home & Garden": "Home & Furniture", "Furniture": "Home & Furniture",
    "Home Improvement": "Home & Furniture", "Furniture & Decor": "Home & Furniture",
    "Gardening Tools": "Home & Furniture",
    "Health & Wellness": "Health & Beauty", "Beauty Products": "Health & Beauty",
    "Health & Beauty": "Health & Beauty", "Health Supplements": "Health & Beauty",
    "Beauty & Personal Care": "Health & Beauty", "Cosmetics": "Health & Beauty",
    "Sporting Goods": "Sports & Outdoors", "Sports & Outdoors": "Sports & Outdoors",
    "Outdoor Equipment": "Sports & Outdoors", "Sports Equipment": "Sports & Outdoors",
    "Toys": "Toys & Games", "Toys & Games": "Toys & Games",
    "Office Supplies": "Other", "Automotive": "Other",
}

# Consistent color per behavioral segment, used across every chart.
SEGMENT_COLORS = {
    "Promising": "#378ADD",  # blue  - opportunity
    "Growth": "#639922",     # green - positive momentum
    "Stable": "#888780",     # gray  - neutral
    "Decline": "#E24B4A",    # red   - warning / at risk
}
SEGMENT_ORDER = ["Promising", "Growth", "Stable", "Decline"]


@st.cache_data
def load_data(path: str = "NR_dataset.xlsx") -> pd.DataFrame:
    df = pd.read_excel(path)

    # 1 record has no segment label. The assignment brief describes the
    # dataset as "99 sampled consumers" -- dropping this one null-label row
    # brings the valid record count to exactly 99, so this is the intended cut.
    df = df.dropna(subset=["label"])

    # Consolidate the 34 raw category strings into 9 groups.
    df["CategoryGroup"] = df["ProductCategory"].map(CATEGORY_MAP).fillna("Other")

    # "55+" and "55-64" are the same bucket recorded two different ways.
    df["CustomerAgeGroup"] = df["CustomerAgeGroup"].replace({"55-64": "55+"})

    df["TransactionDate"] = pd.to_datetime(df["TransactionDate"])
    # Weekly bucket for the trend chart -- the data only spans ~5 weeks, so
    # daily granularity would be too noisy.
    df["Week"] = df["TransactionDate"].dt.to_period("W").apply(lambda p: p.start_time)

    return df


df = load_data()

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
st.sidebar.header("Filters")

# Every filter widget below has an explicit `key`. Reset works by deleting
# those keys from session_state and rerunning -- Streamlit then reinitializes
# each widget from its `default=` value, same as a fresh page load.
FILTER_KEYS = [
    "f_segment", "f_region", "f_category", "f_channel", "f_age", "f_gender", "f_date",
]


def reset_filters():
    for k in FILTER_KEYS:
        st.session_state.pop(k, None)


st.sidebar.button("Reset filters", on_click=reset_filters, use_container_width=True)

segments = st.sidebar.multiselect(
    "Segment", SEGMENT_ORDER, default=SEGMENT_ORDER, key="f_segment"
)
regions = st.sidebar.multiselect(
    "Region", sorted(df["CustomerRegion"].unique()),
    default=sorted(df["CustomerRegion"].unique()), key="f_region",
)
categories = st.sidebar.multiselect(
    "Category", sorted(df["CategoryGroup"].unique()),
    default=sorted(df["CategoryGroup"].unique()), key="f_category",
)
channels = st.sidebar.multiselect(
    "Channel", sorted(df["RetailChannel"].unique()),
    default=sorted(df["RetailChannel"].unique()), key="f_channel",
)
age_groups = st.sidebar.multiselect(
    "Age group", sorted(df["CustomerAgeGroup"].unique()),
    default=sorted(df["CustomerAgeGroup"].unique()), key="f_age",
)
genders = st.sidebar.multiselect(
    "Gender", sorted(df["CustomerGender"].unique()),
    default=sorted(df["CustomerGender"].unique()), key="f_gender",
)

min_date, max_date = df["TransactionDate"].min().date(), df["TransactionDate"].max().date()
date_range = st.sidebar.date_input(
    "Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date,
    key="f_date",
)

mask = (
    df["label"].isin(segments)
    & df["CustomerRegion"].isin(regions)
    & df["CategoryGroup"].isin(categories)
    & df["RetailChannel"].isin(channels)
    & df["CustomerAgeGroup"].isin(age_groups)
    & df["CustomerGender"].isin(genders)
)
# date_input returns a single date until the user has picked both ends of the
# range -- guard against that so the app doesn't crash mid-selection.
if isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = date_range
    mask &= (df["TransactionDate"].dt.date >= start) & (df["TransactionDate"].dt.date <= end)

fdf = df[mask]

# ---------------------------------------------------------------------------
# Header + empty-state guard
# ---------------------------------------------------------------------------
st.title("NovaRetail Customer Intelligence Dashboard")
st.caption(
    "Revenue, segment health, and growth signals across regions, categories, and channels."
)

if fdf.empty:
    st.warning("No transactions match the current filters. Adjust filters in the sidebar.")
    st.stop()

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total revenue", f"${fdf['PurchaseAmount'].sum():,.0f}")
# Median, not mean -- PurchaseAmount is right-skewed (a few large orders pull
# the mean up), so median better represents a "typical" purchase.
k2.metric("Median purchase", f"${fdf['PurchaseAmount'].median():,.0f}")
k3.metric("Customers", f"{fdf['CustomerID'].nunique()}")
k4.metric("Avg satisfaction", f"{fdf['CustomerSatisfaction'].mean():.1f} / 5")
decline_share = 100 * (fdf["label"] == "Decline").mean()
k5.metric("Decline share", f"{decline_share:.0f}%")

st.divider()

# ---------------------------------------------------------------------------
# Row 1: segment revenue + segment customer count
# ---------------------------------------------------------------------------
c1, c2 = st.columns(2)
with c1:
    seg_rev = (
        fdf.groupby("label", as_index=False)["PurchaseAmount"].sum()
        .sort_values("PurchaseAmount", ascending=False)
    )
    fig = px.bar(
        seg_rev, x="label", y="PurchaseAmount", color="label",
        color_discrete_map=SEGMENT_COLORS, title="Revenue by segment",
    )
    fig.update_layout(showlegend=False, xaxis_title=None, yaxis_title="Revenue ($)")
    st.plotly_chart(fig, use_container_width=True)

with c2:
    seg_cust = (
        fdf.groupby("label", as_index=False)["CustomerID"].nunique()
        .rename(columns={"CustomerID": "Customers"})
        .sort_values("Customers", ascending=False)
    )
    fig = px.bar(
        seg_cust, x="label", y="Customers", color="label",
        color_discrete_map=SEGMENT_COLORS, title="Customers by segment",
    )
    fig.update_layout(showlegend=False, xaxis_title=None)
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Row 2: weekly trend + region
# ---------------------------------------------------------------------------
c3, c4 = st.columns(2)
with c3:
    trend = fdf.groupby("Week", as_index=False)["PurchaseAmount"].sum()
    fig = px.line(trend, x="Week", y="PurchaseAmount", markers=True, title="Weekly revenue trend")
    fig.update_layout(yaxis_title="Revenue ($)")
    st.plotly_chart(fig, use_container_width=True)

with c4:
    reg_rev = (
        fdf.groupby("CustomerRegion", as_index=False)["PurchaseAmount"].sum()
        .sort_values("PurchaseAmount", ascending=False)
    )
    fig = px.bar(reg_rev, x="CustomerRegion", y="PurchaseAmount", title="Revenue by region")
    fig.update_layout(xaxis_title=None, yaxis_title="Revenue ($)")
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Row 3: category + channel
# ---------------------------------------------------------------------------
c5, c6 = st.columns(2)
with c5:
    cat_rev = (
        fdf.groupby("CategoryGroup", as_index=False)["PurchaseAmount"].sum()
        .sort_values("PurchaseAmount", ascending=True)
    )
    fig = px.bar(
        cat_rev, x="PurchaseAmount", y="CategoryGroup", orientation="h",
        title="Revenue by category",
    )
    fig.update_layout(yaxis_title=None, xaxis_title="Revenue ($)")
    st.plotly_chart(fig, use_container_width=True)

with c6:
    chan_rev = fdf.groupby("RetailChannel", as_index=False)["PurchaseAmount"].sum()
    fig = px.bar(chan_rev, x="RetailChannel", y="PurchaseAmount", title="Revenue by channel")
    fig.update_layout(xaxis_title=None, yaxis_title="Revenue ($)")
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Early warning: satisfaction by segment
# ---------------------------------------------------------------------------
st.subheader("Early warning: satisfaction by segment")
fig = px.box(
    fdf, x="label", y="CustomerSatisfaction", color="label",
    color_discrete_map=SEGMENT_COLORS,
    category_orders={"label": SEGMENT_ORDER},
)
fig.update_layout(showlegend=False, xaxis_title=None, yaxis_title="Satisfaction (1-5)")
st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Raw data
# ---------------------------------------------------------------------------
with st.expander("View filtered raw data"):
    st.dataframe(fdf.drop(columns=["idx"]), use_container_width=True)
