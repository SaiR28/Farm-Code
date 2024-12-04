"""
Production-Ready Hydroponic Farm API
----------------------------------
Thoroughly reviewed and corrected version with robust error handling and proper resource management.
"""

from flask import Flask, request, jsonify
from datetime import datetime
import sqlite3
import os
from typing import Dict, Any, Tuple, Optional
from pathlib import Path
from functools import wraps
from dataclasses import dataclass, field
import logging
from werkzeug.utils import secure_filename
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import threading
import queue
import atexit

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('farm_api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
@dataclass
class Config:
    """Application configuration settings"""
    DATABASE: str = 'farm_data.db'
    BASE_IMAGE_FOLDER: Path = field(default_factory=lambda: Path('uploaded_images'))
    ALLOWED_IMAGE_EXTENSIONS: set = field(default_factory=lambda: {'png', 'jpg', 'jpeg'})
    MAX_IMAGE_SIZE: int = 10 * 1024 * 1024  # 10MB
    DB_POOL_SIZE: int = 20
    WRITE_QUEUE_SIZE: int = 1000
    THREAD_POOL_SIZE: int = 4
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 0.1  # seconds

config = Config()
config.BASE_IMAGE_FOLDER.mkdir(exist_ok=True, parents=True)

app = Flask(__name__)

# Initialize rate limiter with storage
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per minute", "5 per second"],
    storage_uri="memory://"
)

class DatabaseError(Exception):
    """Custom exception for database-related errors"""
    pass

