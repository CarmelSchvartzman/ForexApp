# Como usarla?:
# pip install flask yfinance ta plotly xlsxwriter
# python forex_flask.py


# Como browse?:
# Running on http://127.0.0.1:5000




from flask import Flask, render_template_string, send_file
import yfinance as yf
import ta
import plotly.graph_objs as go
import plotly.offline as pyo
import pandas as pd
import io
from ta.volatility import BollingerBands
from ta.momentum import StochasticOscillator
from ta.volume import OnBalanceVolumeIndicator
from ta.trend import IchimokuIndicator


app = Flask(__name__)


import logging

# In your app.py or equivalent file
import os

# ... your app setup ...

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000)) # Use environment PORT or default
    app.run(host='0.0.0.0', port=port)



def get_forex_data(symbol="EURUSD=X", period="180d", interval="1d"):
    """Fetch and prepare forex data with indicators"""
    try:
        data = yf.download(symbol, period=period, interval=interval)

        if data.empty:
            raise ValueError("No data fetched from Yahoo Finance")

        # --- Flatten MultiIndex columns ---
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [col[0] for col in data.columns]

        # Ensure standard naming
        rename_map = {
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume"
        }
        data.rename(columns={c: rename_map.get(c.lower(), c) for c in data.columns}, inplace=True)

        df = data.copy()

        # Bollinger Bands
        bb = ta.volatility.BollingerBands(close=df["Close"])
        df["BB_MIDDLE"] = bb.bollinger_mavg().squeeze()
        df["BB_UPPER"] = bb.bollinger_hband().squeeze()
        df["BB_LOWER"] = bb.bollinger_lband().squeeze()

        # Stochastic Oscillator
        stoch = ta.momentum.StochasticOscillator(
            high=df["High"], low=df["Low"], close=df["Close"]
        )
        df["STOCH_K"] = stoch.stoch().squeeze()
        df["STOCH_D"] = stoch.stoch_signal().squeeze()

        # On-Balance Volume (OBV)
        df["OBV"] = ta.volume.OnBalanceVolumeIndicator(
            close=df["Close"], volume=df["Volume"]
        ).on_balance_volume().squeeze()

        # Ichimoku Cloud
        ichimoku = ta.trend.IchimokuIndicator(
            high=df["High"], low=df["Low"], window1=9, window2=26, window3=52
        )
        df["ICH_A"] = ichimoku.ichimoku_a().squeeze()
        df["ICH_B"] = ichimoku.ichimoku_b().squeeze()
        df["ICH_BASE"] = ichimoku.ichimoku_base_line().squeeze()
        df["ICH_CONV"] = ichimoku.ichimoku_conversion_line().squeeze()

        df.dropna(inplace=True)
        return df

    except Exception as e:
        logging.error("Error fetching or processing forex data", exc_info=True)
        return pd.DataFrame()





def generate_signals(df):
    signals = []
    for i in range(len(df)):
        row = df.iloc[i]
        signal = None

        # Bollinger breakout
        if row["Close"] > row["BB_UPPER"]:
            signal = "SELL (Bollinger breakout)"
        elif row["Close"] < row["BB_LOWER"]:
            signal = "BUY (Bollinger rebound)"

        # Stochastic crossover
        if row["STOCH_K"] > row["STOCH_D"]:
            signal = "BUY (Stochastic)"
        elif row["STOCH_K"] < row["STOCH_D"]:
            signal = "SELL (Stochastic)"

        # Ichimoku confirmation
        if row["Close"] > row["ICH_BASE"]:
            signal = "BUY (Ichimoku trend)"
        elif row["Close"] < row["ICH_BASE"]:
            signal = "SELL (Ichimoku trend)"

        if signal:
            signals.append((df.index[i].strftime("%Y-%m-%d"), row["Close"], signal))

    return signals[-50:]  # keep last 50 for export


