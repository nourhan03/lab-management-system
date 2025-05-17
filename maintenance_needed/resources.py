from flask_restful import Resource
from .services import MaintenanceService


class MaintenanceNeededResource(Resource):
    def get(self):
        try:
            success, result = MaintenanceService.get_devices_needing_maintenance()
            
            if not success:
                return {
                    "success": False,
                    "message": result
                }, 500

            return {
                "success": True,
                "message": "تم جلب بيانات الأجهزة وأولويات الصيانة بنجاح",
                "devices": result
            }, 200

        except Exception as e:
            return {
                "success": False,
                "message": f"حدث خطأ أثناء جلب بيانات الأجهزة: {str(e)}"
            }, 500 