class DatabasePool:
    """Thread-safe connection pool for database connections"""
    
    def __init__(self, database: str, max_connections: int = 20):
        self.database = database
        self.pool = queue.Queue(maxsize=max_connections)
        self.lock = threading.Lock()
        self._active_connections = set()
        self._fill_pool()
    
    def _fill_pool(self) -> None:
        """Fill the connection pool"""
        for _ in range(self.pool.maxsize):
            self._create_connection()
    
    def _create_connection(self) -> None:
        """Create a new database connection"""
        try:
            conn = sqlite3.connect(self.database, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self.pool.put(conn)
        except sqlite3.Error as e:
            logger.error(f"Error creating database connection: {e}")
            raise DatabaseError(f"Failed to create database connection: {e}")
    
    def get_connection(self) -> sqlite3.Connection:
        """Get a connection from the pool with retry logic"""
        for attempt in range(config.MAX_RETRIES):
            try:
                conn = self.pool.get(timeout=1.0)
                with self.lock:
                    self._active_connections.add(conn)
                return conn
            except queue.Empty:
                if attempt < config.MAX_RETRIES - 1:
                    time.sleep(config.RETRY_DELAY)
                    continue
                raise DatabaseError("Unable to get database connection from pool")
    
    def return_connection(self, conn: sqlite3.Connection) -> None:
        """Return a connection to the pool"""
        try:
            with self.lock:
                if conn in self._active_connections:
                    self._active_connections.remove(conn)
                    self.pool.put(conn)
        except Exception as e:
            logger.error(f"Error returning connection to pool: {e}")
    
    def close_all(self) -> None:
        """Close all connections in the pool"""
        with self.lock:
            while not self.pool.empty():
                try:
                    conn = self.pool.get_nowait()
                    if conn in self._active_connections:
                        self._active_connections.remove(conn)
                    conn.close()
                except queue.Empty:
                    break
            # Close any remaining active connections
            for conn in self._active_connections.copy():
                try:
                    conn.close()
                    self._active_connections.remove(conn)
                except Exception as e:
                    logger.error(f"Error closing connection: {e}")

def validate_request_data(required_fields: set) -> callable:
    """Decorator to validate request data"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not request.is_json:
                return jsonify({"error": "Request must be JSON"}), 400
            
            data = request.get_json()
            if not data:
                return jsonify({"error": "Empty request body"}), 400
                
            missing_fields = required_fields - set(data.keys())
            
            if missing_fields:
                return jsonify({
                    "error": f"Missing required fields: {', '.join(missing_fields)}"
                }), 400
            
            # Validate data types
            for field in required_fields:
                if not isinstance(data[field], (int, float, str)):
                    return jsonify({
                        "error": f"Invalid data type for field: {field}"
                    }), 400
            
            return f(*args, **kwargs)
        return wrapper
    return decorator

@app.route('/api/rack/<int:rack_id>/actuator', methods=['POST'])
@limiter.limit("10 per second")
@validate_request_data({'light_status', 'pump_status', 'ph_up_pump_status', 
                       'ph_down_pump_status', 'nutrient_pump_status'})
def collect_actuator_data(rack_id: int) -> Tuple[Dict[str, str], int]:
    """Endpoint to collect actuator data"""
    try:
        conn = db_pool.get_connection()
        try:
            cursor = conn.cursor()
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute("""
                INSERT INTO actuator_data 
                (rack_id, light_status, pump_status, ph_up_pump_status,
                ph_down_pump_status, nutrient_pump_status, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                rack_id,
                request.json['light_status'],
                request.json['pump_status'],
                request.json['ph_up_pump_status'],
                request.json['ph_down_pump_status'],
                request.json['nutrient_pump_status'],
                timestamp
            ))
            conn.commit()
            return jsonify({"message": "Actuator data collected successfully!"}), 200
        except sqlite3.Error as e:
            logger.error(f"Database error collecting actuator data: {e}")
            return jsonify({"error": "Database error"}), 500
        finally:
            db_pool.return_connection(conn)
    except DatabaseError as e:
        logger.error(f"Error collecting actuator data: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/rack/<int:rack_id>/camera/<int:camera_id>/image', methods=['POST'])
@limiter.limit("5 per second")
def upload_image(rack_id: int, camera_id: int) -> Tuple[Dict[str, str], int]:
    """Endpoint to upload an image from a camera"""
    if 'image' not in request.files:
        return jsonify({"error": "No image file provided"}), 400
    
    image = request.files['image']
    if not image.filename:
        return jsonify({"error": "No selected image"}), 400
    
    # Check if the file is an allowed image type
    ext = image.filename.rsplit('.', 1)[1].lower() if '.' in image.filename else ''
    if ext not in config.ALLOWED_IMAGE_EXTENSIONS:
        return jsonify({"error": "Invalid image format"}), 400
    
    try:
        # Create a secure filename
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = secure_filename(f"{rack_id}_{camera_id}_{timestamp}.{ext}")
        
        # Create directory if it doesn't exist
        camera_folder = config.BASE_IMAGE_FOLDER / str(rack_id) / str(camera_id)
        camera_folder.mkdir(parents=True, exist_ok=True)
        
        # Full path for the image
        file_path = camera_folder / filename
        
        # Save the image
        image.save(str(file_path))
        
        # Save metadata to database
        conn = db_pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO images (rack_id, camera_id, file_path, timestamp)
                VALUES (?, ?, ?, ?)
            """, (rack_id, camera_id, str(file_path), timestamp))
            conn.commit()
            
            return jsonify({
                "message": "Image uploaded successfully!",
                "file_path": str(file_path)
            }), 200
        except sqlite3.Error as e:
            logger.error(f"Database error saving image metadata: {e}")
            if file_path.exists():
                file_path.unlink()  # Delete the image if db insert fails
            return jsonify({"error": "Database error"}), 500
        finally:
            db_pool.return_connection(conn)
            
    except Exception as e:
        logger.error(f"Error uploading image: {e}")
        return jsonify({"error": f"Failed to upload image: {str(e)}"}), 500

def init_db() -> None:
    """Initialize the database tables with proper indexing"""
    with sqlite3.connect(config.DATABASE) as conn:
        cursor = conn.cursor()
        
        # Create tables with indexes
        tables_and_indexes = {
            'sensor_data': ("""
                CREATE TABLE IF NOT EXISTS sensor_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rack_id INTEGER NOT NULL,
                    ph REAL NOT NULL,
                    tds REAL NOT NULL,
                    water_temp REAL NOT NULL,
                    light_intensity REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """, [
                "CREATE INDEX IF NOT EXISTS idx_sensor_rack_time ON sensor_data(rack_id, timestamp)"
            ]),
            
            'actuator_data': ("""
                CREATE TABLE IF NOT EXISTS actuator_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rack_id INTEGER NOT NULL,
                    light_status VARCHAR(10) NOT NULL,
                    pump_status VARCHAR(10) NOT NULL,
                    ph_up_pump_status VARCHAR(10) NOT NULL,
                    ph_down_pump_status VARCHAR(10) NOT NULL,
                    nutrient_pump_status VARCHAR(10) NOT NULL,
                    timestamp TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """, [
                "CREATE INDEX IF NOT EXISTS idx_actuator_rack_time ON actuator_data(rack_id, timestamp)"
            ]),
                CREATE TABLE IF NOT EXISTS environment_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rack_id INTEGER NOT NULL,
                    temperature REAL NOT NULL,
                    humidity REAL NOT NULL,
                    pressure REAL NOT NULL,
                    voc REAL NOT NULL,
                    co2 REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """, [
                "CREATE INDEX IF NOT EXISTS idx_env_rack_time ON environment_data(rack_id, timestamp)"
            ]),
            
            'images': ("""
                CREATE TABLE IF NOT EXISTS images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rack_id INTEGER NOT NULL,
                    camera_id INTEGER NOT NULL,
                    file_path TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(rack_id, camera_id, file_path)
                )
            """, [
                "CREATE INDEX IF NOT EXISTS idx_images_rack_time ON images(rack_id, timestamp)"
            ])
        }
        
        for table_name, (table_sql, indexes) in tables_and_indexes.items():
            try:
                cursor.execute(table_sql)
                for index_sql in indexes:
                    cursor.execute(index_sql)
                logger.info(f"Created/verified table and indexes: {table_name}")
            except sqlite3.Error as e:
                logger.error(f"Error creating table {table_name}: {e}")
                raise

