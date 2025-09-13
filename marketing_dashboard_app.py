
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import timedelta

st.set_page_config(layout="wide", page_title="Marketing Intelligence Dashboard (Prototype)")

@st.cache_data
def load_data():
    marketing = pd.read_csv("marketing_cleaned_raw.csv", parse_dates=['date'])
    daily_totals = pd.read_csv("daily_totals.csv", parse_dates=['date'])
    daily_merged = pd.read_csv("daily_merged_business_marketing.csv", parse_dates=['date'])
    channel_kpis = pd.read_csv("channel_level_kpis.csv")
    return marketing, daily_totals, daily_merged, channel_kpis

marketing, daily_totals, daily_merged, channel_kpis = load_data()

st.title("Marketing Intelligence Dashboard — Prototype (Overview)")
st.markdown("Interactive prototype: KPI summary, spend vs revenue trends, and channel performance.")

# Sidebar filters
st.sidebar.header("Filters")
min_date = marketing['date'].min().date()
max_date = marketing['date'].max().date()
date_range = st.sidebar.date_input("Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
selected_channels = st.sidebar.multiselect("Channels", options=sorted(marketing['channel'].unique()), default=sorted(marketing['channel'].unique()))
state_filter = st.sidebar.text_input("State filter (optional) — exact match, leave blank for all")

# enforce date_range tuple
if isinstance(date_range, list) or isinstance(date_range, tuple):
    start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
else:
    start_date, end_date = pd.to_datetime(date_range), pd.to_datetime(date_range)

# Filter data
mkt_f = marketing[(marketing['date'] >= start_date) & (marketing['date'] <= end_date) & (marketing['channel'].isin(selected_channels))]
dt_f = daily_totals[(daily_totals['date'] >= start_date) & (daily_totals['date'] <= end_date)]
dm_f = daily_merged[(daily_merged['date'] >= start_date) & (daily_merged['date'] <= end_date)]
if state_filter.strip():
    mkt_f = mkt_f[mkt_f['state'] == state_filter.strip()]

# KPIs row
total_spend = mkt_f['spend'].sum()
total_attr_rev = mkt_f['attributed_revenue'].sum()
total_business_rev = dm_f['total_revenue'].sum() if 'total_revenue' in dm_f.columns else np.nan
total_gross_profit = dm_f['gross_profit'].sum() if 'gross_profit' in dm_f.columns else np.nan
new_customers = dm_f['new_customers'].sum() if 'new_customers' in dm_f.columns else np.nan
overall_roas = (total_attr_rev / total_spend) if total_spend>0 else np.nan
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Ad Spend", f"₹ {total_spend:,.0f}")
col2.metric("Total Attributed Revenue", f"₹ {total_attr_rev:,.0f}", delta=None)
col3.metric("Business Revenue (total)", f"₹ {total_business_rev:,.0f}" if not np.isnan(total_business_rev) else "N/A")
col4.metric("Gross Profit (total)", f"₹ {total_gross_profit:,.0f}" if not np.isnan(total_gross_profit) else "N/A")
col5.metric("Overall ROAS", f"{overall_roas:.2f}" if not np.isnan(overall_roas) else "N/A")

st.markdown("---")

# Time series: Spend (stacked by channel) vs Business Revenue
st.subheader("Spend vs Revenue — time series")
# prepare timeseries data
ts_spend = mkt_f.groupby(['date','channel']).agg({'spend':'sum'}).reset_index()
ts_spend_pivot = ts_spend.pivot(index='date', columns='channel', values='spend').fillna(0)
ts_spend_pivot['total_spend'] = ts_spend_pivot.sum(axis=1)
ts_spend_pivot = ts_spend_pivot.reset_index()
# business revenue series
rev_ts = dm_f[['date','total_revenue']].groupby('date').sum().reset_index()

fig = px.area(ts_spend_pivot, x='date', y=[c for c in ts_spend_pivot.columns if c not in ['date','total_spend']], title="Daily Ad Spend by Channel (stacked)")
fig.update_layout(legend_title_text='Channel', height=350)
st.plotly_chart(fig, use_container_width=True)

fig2 = px.line(rev_ts, x='date', y='total_revenue', title="Daily Business Total Revenue", height=250)
st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# Channel performance table
st.subheader("Channel performance (selected date range)")
channel_table = mkt_f.groupby('channel').agg(
    impressions = ('impressions','sum'),
    clicks = ('clicks','sum'),
    spend = ('spend','sum'),
    attributed_revenue = ('attributed_revenue','sum'),
    campaigns = ('campaign', 'nunique')
).reset_index()
channel_table['ctr'] = channel_table['clicks'] / channel_table['impressions']
channel_table['cpc'] = channel_table['spend'] / channel_table['clicks']
channel_table['roas'] = channel_table['attributed_revenue'] / channel_table['spend']

st.dataframe(channel_table.sort_values('spend', ascending=False).round(3), height=300)

# Top campaigns by ROAS
st.subheader("Top campaigns by ROAS")
camp = mkt_f.groupby(['channel','campaign']).agg(spend=('spend','sum'), attributed_revenue=('attributed_revenue','sum'), impressions=('impressions','sum'), clicks=('clicks','sum')).reset_index()
camp['roas'] = camp['attributed_revenue'] / camp['spend']
top_camp = camp.replace([np.inf, -np.inf], np.nan).dropna(subset=['roas']).sort_values('roas', ascending=False).head(15)
st.dataframe(top_camp.round(3))

st.markdown("---")
st.markdown("**Notes & assumptions:** The dashboard uses `attributed_revenue` from the campaign datasets as the marketing attribution. ROAS = attributed_revenue / spend. CPC and CTR computed from raw fields.")

# Export data
st.sidebar.markdown("### Export")
if st.sidebar.button("Download filtered marketing rows as CSV"):
    st.download_button("Download marketing CSV", data=mkt_f.to_csv(index=False).encode('utf-8'), file_name="marketing_filtered.csv", mime="text/csv")

if st.sidebar.button("Download daily merged business+marketing"):
    st.download_button("Download merged CSV", data=dm_f.to_csv(index=False).encode('utf-8'), file_name="daily_merged_filtered.csv", mime="text/csv")

st.sidebar.markdown("App created as part of an industry-level assignment prototype.")
