from flask import request, jsonify
from flask_restful import Resource
from datetime import datetime
from .services import MaintenancePredictionService
from model import Devices, DeviceLabs, Laboratories

class DeviceMaintenancePredictionResource(Resource):
    def get(self):
        """
        الحصول على قائمة بالأجهزة المتاحة التي تحتاج إلى صيانة متوقعة
        ---
        responses:
          200:
            description: قائمة بتوقعات الصيانة للأجهزة المتاحة
        """
        try:
            maintenance_predictions = MaintenancePredictionService.predict_device_maintenance()
            return jsonify({
                "status": "success",
                "data": maintenance_predictions,
                "message": "تم استرجاع توقعات الصيانة بنجاح"
            })
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": f"حدث خطأ أثناء استرجاع توقعات الصيانة: {str(e)}"
            }), 500
    