def generate_price_chart(df):
    fig = go.Figure()

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        name="Candlestick"
    ))

    # Bollinger Bands
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_UPPER"], line=dict(color='rgba(200,0,0,0.5)'), name="BB Upper"))
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_MIDDLE"], line=dict(color='rgba(0,0,200,0.5)'), name="BB Middle"))
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_LOWER"], line=dict(color='rgba(200,0,0,0.5)'), name="BB Lower"))

    # Ichimoku Cloud
    fig.add_trace(go.Scatter(x=df.index, y=df["ICH_A"], line=dict(color="green"), name="Span A"))
    fig.add_trace(go.Scatter(x=df.index, y=df["ICH_B"], line=dict(color="red"), name="Span B",
                             fill='tonexty', fillcolor='rgba(200,200,200,0.2)'))

    fig.update_layout(
        title="EUR/USD Price with Bollinger Bands & Ichimoku",
        xaxis_title="Date", yaxis_title="Price",
        template="plotly_white", xaxis_rangeslider_visible=False, height=700
    )

    return pyo.plot(fig, output_type="div")


def generate_stochastic_chart(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["STOCH_K"], line=dict(color="blue"), name="%K"))
    fig.add_trace(go.Scatter(x=df.index, y=df["STOCH_D"], line=dict(color="orange"), name="%D"))

    fig.update_layout(
        title="Stochastic Oscillator",
        xaxis_title="Date", yaxis_title="Value",
        template="plotly_white", height=400
    )
    return pyo.plot(fig, output_type="div")


def generate_obv_chart(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["OBV"], line=dict(color="purple"), name="OBV"))

    fig.update_layout(
        title="On-Balance Volume (OBV)",
        xaxis_title="Date", yaxis_title="OBV",
        template="plotly_white", height=400
    )
    return pyo.plot(fig, output_type="div")



def interpret_trend(df):
    """Generate color-coded summary of current trend using Ichimoku and Bollinger Bands."""
    try:
        last = df.iloc[-1]
        messages = []
        color = "black"  # default
        
        print(" interpret_trend:start", df.columns )

        # === Ichimoku analysis ===
        if 'ICH_A' in df.columns and 'ICH_B' in df.columns:
            if last["Close"] > max(last['ICH_A'], last['ICH_B']):
                ich_text = "Bullish (price above Ichimoku cloud)"
                color = "green"
            elif last["Close"] < min(last['ICH_A'], last['ICH_B']):
                ich_text = "Bearish (price below Ichimoku cloud)"
                color = "red"
            else:
                ich_text = "Neutral (price inside Ichimoku cloud)"
                color = "orange"
            messages.append(ich_text)

        # === Bollinger Band analysis ===
        if "BB_UPPER" in df.columns and "BB_LOWER" in df.columns and "BB_MIDDLE" in df.columns:
            if last["Close"] > last["BB_UPPER"]:
                bb_text = "Overbought (above upper Bollinger Band)"
            elif last["Close"] < last["BB_LOWER"]:
                bb_text = "Oversold (below lower Bollinger Band)"
            else:
                bb_text = "Stable (within Bollinger range)"
            messages.append(bb_text)

        # Final color-coded output
        summary = " | ".join(messages)
        
        print(" interpret_trend:end" )
        
        
        return {"text": summary, "color": color}

    except Exception as e:
        print("Error interpreting trend:", e)
        return {"text": "No trend interpretation available.", "color": "black"}




