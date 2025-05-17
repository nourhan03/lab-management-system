from flask_restful import Resource, request
from .services import ReservationService
from model import Reservations, Laboratories


class ReservationListResource(Resource):
    def post(self):
        try:
            data = request.get_json()
            
            # التحقق من البيانات المطلوبة
            required_fields = [
                'user_id', 'lab_id', 'experiment_id', 'device_ids',
                'date', 'start_time', 'end_time', 'purpose'
            ]
            for field in required_fields:
                if field not in data:
                    return {"success": False, "message": f"الحقل {field} مطلوب"}, 400

            # إنشاء الحجز
            reservation_id, message = ReservationService.create_reservation(
                data['user_id'],
                data['lab_id'],
                data['experiment_id'],
                data['device_ids'],
                data['date'],
                data['start_time'],
                data['end_time'],
                data['purpose']
            )

            if not reservation_id:
                return {"success": False, "message": message}, 400

            # التحقق من حالة الحجز
            reservation = Reservations.query.get(reservation_id)
            if reservation.IsAllowed:
                return {
                    "success": True,
                    "message": "تم إنشاء الحجز بنجاح",
                    "reservation_id": reservation_id
                }, 201
            else:
                # الحصول على اسم المعمل
                lab = Laboratories.query.get(data['lab_id'])
                lab_name = lab.LabName if lab else "غير معروف"
                
                return {
                    "success": False,
                    "message": f"{lab_name} محجوز بالفعل",
                    "reservation_id": reservation_id,
                    "status": "تم تسجيل محاولة الحجز"
                }, 400

        except Exception as e:
            return {
                "success": False,
                "message": f"حدث خطأ أثناء إنشاء الحجز: {str(e)}"
            }, 500 

