PY ?= python

.PHONY: all data pipeline test dashboard screenshot powerbi clean

all: data pipeline test          ## download data, build DB + report, run tests

data:                            ## download the Olist CSVs into data/raw/
	$(PY) data/download_data.py

pipeline:                        ## build DuckDB, run DQ checks, queries, charts, summary
	$(PY) -m src.pipeline

test:                            ## pytest on the hand-made fixture
	$(PY) -m pytest

dashboard:                       ## interactive dashboard on http://localhost:8501
	streamlit run app.py

screenshot:                      ## headless screenshot of the dashboard (Playwright)
	$(PY) scripts/screenshot_dashboard.py

powerbi:                         ## export mart tables as CSV to powerbi/data/
	$(PY) -m src.export_powerbi

clean:
	rm -f data/olist.duckdb
	rm -rf powerbi/data
