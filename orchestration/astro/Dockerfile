FROM astrocrpublic.azurecr.io/runtime:3.3-9

ARG CODE_REVISION=unknown
ENV BLUEBIKES_CODE_REVISION=${CODE_REVISION}

COPY --from=dbt_project --chown=astro:0 requirements.txt /tmp/dbt-requirements.txt
RUN python -m venv /usr/local/airflow/dbt-venv && /usr/local/airflow/dbt-venv/bin/pip install --no-cache-dir -r /tmp/dbt-requirements.txt

COPY --chown=astro:0 ingestion /usr/local/airflow/ingestion
COPY --chown=astro:0 warehouse /usr/local/airflow/warehouse
COPY --from=dbt_project --chown=astro:0 . /usr/local/airflow/dbt
