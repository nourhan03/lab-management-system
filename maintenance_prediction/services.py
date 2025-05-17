from datetime import datetime, timedelta
from sqlalchemy import func, not_, or_
from model import Devices, Maintenances, Laboratories, DeviceLabs
from extensions import db

class MaintenancePredictionService:
    @staticmethod
    def predict_device_maintenance():
        # الحصول على الأجهزة المتاحة (جميع الأجهزة باستثناء: قيد الصيانة، في الصيانة، غير متاح)
        unavailable_statuses = ["قيد الصيانة", "في الصيانة", "غير متاح"]
        available_devices = Devices.query.filter(not_(Devices.Status.in_(unavailable_statuses))).all()
        
        maintenance_predictions = []
        
        current_date = datetime.now()
        
        for device in available_devices:
            prediction = {
                "Id": device.Id,
                "Name": device.Name,
                "CurrentHour": device.CurrentHour,
                "MaximumHour": device.MaximumHour
            }
            
            # التحقق من ساعات التشغيل للصيانة الدورية
            if device.CurrentHour >= device.MaximumHour * 0.9:  # إذا وصل إلى 90% من الحد الأقصى
                prediction["MaintenanceType"] = "صيانة دورية"
                # حساب التاريخ المتوقع بناءً على معدل استخدام الجهاز
                remaining_hours = device.MaximumHour - device.CurrentHour
                prediction["ExpectedDate"] = (current_date + timedelta(days=remaining_hours/8)).strftime('%Y-%m-%d')  # تقدير 8 ساعات في اليوم
                
                # حساب التكلفة المتوقعة للصيانة
                prediction["ExpectedCost"] = MaintenancePredictionService.get_expected_maintenance_cost(device, "صيانة دورية")
            
            # التحقق من تاريخ المعايرة
            if device.CalibrationInterval is not None and device.LastMaintenanceDate is not None:
                last_calibration = Maintenances.query.filter(
                    Maintenances.DeviceId == device.Id,
                    Maintenances.Type == "معايرة"
                ).order_by(Maintenances.EndAt.desc()).first()
                
                if last_calibration:
                    # حساب تاريخ المعايرة التالية المتوقعة
                    next_calibration_date = last_calibration.EndAt + timedelta(days=device.CalibrationInterval * 30)  # تحويل الشهور إلى أيام
                    
                    # إذا كان موعد المعايرة التالية قريبًا (خلال 30 يوم)
                    if (next_calibration_date - current_date).days <= 30 and (next_calibration_date - current_date).days > 0:
                        # إضافة معايرة متوقعة فقط إذا لم تكن هناك صيانة دورية متوقعة بالفعل أو إذا كانت المعايرة قبل الصيانة الدورية
                        if "MaintenanceType" not in prediction or (
                            datetime.strptime(prediction["ExpectedDate"], '%Y-%m-%d') > next_calibration_date
                        ):
                            prediction["MaintenanceType"] = "معايرة"
                            prediction["ExpectedDate"] = next_calibration_date.strftime('%Y-%m-%d')
                            
                            # حساب التكلفة المتوقعة للمعايرة
                            prediction["ExpectedCost"] = MaintenancePredictionService.get_expected_maintenance_cost(device, "معايرة")
                            
                    # إذا تجاوز موعد المعايرة التالية التاريخ الحالي
                    elif (next_calibration_date - current_date).days <= 0:
                        prediction["MaintenanceType"] = "معايرة متأخرة"
                        prediction["ExpectedDate"] = next_calibration_date.strftime('%Y-%m-%d')
                        
                        # حساب التكلفة المتوقعة للمعايرة
                        prediction["ExpectedCost"] = MaintenancePredictionService.get_expected_maintenance_cost(device, "معايرة")
            
            # إضافة التوقع فقط إذا تم تحديد نوع الصيانة
            if "MaintenanceType" in prediction:
                maintenance_predictions.append(prediction)
        
        return maintenance_predictions
        
    @staticmethod
    def get_expected_maintenance_cost(device, maintenance_type):
        """
        حساب التكلفة المتوقعة للصيانة بناءً على صيانات سابقة للجهاز نفسه أو أجهزة من نفس الفئة
        
        :param device: الجهاز المراد حساب تكلفة صيانته
        :param maintenance_type: نوع الصيانة (صيانة دورية أو معايرة)
        :return: التكلفة المتوقعة للصيانة
        """
        # 1. البحث عن صيانات سابقة لنفس الجهاز ومن نفس النوع
        previous_maintenance = Maintenances.query.filter(
            Maintenances.DeviceId == device.Id,
            Maintenances.Type == maintenance_type
        ).order_by(Maintenances.EndAt.desc()).first()
        
        if previous_maintenance:
            return float(previous_maintenance.Cost)
        
        # 2. إذا لم يتم العثور على صيانات سابقة للجهاز، ابحث عن صيانات لأجهزة من نفس الفئة
        similar_devices = Devices.query.filter(
            Devices.CategoryName == device.CategoryName,
            Devices.Id != device.Id
        ).all()
        
        similar_device_ids = [d.Id for d in similar_devices]
        
        if similar_device_ids:
            # البحث عن أحدث صيانة للأجهزة من نفس الفئة
            similar_maintenance = Maintenances.query.filter(
                Maintenances.DeviceId.in_(similar_device_ids),
                Maintenances.Type == maintenance_type
            ).order_by(Maintenances.EndAt.desc()).first()
            
            if similar_maintenance:
                return float(similar_maintenance.Cost)
        
        # 3. إذا لم يتم العثور على أي صيانات، استخدم متوسط تكلفة جميع الصيانات من نفس النوع
        avg_cost = db.session.query(func.avg(Maintenances.Cost)).filter(
            Maintenances.Type == maintenance_type
        ).scalar()
        
        if avg_cost:
            return float(avg_cost)
        
        # 4. إذا لم يتم العثور على أي شيء، عد بقيمة افتراضية
        return 500.0  # قيمة افتراضية معقولة للصيانة
   