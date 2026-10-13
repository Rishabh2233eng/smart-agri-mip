# SmartAgri Market Intelligence Platform

Final-year capstone (B.Tech CSE, IILM University). Helps farmers decide where and when to sell, using real mandi prices and forecasts that come with honest uncertainty ranges.

## What works today
- Live price lookup for any crop and market from the government daily mandi feed (data.gov.in / Agmarknet)
- SQLite database and daily collector that builds our own price history
- Data-quality check that flags suspicious quotes
- Streamlit dashboard
- Forecast and decision engine: conformal prediction intervals, cost- and risk-aware choice of market and sell day. Currently evaluated on a labelled simulation.

## Status
The government feed only serves the current day. Real multi-year history is being added from downloadable Agmarknet datasets (case study: Delhi-NCR). Until then the forecast results come from a simulation and are NOT real-data results.

## Run
    python -m pip install -r requirements.txt
    # put DATAGOV_API_KEY=your_key in a .env file (never commit it)
    python live_demo.py              # live price lookup
    python -m streamlit run app.py   # dashboard
    python run_demo.py               # forecasting + decisions on the simulation
    python data_tools.py snapshot    # save today's prices to the database
