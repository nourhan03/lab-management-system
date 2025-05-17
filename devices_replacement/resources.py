
from flask import jsonify
from flask_restful import Resource
from .services import DevicesReplacementService

class DevicesReplacementResource(Resource):
    """مورد API للأجهزة التي تحتاج إلى استبدال"""
    
    def get(self):
        """
        الحصول على قائمة بالأجهزة التي تحتاج إلى استبدال
        ---
        responses:
          200:
            description: قائمة بالأجهزة التي تحتاج إلى استبدال مع تحليل لكل جهاز
        """
        try:
            devices_for_replacement = DevicesReplacementService.get_devices_for_replacement()
            
            return jsonify({
                "status": "نجاح",
                "data": devices_for_replacement,
                "message": "تم استرجاع قائمة الأجهزة التي تحتاج إلى استبدال بنجاح"
            })
        except Exception as e:
            return jsonify({
                "status": "فشل",
                "message": f"حدث خطأ أثناء استرجاع قائمة الأجهزة: {str(e)}"
            }), 500