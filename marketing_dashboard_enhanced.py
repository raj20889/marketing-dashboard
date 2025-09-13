import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import os
from datetime import timedelta

st.set_page_config(layout="wide", page_title="Marketing Intelligence Dashboard (Enhanced)")

# ---------------- Helper for environment-agnostic file paths ----------------
def local_path(filename):
    """Try /mnt/data first (local), else current folder (Streamlit Cloud)."""
    if os.path.exists(os.path.join("/mnt/data", filename)):
        return os.path.join("/mnt/data", filename)
    else:
        return filename

# ---------------- Load data ----------------
@st.cache_data
def load_data():
    marketing = pd.read_csv(local_path("marketing_cleaned_raw.csv"), parse_dates=['date'])
    daily_totals = pd.read_csv(local_path("daily_totals.csv"), parse_dates=['date'])
    daily_merged = pd.read_csv(local_path("daily_merged_business_marketing.csv"), parse_dates=['date'])
    return marketing, daily_totals, daily_merged

marketing, daily_totals, daily_merged = load_data()

# ---------------- Sidebar & Filters ----------------
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Overview", "Diagnostics & Lag Analysis", "Cohort & Acquisition", "Export & Report"])

min_date = marketing['date'].min().date()
max_date = marketing['date'].max().date()
date_range = st.sidebar.date_input("Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date)

channels = sorted(marketing['channel'].unique())
selected_channels = st.sidebar.multiselect("Channels", channels, default=channels)

state_filter = st.sidebar.text_input("State (optional)")

start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])

mkt = marketing[
    (marketing['date'] >= start_date) &
    (marketing['date'] <= end_date) &
    (marketing['channel'].isin(selected_channels))
].copy()

dm = daily_merged[(daily_merged['date'] >= start_date) & (daily_merged['date'] <= end_date)].copy()

if state_filter.strip():
    mkt = mkt[mkt['state'] == state_filter.strip()]

# ---------------- KPI calculation ----------------
def calc_kpis(df):
    s = df['spend'].sum()
    r = df['attributed_revenue'].sum()
    return s, r, (r / s if s > 0 else np.nan)

# ---------------- Pages ----------------
if page == "Overview":
    st.title("Overview — KPIs & Trends")
    
    total_spend, total_attr_rev, overall_roas = calc_kpis(mkt)
    total_business_rev = dm['total_revenue'].sum() if 'total_revenue' in dm.columns else np.nan
    total_gross_profit = dm['gross_profit'].sum() if 'gross_profit' in dm.columns else np.nan

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Ad Spend", f"₹ {total_spend:,.0f}")
    col2.metric("Total Attributed Rev", f"₹ {total_attr_rev:,.0f}")
    col3.metric("Business Revenue", f"₹ {total_business_rev:,.0f}" if not np.isnan(total_business_rev) else "N/A")
    col4.metric("Gross Profit", f"₹ {total_gross_profit:,.0f}" if not np.isnan(total_gross_profit) else "N/A")
    col5.metric("Overall ROAS", f"{overall_roas:.2f}" if not np.isnan(overall_roas) else "N/A")

    st.markdown("---")
    st.subheader("Spend by Channel (stacked)")
    ts_spend = mkt.groupby(['date','channel']).spend.sum().reset_index()
    spend_pivot = ts_spend.pivot(index='date', columns='channel', values='spend').fillna(0).reset_index()
    fig = px.area(spend_pivot, x='date', y=[c for c in spend_pivot.columns if c != 'date'], title='Daily Ad Spend by Channel (stacked)')
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Revenue vs Spend (7-day rolling)")
    rev_ts = dm[['date','total_revenue']].groupby('date').sum().reset_index()
    rev_ts['rev_7d'] = rev_ts['total_revenue'].rolling(7, min_periods=1).mean()
    spend_total = ts_spend.groupby('date').spend.sum().reset_index().rename(columns={'spend':'total_spend'})
    spend_total['spend_7d'] = spend_total['total_spend'].rolling(7, min_periods=1).mean()
    df_join = rev_ts.merge(spend_total, on='date', how='left').fillna(0)
    fig2 = px.line(df_join, x='date', y=['rev_7d','spend_7d'], labels={'value':'Amount','variable':'Metric'}, title='7-day rolling: Revenue vs Spend')
    st.plotly_chart(fig2, use_container_width=True)