@app.route("/")
def index():
    df = get_forex_data()
    signals = generate_signals(df)
    price_chart = generate_price_chart(df)
    stochastic_chart = generate_stochastic_chart(df)
    obv_chart = generate_obv_chart(df)

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Forex Dashboard - EUR/USD</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f4f4f9; }
            h1 { color: #333; }
            .tabs { overflow: hidden; background: #ddd; }
            .tabs button { background: #ccc; float: left; border: none; outline: none; cursor: pointer; padding: 12px 20px; transition: 0.3s; }
            .tabs button:hover { background: #bbb; }
            .tabs button.active { background: #999; color: white; }
            .tabcontent { display: none; padding: 20px; background: white; }
            table { border-collapse: collapse; width: 90%; margin-top: 20px; background: white; }
            th, td { border: 1px solid #ccc; padding: 8px; text-align: center; }
            th { background: #eee; }
            tr:nth-child(even) { background: #f9f9f9; }
            .download-btn { margin-top: 15px; padding: 10px; background: #4CAF50; color: white; border: none; cursor: pointer; }
            .download-btn:hover { background: #45a049; }
        </style>
        <script>
            function openTab(evt, tabName) {
                var i, tabcontent, tablinks;
                tabcontent = document.getElementsByClassName("tabcontent");
                for (i = 0; i < tabcontent.length; i++) { tabcontent[i].style.display = "none"; }
                tablinks = document.getElementsByTagName("button");
                for (i = 0; i < tablinks.length; i++) { tablinks[i].className = tablinks[i].className.replace(" active", ""); }
                document.getElementById(tabName).style.display = "block";
                evt.currentTarget.className += " active";
            }
        </script>
    </head>
    <body>
        
    
        <h1>Forex Predictor Dashboard - EUR/USD (180 days)</h1>
       

        <div class="tabs">
       
            <button onclick="openTab(event, 'Price')" class="active">📈 Price + Indicators</button>
            <button onclick="openTab(event, 'Stochastic')">📊 Stochastic</button>
            <button onclick="openTab(event, 'OBV')">📊 OBV</button>
            <button onclick="openTab(event, 'Signals')">📌 Signals</button>
        </div>

        <div id="Price" class="tabcontent" style="display:block;">
        <h3 style="color: {{ trend_summary.color }}; font-weight: bold;">
        Prediction : {{ trend_summary.text }}
        </h3>

            {{ price_chart|safe }}
        </div>

        <div id="Stochastic" class="tabcontent">
         <h3 style="color: {{ trend_summary.color }}; font-weight: bold;">
        Prediction : {{ trend_summary.text }}
        </h3>
            {{ stochastic_chart|safe }}
        </div>

        <div id="OBV" class="tabcontent">
         <h3 style="color: {{ trend_summary.color }}; font-weight: bold;">
        Prediction : {{ trend_summary.text }}
        </h3>
            {{ obv_chart|safe }}
        </div>

        <div id="Signals" class="tabcontent">
         <h3 style="color: {{ trend_summary.color }}; font-weight: bold;">
        Prediction : {{ trend_summary.text }}
        </h3>
        </h3>
            <h3>Latest Trading Signals</h3>
            <table>
                <tr><th>Date</th><th>Close Price</th><th>Signal</th></tr>
                {% for date, price, signal in signals %}
                <tr>
                    <td>{{ date }}</td>
                    <td>{{ "%.4f"|format(price) }}</td>
                    <td>{{ signal }}</td>
                </tr>
                {% endfor %}
            </table>
            <br>
            <a href="/download/csv"><button class="download-btn">⬇ Download CSV</button></a>
            <a href="/download/excel"><button class="download-btn">⬇ Download Excel</button></a>
        </div>
       <h4 style="color: {{ trend_summary.color }}; font-weight: bold;">
        Powered by CarmelSoft 
        </h4>
    </body>
    </html>
    """
    # return render_template_string(html, signals=signals,
                                  # price_chart=price_chart,
                                  # stochastic_chart=stochastic_chart,
                                  # obv_chart=obv_chart)

    trend_summary = interpret_trend(df)
    #return render_template("index.html", chart=price_chart, signals=signals, trend_summary=trend_summary)
    return render_template_string(html, signals=signals,
                                    price_chart=price_chart,
                                    stochastic_chart=stochastic_chart,
                                    obv_chart=obv_chart, trend_summary=trend_summary)
                                    
                                    

@app.route("/download/csv")
def download_csv():
    df = get_forex_data()
    signals = generate_signals(df)
    df_out = pd.DataFrame(signals, columns=["Date", "Close", "Signal"])

    output = io.StringIO()
    df_out.to_csv(output, index=False)
    output.seek(0)

    return send_file(io.BytesIO(output.getvalue().encode()),
                     mimetype="text/csv",
                     as_attachment=True,
                     download_name="forex_signals.csv")


@app.route("/download/excel")
def download_excel():
    df = get_forex_data()
    signals = generate_signals(df)
    df_out = pd.DataFrame(signals, columns=["Date", "Close", "Signal"])

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_out.to_excel(writer, index=False, sheet_name="Signals")
    output.seek(0)

    return send_file(output,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True,
                     download_name="forex_signals.xlsx")


if __name__ == "__main__":
    app.run(debug=True)
