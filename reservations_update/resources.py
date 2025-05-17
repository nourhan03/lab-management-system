from flask_restful import Resource, request
from .services import ReservationService
from model import Reservations


class ReservationResource(Resource):
    def put(self, reservation_id):
        try:
            data = request.get_json()
            
            # التحقق من وجود الحجز
            reservation = Reservations.query.get(reservation_id)
            if not reservation:
                return {
                    "success": False,
                    "message": "الحجز غير موجود"
                }, 404

            # التحقق من البيانات المطلوب تحديثها
            allowed_fields = [
                'lab_id', 'experiment_id', 'device_ids',
                'date', 'start_time', 'end_time', 'purpose'
            ]
            
            update_data = {}
            for field in allowed_fields:
                if field in data:
                    update_data[field] = data[field]
            
            if not update_data:
                return {
                    "success": False,
                    "message": "لم يتم تقديم أي بيانات للتحديث"
                }, 400

            # تحديث الحجز
            success, message = ReservationService.update_reservation(
                reservation_id,
                update_data
            )

            if not success:
                return {"success": False, "message": message}, 400

            return {
                "success": True,
                "message": "تم تحديث الحجز بنجاح",
                "reservation_id": reservation_id
            }, 200

        except Exception as e:
            return {
                "success": False,
                "message": f"حدث خطأ أثناء تحديث الحجز: {str(e)}"
            }, 500 