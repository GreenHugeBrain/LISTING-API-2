import json
import threading
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import JSON, UniqueConstraint
from flask_cors import CORS
import time

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
CORS(app)

# Define your Listing model with a unique constraint for steamid and market_name
class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    steamid = db.Column(db.String(20), nullable=False)
    market_name = db.Column(db.String(100), nullable=False)
    wear = db.Column(db.Float)
    sale_price = db.Column(db.Float)
    additional_data = db.Column(JSON)  # JSON column for additional data

    __table_args__ = (
        UniqueConstraint('steamid', 'market_name', name='unique_steamid_market_name'),
    )

    def __repr__(self):
        return f'<Listing {self.market_name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'steamid': self.steamid,
            'market_name': self.market_name,
            'wear': self.wear,
            'sale_price': self.sale_price,
            'additional_data': self.additional_data
        }

# Initialize database
with app.app_context():
    db.create_all()

@app.route('/', methods=['GET'])
def home():
    listings = Listing.query.all()
    return jsonify([listing.to_dict() for listing in listings])

# Route to handle /receiveSaleFeed POST requests from the first Flask app
@app.route('/receiveSaleFeed', methods=['POST'])
def receive_sale_feed():
    if request.is_json:
        data = request.get_json()
        sales = data.get('sales', [])
        try:
            for sale in sales:
                # Check for existing record
                existing_listing = Listing.query.filter_by(
                    steamid=sale.get('steamid'),
                    market_name=sale.get('marketName')
                ).first()

                if not existing_listing:
                    # Add the new listing
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
            print(f"Error processing data: {e}")
            return jsonify({"error": "Failed to process data"}), 500
    else:
        return jsonify({"error": "Request must be JSON"}), 400

# Function to delete all listings every 2 minutes
def delete_data_every_2_minutes():
    while True:
        time.sleep(1222120)  # 120 seconds = 2 minutes
        with app.app_context():
            try:
                db.session.query(Listing).delete()
                db.session.commit()
                print("All data deleted from database.")
            except Exception as e:
                db.session.rollback()
                print(f"Error deleting data: {e}")

if __name__ == "__main__":
    # Start the periodic data deletion in a separate thread
    deletion_thread = threading.Thread(target=delete_data_every_2_minutes)
    deletion_thread.start()

    app.run(port=5001, debug=True)