elif page == "Diagnostics & Lag Analysis":
    st.title("Diagnostics & Lag Analysis")
    st.markdown("This section estimates how ad spend leads or lags business orders (cross-correlation).")

    orders = dm[['date']].copy()
    order_cols = [c for c in dm.columns if 'order' in c.lower() or 'orders' in c.lower()]
    if order_cols:
        orders['orders'] = dm[order_cols[0]].values
    else:
        orders['orders'] = 0
    st.write('Using orders column:', order_cols[0] if order_cols else 'None found')

    max_lag = st.slider('Max lag days (both directions)', 0, 30, 14)
    results = []

    for ch in selected_channels:
        srs = mkt[mkt['channel'] == ch].groupby('date').spend.sum().reindex(pd.date_range(start_date, end_date), fill_value=0)
        ords = orders.set_index('date').reindex(pd.date_range(start_date, end_date), fill_value=0)['orders']
        lags = list(range(-max_lag, max_lag+1))
        cors = []

        for lag in lags:
            if lag < 0:
                val = np.corrcoef(srs.shift(-lag).fillna(0), ords.fillna(0))[0,1]
            else:
                val = np.corrcoef(srs.fillna(0), ords.shift(lag).fillna(0))[0,1]
            cors.append(val)

        best_lag = lags[np.nanargmax(np.nan_to_num(cors, nan=-999))]
        results.append({'channel': ch, 'best_lag_days': best_lag, 'max_corr': np.nanmax(cors)})

        st.subheader(f'Channel: {ch} — correlation by lag')
        dfc = pd.DataFrame({'lag': lags, 'corr': cors})
        st.line_chart(dfc.set_index('lag')['corr'], height=250)

    st.table(pd.DataFrame(results))

elif page == "Cohort & Acquisition":
    st.title("Cohort & Acquisition Attribution (proportional)")
    st.markdown("We attribute daily new customers to channels proportionally based on that day's attributed_revenue by channel.")

    if 'new_customers' not in dm.columns:
        st.error('No new_customers column found in business data.')
    else:
        rev_by_ch = mkt.groupby(['date','channel']).attributed_revenue.sum().reset_index()
        total_rev_by_date = rev_by_ch.groupby('date').attributed_revenue.sum().reset_index().rename(columns={'attributed_revenue':'total_rev'})
        merged = rev_by_ch.merge(total_rev_by_date, on='date', how='left')
        merged['rev_share'] = merged['attributed_revenue'] / merged['total_rev']

        cust = dm[['date','new_customers']].copy()
        merged = merged.merge(cust, on='date', how='left').fillna(0)
        merged['new_customers_attrib'] = merged['rev_share'] * merged['new_customers']

        cohort = merged.groupby('channel').agg(total_new_customers_attr=('new_customers_attrib','sum')).reset_index().sort_values('total_new_customers_attr', ascending=False)
        st.table(cohort.round(1))

        st.markdown('Top daily-channel breakdown (sample)')
        st.dataframe(merged.sort_values(['date','rev_share'], ascending=[False,False]).head(50))

elif page == "Export & Report":
    st.title("Export & Report")
    st.markdown("Download datasets and a summary slide deck for stakeholders.")

    if st.button('Download channel-level KPIs CSV'):
        df = mkt.groupby('channel').agg(
            impressions=('impressions','sum'),
            clicks=('clicks','sum'),
            spend=('spend','sum'),
            attributed_revenue=('attributed_revenue','sum')
        ).reset_index()
        st.download_button('Download KPIs', data=df.to_csv(index=False).encode('utf-8'), file_name='channel_kpis_export.csv')

    st.markdown('Download a short slide deck summarizing top-level findings.')
    pptx_path = local_path("marketing_summary_slides.pptx")
    if os.path.exists(pptx_path):
        with open(pptx_path,'rb') as f:
            st.download_button('Download Slides', f.read(), file_name='marketing_summary_slides.pptx')
    else:
        st.warning("marketing_summary_slides.pptx not found. Please upload it.")
