import json
import requests
import socketio
import threading
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import JSON, UniqueConstraint
import time

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

sio = socketio.Client()

class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    steamid = db.Column(db.String(20), nullable=False)
    market_name = db.Column(db.String(100), nullable=False)
    wear = db.Column(db.Float)
    sale_price = db.Column(db.Float)
    additional_data = db.Column(JSON)

    __table_args__ = (
        UniqueConstraint('steamid', 'market_name', name='unique_steamid_market_name'),
    )

    def __repr__(self):
        return f'<Listing {self.market_name}>'

# Initialize database
with app.app_context():
    db.create_all()

# WebSocket event handlers
@sio.event
def connect():
    print("Connected to the WebSocket server")

@sio.event
def saleFeed(data):
    print(f"Received sale feed data: {data}")
    
    # Forward the data to the /saleFeed endpoint
    response = requests.post('http://0.0.0.0:10000/saleFeed', json=data)
    print(f"Data posted to Flask app: {response.status_code}")

@sio.event
def disconnect():
    print("Disconnected from the WebSocket server")

# Route to handle /saleFeed POST requests
@app.route('/saleFeed', methods=['POST'])
def handle_sale_feed():
    if request.is_json:
        data = request.get_json()
        sales = data.get('sales', [])
        try:
            for sale in sales:
                # Add the new listing, ensuring uniqueness
                new_listing = Listing(
                    steamid=sale.get('steamid'),
                    market_name=sale.get('marketName'),
                    wear=sale.get('wear'),
                    sale_price=sale.get('salePrice'),
                    additional_data=sale 
                )
                db.session.add(new_listing)
            db.session.commit()
            return jsonify({"status": "success"}), 200
        except Exception as e:
            db.session.rollback()
            print(f"Database error: {e}")
            return jsonify({"error": "Failed to process data. It may already exist."}), 500
    else:
        return jsonify({"error": "Request must be JSON"}), 400

# Route to display all listings
@app.route('/', methods=['GET'])
def displayAllData():
    try:
        listings = Listing.query.all()
        result = [{'id': listing.id, 'steamid': listing.steamid, 'market_name': listing.market_name, 'wear': listing.wear, 'sale_price': listing.sale_price, 'additional_data': listing.additional_data} for listing in listings]
        return jsonify(result), 200
    except Exception as e:
        print(f"Error retrieving data: {e}")
        return jsonify({"error": "Failed to retrieve data"}), 500

# Function to delete all listings every 2 minutes
def delete_data_every_2_minutes():
    while True:
        time.sleep(120)  # 120 seconds = 2 minutes
        with app.app_context():
            try:
                db.session.query(Listing).delete()
                db.session.commit()
                print("All data deleted from database.")
            except Exception as e:
                db.session.rollback()
                print(f"Error deleting data: {e}")

# Start the WebSocket client and connect
def run_websocket_client():
    try:
        sio.connect('https://skinport.com', transports=['websocket'])  # Replace with your WebSocket URL
        sio.emit('saleFeedJoin', {'currency': 'EUR', 'locale': 'en', 'appid': 730})
    except Exception as e:
        print(f"WebSocket error: {e}")

if __name__ == "__main__":
    websocket_thread = threading.Thread(target=run_websocket_client)
    websocket_thread.start()

    # Start the periodic data deletion in a separate thread
    deletion_thread = threading.Thread(target=delete_data_every_2_minutes)
    deletion_thread.start()

    app.run(debug=True)