# Initialize database pool
db_pool = DatabasePool(config.DATABASE, config.DB_POOL_SIZE)

@app.route('/api/rack/<int:rack_id>/data', methods=['POST'])
@limiter.limit("10 per second")
@validate_request_data({'ph', 'tds', 'water_temp', 'light_intensity'})
def collect_sensor_data(rack_id: int) -> Tuple[Dict[str, str], int]:
    """Endpoint to collect sensor data"""
    try:
        conn = db_pool.get_connection()
        try:
            cursor = conn.cursor()
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute("""
                INSERT INTO sensor_data 
                (rack_id, ph, tds, water_temp, light_intensity, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                rack_id,
                request.json['ph'],
                request.json['tds'],
                request.json['water_temp'],
                request.json['light_intensity'],
                timestamp
            ))
            conn.commit()
            return jsonify({"message": "Sensor data collected successfully!"}), 200
        except sqlite3.Error as e:
            logger.error(f"Database error collecting sensor data: {e}")
            return jsonify({"error": "Database error"}), 500
        finally:
            db_pool.return_connection(conn)
    except DatabaseError as e:
        logger.error(f"Error collecting sensor data: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/rack/<int:rack_id>/environment', methods=['POST'])
@limiter.limit("10 per second")
@validate_request_data({'temperature', 'humidity', 'pressure', 'voc', 'co2'})
def collect_environment_data(rack_id: int) -> Tuple[Dict[str, str], int]:
    """Endpoint to collect environment data"""
    try:
        conn = db_pool.get_connection()
        try:
            cursor = conn.cursor()
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute("""
                INSERT INTO environment_data 
                (rack_id, temperature, humidity, pressure, voc, co2, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                rack_id,
                request.json['temperature'],
                request.json['humidity'],
                request.json['pressure'],
                request.json['voc'],
                request.json['co2'],
                timestamp
            ))
            conn.commit()
            return jsonify({"message": "Environment data collected successfully!"}), 200
        except sqlite3.Error as e:
            logger.error(f"Database error collecting environment data: {e}")
            return jsonify({"error": "Database error"}), 500
        finally:
            db_pool.return_connection(conn)
    except DatabaseError as e:
        logger.error(f"Error collecting environment data: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/rack/<int:rack_id>/data/all', methods=['GET'])
@limiter.limit("5 per second")
def get_rack_data(rack_id: int) -> Tuple[Dict[str, Any], int]:
    """Get all data for a specific rack"""
    try:
        conn = db_pool.get_connection()
        try:
            cursor = conn.cursor()
            
            def fetch_latest_data(table: str, columns: list) -> Optional[Dict]:
                """Helper function to fetch latest data from a table"""
                column_str = ', '.join(columns)
                cursor.execute(f"""
                    SELECT {column_str}
                    FROM {table}
                    WHERE rack_id = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (rack_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
            
            # Get latest sensor data
            sensor_data = fetch_latest_data(
                'sensor_data',
                ['ph', 'tds', 'water_temp', 'light_intensity', 'timestamp']
            )
            
            # Get latest actuator data
            actuator_data = fetch_latest_data(
                'actuator_data',
                ['light_status', 'pump_status', 'ph_up_pump_status',
                 'ph_down_pump_status', 'nutrient_pump_status', 'timestamp']
            )
            
            # Get latest environment data
            environment_data = fetch_latest_data(
                'environment_data',
                ['temperature', 'humidity', 'pressure', 'voc', 'co2', 'timestamp']
            )
            
            # Get recent images
            cursor.execute("""
                SELECT camera_id, file_path, timestamp
                FROM images
                WHERE rack_id = ?
                ORDER BY timestamp DESC
                LIMIT 5
            """, (rack_id,))
            recent_images = [dict(row) for row in cursor.fetchall()]
            
            response_data = {
                "rack_id": rack_id,
                "sensor_data": sensor_data,
                "actuator_data": actuator_data,
                "environment_data": environment_data,
                "recent_images": recent_images,
                "timestamp": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return jsonify(response_data), 200
        except sqlite3.Error as e:
            logger.error(f"Database error retrieving rack data: {e}")
            return jsonify({"error": "Database error"}), 500
        finally:
            db_pool.return_connection(conn)
    except DatabaseError as e:
        logger.error(f"Error retrieving rack data: {e}")
        return jsonify({"error": str(e)}), 500

def cleanup() -> None:
    """Cleanup resources on shutdown"""
    logger.info("Cleaning up resources...")
    db_pool.close_all()

# Register cleanup handler
atexit.register(cleanup)

if __name__ == '__main__':
    # Initialize database
    init_db()
    
    try:
        # Try to use production server (waitress)
        from waitress import serve
        logger.info("Starting production server with Waitress...")
        serve(app, host='0.0.0.0', port=5000, threads=8)
    except ImportError:
        # Fall back to Flask development server
        logger.warning("Waitress not installed. Using Flask development server instead.")
        logger.warning("Install waitress for production use: pip install waitress")
        app.run(host='0.0.0.0', port=5000, debug=True)