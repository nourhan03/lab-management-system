from model import Devices, Laboratories, Maintenances
from sqlalchemy import or_, and_, select
from datetime import datetime
from extensions import db


class MaintenanceService:
    @staticmethod
    def calculate_periodic_maintenance_priority(current_hours, max_hours):
        percentage = (current_hours / max_hours) * 100
        if current_hours >= max_hours:
            return "طارئة"
        elif percentage >= 90:
            return "عالية"
        elif 60 <= percentage < 90:
            return "متوسطة"
        else:
            return "ضعيفة"

    @staticmethod
    def calculate_months_between_dates(start_date, end_date):
        # حساب عدد الشهور بين تاريخين
        months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
        if end_date.day < start_date.day:
            months -= 1
        return months

    @staticmethod
    def calculate_calibration_priority(device_id, calibration_interval):
        if not calibration_interval:
            return "غير محدد"

        # استخدام select لتحديد الأعمدة المطلوبة فقط
        stmt = select(Maintenances.EndAt).where(
            and_(
                Maintenances.DeviceId == device_id,
                Maintenances.Type == "معايرة"
            )
        ).order_by(Maintenances.EndAt.desc())
        
        last_calibration = db.session.execute(stmt).first()

        if not last_calibration or not last_calibration[0]:
            return "غير محدد"

        # حساب عدد الشهور منذ آخر معايرة
        months_since_calibration = MaintenanceService.calculate_months_between_dates(
            last_calibration[0],
            datetime.now()
        )
        
        # حساب النسبة المئوية من فترة المعايرة التي مرت
        percentage = (months_since_calibration / calibration_interval) * 100
        
        if months_since_calibration >= calibration_interval:
            return "طارئة"
        elif percentage >= 90:
            return "عالية"
        elif 60 <= percentage < 90:
            return "متوسطة"
        else:
            return "ضعيفة"

    @staticmethod
    def get_last_calibration_date(device_id):
        # استخدام select لتحديد الأعمدة المطلوبة فقط
        stmt = select(Maintenances.EndAt).where(
            and_(
                Maintenances.DeviceId == device_id,
                Maintenances.Type == "معايرة"
            )
        ).order_by(Maintenances.EndAt.desc())
        
        result = db.session.execute(stmt).first()
        return result[0] if result else None

    @staticmethod
    def get_devices_needing_maintenance():
        try:
            # نجلب كل الأجهزة أولاً للتحقق
            all_devices = Devices.query.all()
            print(f"Total devices found: {len(all_devices)}")
            
            # نطبع حالة كل جهاز للتحقق
            for device in all_devices:
                print(f"Device ID: {device.Id}, Name: {device.Name}, Status: {device.Status}")

            # نجلب الأجهزة المتاحة فقط
            devices = Devices.query.filter(
                Devices.Status != ["في الصيانة", "غير متاح"]
            ).all()
            print(f"Available devices: {len(devices)}")

            devices_data = []
            for device in devices:
                # حساب أولوية الصيانة الدورية
                periodic_priority = MaintenanceService.calculate_periodic_maintenance_priority(
                    device.CurrentHour,
                    device.MaximumHour
                )

                # حساب أولوية صيانة المعايرة
                calibration_priority = MaintenanceService.calculate_calibration_priority(
                    device.Id,
                    device.CalibrationInterval
                )

                # تحديد الأولوية النهائية (نأخذ الأعلى أولوية)
                priority_order = {"طارئة": 4, "عالية": 3, "متوسطة": 2, "ضعيفة": 1, "غير محدد": 0}
                final_priority = (
                    periodic_priority if priority_order[periodic_priority] > priority_order[calibration_priority]
                    else calibration_priority
                )

                # الحصول على تاريخ آخر معايرة
                last_calibration_date = MaintenanceService.get_last_calibration_date(device.Id)

                devices_data.append({
                    "device_id": device.Id,
                    "device_name": device.Name,
                    "last_maintenance_date": device.LastMaintenanceDate.strftime("%Y-%m-%d") if device.LastMaintenanceDate else None,
                    "current_hours": device.CurrentHour,
                    "priority": final_priority,
                    "periodic_maintenance_details": {
                        "current_hours": device.CurrentHour,
                        "maximum_hours": device.MaximumHour,
                        "priority": periodic_priority
                    },
                    "calibration_maintenance_details": {
                        "last_calibration_date": last_calibration_date.strftime("%Y-%m-%d") if last_calibration_date else None,
                        "calibration_interval_months": device.CalibrationInterval,
                        "priority": calibration_priority
                    }
                })

            # ترتيب الأجهزة حسب الأولوية
            priority_order = {"طارئة": 4, "عالية": 3, "متوسطة": 2, "ضعيفة": 1, "غير محدد": 0}
            devices_data.sort(key=lambda x: priority_order[x["priority"]], reverse=True)

            return True, devices_data

        except Exception as e:
            return False, f"حدث خطأ أثناء جلب بيانات الأجهزة: {str(e)}" 