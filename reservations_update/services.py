from model import Users, Laboratories, Experiments, Reservations, Devices, ExperimentDevices, Maintenances
from datetime import datetime, date
from extensions import db
from sqlalchemy import or_, and_
import logging

logger = logging.getLogger(__name__)


class ReservationService:
    @staticmethod
    def validate_user_type(user_id):
        user = Users.query.get(user_id)
        if not user:
            return False, "المستخدم غير موجود"
        
        if user.UserType not in ["دكتور", "باحث"]:
            return False, "نوع المستخدم غير مصرح له بالحجز"
            
        return True, user

    @staticmethod
    def validate_lab_availability(lab_id, user_type, date_str, start_time_str, end_time_str, exclude_reservation_id=None):
        lab = Laboratories.query.get(lab_id)
        if not lab:
            return False, "المعمل غير موجود"
            
        if lab.Status != "متاح":
            return False, "المعمل غير متاح حالياً"
            
        # التحقق من نوع المعمل
        if user_type == "دكتور" and lab.Type != "أكاديمي":
            return False, "هذا المعمل مخصص للأبحاث فقط"
        elif user_type == "باحث" and lab.Type != "بحثي":
            return False, "هذا المعمل مخصص للتدريس فقط"

        # التحقق من صحة التاريخ والوقت
        try:
            reservation_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            start_time = datetime.strptime(start_time_str, "%H:%M").time()
            end_time = datetime.strptime(end_time_str, "%H:%M").time()
            
            # التحقق من أن التاريخ في المستقبل
            if reservation_date < date.today():
                return False, "لا يمكن الحجز في تاريخ سابق"
                
            # التحقق من أن وقت البداية قبل وقت النهاية
            start_datetime = datetime.combine(reservation_date, start_time)
            end_datetime = datetime.combine(reservation_date, end_time)
            
            if start_datetime >= end_datetime:
                return False, "وقت البداية يجب أن يكون قبل وقت النهاية"
        except ValueError:
            return False, "صيغة التاريخ أو الوقت غير صحيحة"

        # التحقق من الحجوزات الموجودة
        existing_reservations = Reservations.query.filter(
            Reservations.LabId == lab_id,
            Reservations.Date == reservation_date,
            Reservations.IsAllowed == True
        )
        
        # استثناء الحجز الحالي عند التحديث
        if exclude_reservation_id:
            existing_reservations = existing_reservations.filter(
                Reservations.Id != exclude_reservation_id
            )

        existing_reservations = existing_reservations.join(Users).all()

        for reservation in existing_reservations:
            res_start = datetime.combine(reservation_date, reservation.StartTime)
            res_end = datetime.combine(reservation_date, reservation.EndTime)
            
            # التحقق من التداخل الزمني
            if (start_datetime < res_end and end_datetime > res_start):
                # إذا كان هناك دكتور حاجز المعمل
                if reservation.user.UserType == "دكتور":
                    return False, "المعمل محجوز من قبل دكتور في هذا الوقت"
                # إذا كان المستخدم الحالي دكتور وهناك باحث حاجز
                elif user_type == "دكتور" and reservation.user.UserType == "باحث":
                    return False, "المعمل محجوز من قبل باحث في هذا الوقت"

        return True, lab

    @staticmethod
    def validate_experiment(experiment_id, lab_id, user_type):
        experiment = Experiments.query.get(experiment_id)
        if not experiment:
            return False, "التجربة غير موجودة"
            
        if experiment.LabId != lab_id:
            return False, "التجربة غير متوفرة في هذا المعمل"
            
        if user_type == "دكتور" and experiment.Type != "أكاديمية":
            return False, "هذه التجربة مخصصة للأبحاث فقط"
        elif user_type == "باحث" and experiment.Type != "بحثية":
            return False, "هذه التجربة مخصصة للتدريس فقط"
            
        return True, experiment

    @staticmethod
    def validate_devices(device_ids, experiment_id, date_str, start_time_str, end_time_str, exclude_reservation_id=None):
        try:
            # التحقق من صحة التاريخ والوقت
            reservation_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            start_time = datetime.strptime(start_time_str, "%H:%M").time()
            end_time = datetime.strptime(end_time_str, "%H:%M").time()
            
            # التحقق من أن التاريخ في المستقبل
            if reservation_date < date.today():
                return False, "لا يمكن الحجز في تاريخ سابق"
                
            # التحقق من أن وقت البداية قبل وقت النهاية
            start_datetime = datetime.combine(reservation_date, start_time)
            end_datetime = datetime.combine(reservation_date, end_time)
            
            if start_datetime >= end_datetime:
                return False, "وقت البداية يجب أن يكون قبل وقت النهاية"
            
            valid_devices = []
            for device_id in device_ids:
                device = Devices.query.get(device_id)
                if not device:
                    return False, f"الجهاز رقم {device_id} غير موجود"
                    
                # التحقق من أن الجهاز تابع للتجربة من خلال جدول ExperimentDevices
                experiment_device = ExperimentDevices.query.filter_by(
                    ExperimentId=experiment_id,
                    DeviceId=device_id
                ).first()
                
                if not experiment_device:
                    return False, f"الجهاز رقم {device_id} غير مرتبط بهذه التجربة"
                    
                if device.Status != "متاح":
                    return False, f"الجهاز {device.Name} غير متاح حالياً. الحالة: {device.Status}"
                
                # البحث عن الحجوزات المتداخلة بطريقة أكثر شمولية
                overlapping_reservations = db.session.query(Reservations).filter(
                    Reservations.DeviceId == device_id,
                    Reservations.Date == reservation_date,
                    Reservations.IsAllowed == True,
                    or_(
                        and_(
                            Reservations.StartTime <= start_time,
                            Reservations.EndTime > start_time
                        ),
                        and_(
                            Reservations.StartTime < end_time,
                            Reservations.EndTime >= end_time
                        ),
                        and_(
                            Reservations.StartTime >= start_time,
                            Reservations.EndTime <= end_time
                        )
                    )
                )
                
                # استثناء الحجز الحالي في حالة التحديث
                if exclude_reservation_id:
                    overlapping_reservations = overlapping_reservations.filter(
                        Reservations.Id != exclude_reservation_id
                    )
                
                overlapping_count = overlapping_reservations.count()
                
                if overlapping_count > 0:
                    return False, f"الجهاز {device.Name} محجوز بالفعل في هذا الوقت"
                
                # التحقق من وجود صيانة متداخلة للجهاز
                try:
                    overlapping_maintenance = db.session.query(Maintenances).filter(
                        Maintenances.DeviceId == device_id,
                        or_(
                            and_(
                                Maintenances.StartAt <= datetime.combine(reservation_date, datetime.min.time()),
                                Maintenances.EndAt >= datetime.combine(reservation_date, datetime.min.time())
                            )
                        ),
                        Maintenances.Status != "مكتملة"
                    ).count()
                    
                    if overlapping_maintenance > 0:
                        return False, f"الجهاز {device.Name} في الصيانة في هذا التاريخ"
                except Exception as e:
                    logger.warning(f"خطأ أثناء التحقق من جدول الصيانة: {str(e)}")
                    # استمر في التنفيذ حتى لو لم يتم العثور على جدول الصيانة
                    pass
                    
                valid_devices.append(device)
                
            return True, valid_devices
            
        except Exception as e:
            logger.error(f"خطأ أثناء التحقق من توفر الأجهزة: {str(e)}")
            return False, f"حدث خطأ أثناء التحقق من توفر الأجهزة: {str(e)}"

    @staticmethod
    def calculate_hours(start_time_str, end_time_str, date_str):
        start_time = datetime.strptime(start_time_str, "%H:%M").time()
        end_time = datetime.strptime(end_time_str, "%H:%M").time()
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
        
        start_datetime = datetime.combine(date, start_time)
        end_datetime = datetime.combine(date, end_time)
        return (end_datetime - start_datetime).total_seconds() / 3600

    @staticmethod
    def deduct_reservation_hours(reservation):
        """تقليل ساعات الحجز القديم"""
        hours = ReservationService.calculate_hours(
            reservation.StartTime.strftime("%H:%M"),
            reservation.EndTime.strftime("%H:%M"),
            reservation.Date.strftime("%Y-%m-%d")
        )
        
        # تقليل ساعات المعمل
        lab = Laboratories.query.get(reservation.LabId)
        lab.UsageHours -= hours
        lab.TotalOperatingHours -= hours
        
        # تقليل ساعات الأجهزة
        devices = Devices.query.join(Reservations).filter(
            Reservations.Id == reservation.Id
        ).all()
        
        for device in devices:
            device.CurrentHour -= hours
            device.TotalOperatingHours -= hours
            
        # تقليل عدد مرات إجراء التجربة
        experiment = Experiments.query.get(reservation.ExperimentId)
        experiment.CompletedCount -= 1
        
        db.session.commit()

    @staticmethod
    def add_reservation_hours(reservation, devices, lab, experiment, hours):
        """إضافة ساعات الحجز الجديد"""
        # إضافة ساعات المعمل
        lab.UsageHours += hours
        lab.TotalOperatingHours += hours
        
        # إضافة ساعات الأجهزة
        for device in devices:
            device.CurrentHour += hours
            device.TotalOperatingHours += hours
            
        # زيادة عدد مرات إجراء التجربة
        experiment.CompletedCount += 1
        
        db.session.commit()

    @staticmethod
    def update_reservation(reservation_id, update_data):
        try:
            # الحصول على الحجز الحالي
            reservation = Reservations.query.get(reservation_id)
            if not reservation:
                return False, "الحجز غير موجود"

            # التحقق من نوع المستخدم
            user_valid, user = ReservationService.validate_user_type(reservation.UserId)
            if not user_valid:
                return False, user

            # تحديد البيانات المطلوب تحديثها
            lab_id = update_data.get('lab_id', reservation.LabId)
            experiment_id = update_data.get('experiment_id', reservation.ExperimentId)
            device_ids = update_data.get('device_ids', [reservation.DeviceId])
            date_str = update_data.get('date', reservation.Date.strftime("%Y-%m-%d"))
            start_time_str = update_data.get('start_time', reservation.StartTime.strftime("%H:%M"))
            end_time_str = update_data.get('end_time', reservation.EndTime.strftime("%H:%M"))
            purpose = update_data.get('purpose', reservation.Purpose)

            # التحقق من توفر المعمل
            lab_valid, lab = ReservationService.validate_lab_availability(
                lab_id, user.UserType, date_str, start_time_str, end_time_str,
                exclude_reservation_id=reservation_id
            )
            if not lab_valid:
                return False, lab

            # التحقق من التجربة
            exp_valid, experiment = ReservationService.validate_experiment(
                experiment_id, lab_id, user.UserType
            )
            if not exp_valid:
                return False, experiment

            # التحقق من الأجهزة
            devices_valid, devices = ReservationService.validate_devices(
                device_ids, experiment_id, date_str, start_time_str, end_time_str,
                exclude_reservation_id=reservation_id
            )
            if not devices_valid:
                return False, devices

            # حساب ساعات الحجز الجديد
            new_hours = ReservationService.calculate_hours(
                start_time_str, end_time_str, date_str
            )

            # تقليل ساعات الحجز القديم
            ReservationService.deduct_reservation_hours(reservation)

            # تحديث بيانات الحجز
            reservation.LabId = lab_id
            reservation.ExperimentId = experiment_id
            reservation.Date = datetime.strptime(date_str, "%Y-%m-%d").date()
            reservation.StartTime = datetime.strptime(start_time_str, "%H:%M").time()
            reservation.EndTime = datetime.strptime(end_time_str, "%H:%M").time()
            reservation.Purpose = purpose
            reservation.IsAllowed = True

            # إضافة ساعات الحجز الجديد
            ReservationService.add_reservation_hours(
                reservation, devices, lab, experiment, new_hours
            )

            # حفظ التغييرات
            db.session.commit()
            return True, "تم تحديث الحجز بنجاح"

        except Exception as e:
            db.session.rollback()
            return False, f"حدث خطأ أثناء تحديث الحجز: {str(e)}" 