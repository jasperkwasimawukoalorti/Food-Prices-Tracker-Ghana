
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import pickle
from sklearn.metrics import mean_squared_error

st.set_page_config(layout="wide")

st.title('Food Price Analysis Dashboard: West Africa')
st.write('Insights into Staple Cereals & Tubers Prices, Weather, and Forecast — Techiman Municipal, Ghana')
st.caption('Blended index across 8 staples (maize, rice, sorghum, cassava, millet, yam) tracked in this market — not a single-commodity series.')

# Load the dataframes
@st.cache_data
def load_data():
    with open('staple_analysis_df.pkl', 'rb') as f:
        staple_analysis_df = pickle.load(f)
    with open('predict_df.pkl', 'rb') as f:
        predict_df = pickle.load(f)
    with open('y_test.pkl', 'rb') as f:
        y_test = pickle.load(f)
    with open('predictions.pkl', 'rb') as f:
        predictions = pickle.load(f)
    with open('baseline_predictions.pkl', 'rb') as f:
        baseline_predictions = pickle.load(f)
    return staple_analysis_df, predict_df, y_test, predictions, baseline_predictions

staple_analysis_df, predict_df, y_test, predictions, baseline_predictions = load_data()

# Ensure 'month' column is datetime type for plotting
staple_analysis_df['month'] = pd.to_datetime(staple_analysis_df['month'])
predict_df['month'] = pd.to_datetime(predict_df['month'])

# Dashboard Layout
col1, col2 = st.columns(2)

with col1:
    st.subheader('Staple Cereals & Tubers: Real Price and Rolling Average')
    fig1, ax1 = plt.subplots(figsize=(10, 6))
    ax1.plot(staple_analysis_df['month'], staple_analysis_df['real_price'], label='Real Price', color='blue')
    ax1.plot(staple_analysis_df['month'], staple_analysis_df['rolling_3m_avg_real_price'], label='Rolling 3-Month Avg', color='green', linestyle='--')
    ax1.set_title('Real Price (Staple Cereals & Tubers, Techiman Municipal)', fontsize=10)
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Real Price (GHS)')
    ax1.legend()
    ax1.grid(True)
    plt.xticks(rotation=45)
    st.pyplot(fig1)

    st.subheader('Monthly Precipitation Sum')
    fig3, ax3 = plt.subplots(figsize=(10, 6))
    ax3.plot(staple_analysis_df['month'], staple_analysis_df['monthly_precipitation_sum'], label='Monthly Precipitation Sum (mm)', color='purple')
    ax3.set_xlabel('Date')
    ax3.set_ylabel('Precipitation (mm)')
    ax3.legend()
    ax3.grid(True)
    plt.xticks(rotation=45)
    st.pyplot(fig3)

with col2:
    st.subheader('Monthly Average Temperature')
    fig2, ax2 = plt.subplots(figsize=(10, 6))
    ax2.plot(staple_analysis_df['month'], staple_analysis_df['monthly_avg_temperature'], label='Monthly Avg Temperature (°C)', color='red')
    ax2.set_xlabel('Date')
    ax2.set_ylabel('Temperature (°C)')
    ax2.legend()
    ax2.grid(True)
    plt.xticks(rotation=45)
    st.pyplot(fig2)

    st.subheader('Staple Cereals & Tubers: Price Forecast')
    fig4, ax4 = plt.subplots(figsize=(10, 6))
    # The split_date_idx is needed to correctly plot the X-axis for predictions
    # Recalculate it or pass it. For simplicity, we'll re-slice based on index for the plot.
    split_date_idx = len(predict_df) - len(y_test) # Assuming y_test corresponds to the end of predict_df
    ax4.plot(predict_df['month'].iloc[split_date_idx:], y_test, label='Actual Real Price', color='blue')
    ax4.plot(predict_df['month'].iloc[split_date_idx:], predictions, label='Model Predictions', color='red', linestyle='--')
    ax4.plot(predict_df['month'].iloc[split_date_idx:], baseline_predictions, label='Baseline Predictions', color='green', linestyle=':')
    ax4.set_title('Staple Cereals & Tubers Forecast — Techiman Municipal: Model vs Baseline', fontsize=10)
    ax4.set_xlabel('Date')
    ax4.set_ylabel('Real Price (GHS)')
    ax4.legend()
    ax4.grid(True)
    plt.xticks(rotation=45)
    st.pyplot(fig4)

    # Show how much better the model is than the naive baseline
    model_mse = mean_squared_error(y_test, predictions)
    baseline_mse = mean_squared_error(y_test, baseline_predictions)
    improvement_pct = (baseline_mse - model_mse) / baseline_mse * 100

    m1, m2, m3 = st.columns(3)
    m1.metric('Model MSE', f'{model_mse:.2f}')
    m2.metric('Baseline MSE', f'{baseline_mse:.2f}')
    m3.metric('Improvement', f'{improvement_pct:.0f}% lower error')
    st.caption('Model MSE vs. a naive baseline that simply predicts next month\'s price as this month\'s price.')

st.subheader('Recommendation')
st.write("The analysis of staple cereal and tuber prices (maize, rice, sorghum, cassava, millet, and yam) in Techiman Municipal reveals a strong correlation with seasonal weather patterns, particularly average monthly temperature. The predictive model, incorporating lagged prices and weather data, outperforms a simple baseline, indicating that these factors are significant drivers of price fluctuations. To mitigate food security risks, we recommend continuous monitoring of temperature and precipitation forecasts, especially during critical growing seasons, and implementing strategies such as strategic grain reserves or diversified agricultural practices to buffer against weather-induced price volatility. Further investigation into specific market-level interventions, and into disaggregating this analysis by individual staple, based on these insights is warranted.")
