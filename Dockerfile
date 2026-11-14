FROM python:3.14-slim

# Set environment variables for clean Python execution
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860

WORKDIR /app

# Install minimal system runtime libraries for rasterio / HDF5 wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    libexpat1 \
    libgomp1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies from binary wheels
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy backend code, compiled React SPA (frontend/dist), and runtime data
COPY src /app/src
COPY frontend/dist /app/frontend/dist
COPY data/phase0_audit_results.json /app/data/phase0_audit_results.json
COPY data/web_tiles /app/data/web_tiles
COPY data/processed/fayoum_gcov_10dates_40m_filtered.h5 /app/data/processed/fayoum_gcov_10dates_40m_filtered.h5
COPY data/processed/phase2_processing_report.json /app/data/processed/phase2_processing_report.json
COPY data/processed/phase3_change_and_timeseries_report.json /app/data/processed/phase3_change_and_timeseries_report.json
COPY data/processed/phase4_cog_and_tile_report.json /app/data/processed/phase4_cog_and_tile_report.json
COPY data/processed/sar_water_benchmark_report.json /app/data/processed/sar_water_benchmark_report.json
COPY data/processed/gunw_coherence/coherence_9pair_manifest.json /app/data/processed/gunw_coherence/coherence_9pair_manifest.json

# Hugging Face Spaces runs as user 1000 on port 7860
RUN chmod -R a+rX /app

EXPOSE 7860

CMD ["uvicorn", "src.nisar_pipeline.api_server:app", "--host", "0.0.0.0", "--port", "7860"]
