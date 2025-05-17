from flask import Flask, jsonify
from flask_cors import CORS
from flask_restful import Api
from extensions import db, socketio, scheduler
from reservations import ReservationListResource
from reservations_update import ReservationResource
from maintenance_needed import MaintenanceNeededResource
from devices_suggestion import SuggestDeviceResource
from maintenance_prediction import DeviceMaintenancePredictionResource
from devices_replacement import DevicesReplacementResource
from future_needs import FutureNeedsResource
import signal
import sys
import os
from dotenv import load_dotenv
from sqlalchemy.exc import OperationalError

# تحميل متغيرات البيئة
load_dotenv()

def create_app(config_name='default'):
    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}})
    
    # استخدام متغير البيئة لرابط قاعدة البيانات
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'mssql+pyodbc://localhost/LabPhysicsFinalDb?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes&charset=UTF8')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    app.config['JSON_AS_ASCII'] = False
    
    app.config['SCHEDULER_API_ENABLED'] = True
    app.config['SCHEDULER_TIMEZONE'] = 'UTC'
    app.config['SCHEDULER_DAEMON'] = False  
    
    db.init_app(app)
    socketio.init_app(app, 
                     cors_allowed_origins="*",
                     async_mode='threading',  
                     daemon=False)  
    scheduler.init_app(app)
    
    # إضافة نقطة وصول للتحقق من صحة التطبيق
    @app.route('/health')
    def health_check():
        try:
            # محاولة التحقق من اتصال قاعدة البيانات
            with app.app_context():
                db.session.execute("SELECT 1")
            return jsonify({"status": "healthy", "database": "connected"})
        except OperationalError as e:
            # إذا كان هناك خطأ في الاتصال بقاعدة البيانات
            app.logger.error(f"Database connection error: {str(e)}")
            return jsonify({
                "status": "unhealthy", 
                "database": "disconnected",
                "error": str(e)
            }), 500
        except Exception as e:
            app.logger.error(f"Health check error: {str(e)}")
            return jsonify({"status": "unhealthy", "error": str(e)}), 500
    
    # إضافة نقطة وصول الجذر
    @app.route('/')
    def root():
        return jsonify({
            "message": "نظام إدارة المختبرات - واجهة برمجة التطبيقات",
            "version": "1.0",
            "status": "online",
            "endpoints": [
                "/reservations", 
                "/devices/maintenance-needed",
                "/devices/suggest/<device_id>",
                "/api/devices-maintenance-prediction",
                "/devices-replacement",
                "/future-spare-parts-needs"
            ]
        })
    
    api = Api(app)
    # Reservation List Resource
    api.add_resource(ReservationListResource, '/reservations')
    api.add_resource(ReservationResource, '/reservations/<int:reservation_id>')

    # Maintenance Needed Resource
    api.add_resource(MaintenanceNeededResource, '/devices/maintenance-needed')

    # Suggest Device Resource
    api.add_resource(SuggestDeviceResource, '/devices/suggest/<int:device_id>')
    
    # توقعات الصيانة للأجهزة المتاحة
    api.add_resource(DeviceMaintenancePredictionResource, '/api/devices-maintenance-prediction')
    
    # الأجهزة التي تحتاج إلى استبدال
    api.add_resource(DevicesReplacementResource, '/devices-replacement')
    
    # الاحتياجات المستقبلية من قطع الغيار
    api.add_resource(FutureNeedsResource, '/future-spare-parts-needs')
    
    return app  # Return the app instance

app = create_app()  # Create the app instance globally

def cleanup_resources():
    with app.app_context():
        try:
            scheduler.shutdown()
            db.session.remove()
            db.engine.dispose()
        except Exception as e:
            print(f'Error during cleanup: {str(e)}')
    
def signal_handler(sig, frame):
    print('تم استلام إشارة إنهاء. جاري إغلاق التطبيق...')
    cleanup_resources()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    scheduler.start()
    
    try:
        socketio.run(app, host='0.0.0.0', port=port, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        print('تم إيقاف التطبيق بواسطة المستخدم')
    finally:
        cleanup_resources()

