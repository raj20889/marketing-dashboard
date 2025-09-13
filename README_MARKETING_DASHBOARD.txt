
Marketing Intelligence Dashboard — Prototype (Streamlit)

Files included:
- marketing_cleaned_raw.csv
- daily_channel.csv
- daily_channel_pivot.csv
- daily_totals.csv
- daily_merged_business_marketing.csv
- channel_level_kpis.csv
- marketing_dashboard_app.py  <-- this Streamlit app

How to run locally:
1. Install dependencies:
   pip install streamlit pandas plotly
2. Run the app:
   streamlit run /mnt/data/marketing_dashboard_app.py
3. Open the browser URL shown by Streamlit (usually http://localhost:8501).

Notes & assumptions:
- The app reads cleaned CSVs saved in /mnt/data. If you regenerate cleaned artifacts, the app will reflect updates.
- Attribution uses the provided 'attributed_revenue' fields in channel datasets.
- If you want additional charts (lag analysis, cohort analysis, conversion funnels), tell me and I will add them.
