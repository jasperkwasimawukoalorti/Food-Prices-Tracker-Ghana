# What Moves the Price of Food — West Africa 🌾

Food-security analytics capstone: fusing WFP food-price, Open-Meteo weather, and World
Bank CPI data into one region×month mart to explain — and forecast — staple cereal and
tuber price swings (maize, rice, sorghum, cassava, millet, yam) in Techiman Municipal,
Ghana, with a live Streamlit dashboard.

> **Scope note:** the current model and charts are trained on a blended index of 8
> staples in Techiman Municipal, not maize in Kumasi alone. Labels throughout this repo
> reflect that. See "Next steps" below if you want to narrow this to maize-only, Kumasi-only.

## Live demo

Once deployed on [Streamlit Community Cloud](https://streamlit.io/cloud), add the link here:

`https://<your-app-name>.streamlit.app`

## What's in this repo

| Path | Description |
|---|---|
| `streamlit_app.py` | The dashboard app — price trends, weather, and the forecast (model vs. baseline) |
| `food_security_integration.ipynb` | Full analysis: DuckDB joins, window functions, model training, evaluation |
| `requirements.txt` | Python dependencies |
| `data/wfp_food_prices_gha.csv` | Raw WFP food price data for Ghana |
| `*.pkl` | Cached dataframes/model outputs the app loads at runtime (`staple_analysis_df`, `predict_df`, `y_test`, `predictions`, `baseline_predictions`) |
| `assets/` | Exported chart images used in the presentation |

## Method

1. **Load & QA** — WFP prices, Open-Meteo weather, World Bank CPI loaded into DuckDB; checked for duplicate/null keys.
2. **Transform in SQL** — monthly weather aggregation, a joined region×month mart, and window functions (month-over-month % change, rolling 3-month average).
3. **Analyse** — real staple prices in Techiman plotted against temperature and precipitation.
4. **Predict** — a lagged-price + weather model forecasts next-month staple price and is compared against a naive "previous month" baseline.
5. **Dashboard** — a 2×2 panel (and a Streamlit app) combining the above into one view.

## Key result

| | MSE |
|---|---|
| Model (lagged price + weather) | **249.19** |
| Baseline (previous month's price) | 335.50 |

The model cuts forecast error by roughly a quarter versus the naive baseline.

## Run locally

```bash
git clone <your-repo-url>
cd <your-repo-name>
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Deploy on Streamlit Community Cloud

1. Push this repo to GitHub (see below).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub.
3. **New app** → pick this repo, branch `main`, main file path `streamlit_app.py`.
4. Deploy. The `.pkl` files and `requirements.txt` in this repo are all it needs.

## Author

Jasper Kwasi Mawuko Alorti — Thrive Africa MLOps Internship 2026
