# MTA Transit App

A simple Flask app that connects to the MTA GTFS real-time feed and returns subway status data.

## 🚀 Setup Instructions

1. Install dependencies:
```
pip install -r requirements.txt
```

2. Replace `YOUR_MTA_API_KEY` in `feed_parser.py` with your real API key from [MTA API Portal](https://api.mta.info).

3. Run the app:
```
python app.py
```

4. Visit:
```
http://127.0.0.1:5000/status
```

You’ll see live subway trip updates in JSON format!
