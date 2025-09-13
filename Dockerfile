
# Simple Dockerfile for running the Streamlit app
FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir streamlit pandas plotly python-pptx
EXPOSE 8501
CMD ["streamlit", "run", "/mnt/data/marketing_dashboard_enhanced.py", "--server.port=8501", "--server.address=0.0.0.0"]
