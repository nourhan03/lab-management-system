from datetime import datetime, timedelta
from sqlalchemy import func, not_, or_
from extensions import db
from model import Devices, Maintenances, SpareParts

class DevicesReplacementService:
    """خدمة لتقييم الأجهزة التي تحتاج إلى استبدال"""
    
    @staticmethod
    def get_devices_for_replacement():
        """الحصول على قائمة بالأجهزة التي قد تحتاج إلى استبدال مع تحليل لكل جهاز"""
        # الحصول على كل الأجهزة
        all_devices = Devices.query.all()
        
        results = []
        for device in all_devices:
            evaluation = DevicesReplacementService.evaluate_device_replacement(device)
            # لإظهار جميع الأجهزة التي تم تقييمها (سواء كانت بحاجة للاستبدال أو لا)
            # قم بتعليق الشرط التالي إذا كنت تريد رؤية كل الأجهزة
            if evaluation["should_retire"]:  # فقط الأجهزة التي تحتاج للاستبدال
                results.append(evaluation)
                
        # ترتيب النتائج حسب الأولوية
        priority_order = {"طارئة": 0, "عالية": 1, "متوسطه": 2, "ضعيفه": 3}
        results.sort(key=lambda x: priority_order.get(x["priority"], 4))
                
        return results
    
    @staticmethod
    def evaluate_device_replacement(device):
        """
        تقييم ما إذا كان الجهاز بحاجة إلى الاستبدال
        
        المعايير:
        1. العمر الافتراضي للجهاز (Lifespan) بالسنوات
        2. تكرار الصيانات في فترة قصيرة
        3. تكلفة الصيانة مقارنة بتكلفة الشراء
        """
        # البدء بافتراض عدم الحاجة للاستبدال
        result = {
            "device_id": device.Id,
            "device_name": device.Name,
            "device_serial": device.SerialNumber,
            "should_retire": False,
            "confidence": "ضعيفه",
            "reasons": [],
            "financial_analysis": {},
            "priority": "ضعيفه"
        }
        
        # المعيار 1: فحص العمر الافتراضي للجهاز بالسنوات
        lifespan_score = DevicesReplacementService._evaluate_by_lifespan(device)
        if lifespan_score:
            result["reasons"].append(lifespan_score["reason"])
            if lifespan_score["retire"]:
                result["should_retire"] = True
        
        # المعيار 2: تكرار الصيانات في فترة قصيرة
        maintenance_score = DevicesReplacementService._evaluate_by_maintenance_frequency(device)
        if maintenance_score:
            result["reasons"].append(maintenance_score["reason"])
            if maintenance_score["retire"]:
                result["should_retire"] = True
        
        # المعيار 3: تكلفة الصيانة مقارنة بتكلفة الشراء
        cost_score = DevicesReplacementService._evaluate_by_maintenance_cost(device)
        if cost_score:
            result["reasons"].append(cost_score["reason"])
            result["financial_analysis"] = cost_score["financial_analysis"]
            if cost_score["retire"]:
                result["should_retire"] = True
        
        # تحديد مستوى الثقة في التوصية
        confidence_scores = [s for s in [lifespan_score, maintenance_score, cost_score] if s]
        positive_scores = sum(1 for s in confidence_scores if s["retire"])
        
        if len(confidence_scores) > 0:
            confidence_ratio = positive_scores / len(confidence_scores)
            if confidence_ratio >= 0.7:
                result["confidence"] = "مرتفعه"
            elif confidence_ratio >= 0.4:
                result["confidence"] = "متوسطه"
            else:
                result["confidence"] = "ضعيفه"
        
        # تحديد مستوى الأولوية
        if result["should_retire"]:
            priorities = [s.get("priority", "ضعيفه") for s in confidence_scores if s]
            if "طارئة" in priorities:
                result["priority"] = "طارئة"
            elif "عالية" in priorities:
                result["priority"] = "عالية"
            elif "متوسطه" in priorities:
                result["priority"] = "متوسطه"
            else:
                result["priority"] = "ضعيفه"
        
        # إضافة نصائح وتوصيات
        result["recommendations"] = DevicesReplacementService._get_recommendations(device, result)
        
        return result
    
    @staticmethod
    def _evaluate_by_lifespan(device):
        """تقييم بناء على العمر الافتراضي للجهاز (بالسنوات)"""
        if not device.PurchaseDate or not device.Lifespan or device.Lifespan == 0:
            return None
        
        # حساب عمر الجهاز الحالي بالأيام
        device_age_days = (datetime.now() - device.PurchaseDate).days
        
        # تحويل العمر الافتراضي من سنوات إلى أيام
        lifespan_days = device.Lifespan * 365
        
        # حساب نسبة العمر المستهلك من العمر الافتراضي
        lifespan_percentage = (device_age_days / lifespan_days) * 100 if lifespan_days > 0 else 100
        
        # تقريب النسبة المئوية لأقرب رقمين عشريين
        lifespan_percentage = round(lifespan_percentage, 2)
        
        result = {
            "retire": False,
            "reason": "",
            "priority": "ضعيفه"
        }
        
        if lifespan_percentage >= 100:
            result["retire"] = True
            # تقريب النسبة الزائدة
            percentage_over = round(lifespan_percentage - 100, 2)
            result["reason"] = f"الجهاز تجاوز عمره الافتراضي ({device.Lifespan} سنوات) بنسبة {percentage_over}٪"
            result["priority"] = "طارئة"
        elif lifespan_percentage >= 85:  # تخفيف من 90% إلى 85%
            result["retire"] = True
            result["reason"] = f"الجهاز استهلك {lifespan_percentage}٪ من عمره الافتراضي البالغ {device.Lifespan} سنوات"
            result["priority"] = "عالية"
        elif lifespan_percentage >= 65:  # تخفيف من 70% إلى 65%
            result["retire"] = True
            result["reason"] = f"الجهاز استهلك {lifespan_percentage}٪ من عمره الافتراضي، وبدأ يقترب من نهاية عمره المتوقع"
            result["priority"] = "متوسطه"
        elif lifespan_percentage >= 50:  # إضافة شرط جديد للأجهزة التي استهلكت 50% من عمرها
            result["retire"] = False
            result["reason"] = f"الجهاز استهلك {lifespan_percentage}٪ من عمره الافتراضي، ويجب مراقبته"
            result["priority"] = "ضعيفه"
            return result
        else:
            return None
        
        return result
    
    @staticmethod
    def _evaluate_by_maintenance_frequency(device):
        """تقييم بناء على تكرار الصيانات في فترة قصيرة"""
        # الحصول على تاريخ صيانات الجهاز 
        six_months_ago = datetime.now() - timedelta(days=180)
        one_year_ago = datetime.now() - timedelta(days=365)
        
        # البحث عن صيانات الإصلاح خلال آخر 6 أشهر
        repair_maintenances = Maintenances.query.filter(
            Maintenances.DeviceId == device.Id,
            Maintenances.SchedulingAt > six_months_ago,
            Maintenances.Type == "إصلاح"
        ).all()
        
        # البحث عن صيانات الدورية خلال آخر سنة
        periodic_maintenances = Maintenances.query.filter(
            Maintenances.DeviceId == device.Id,
            Maintenances.SchedulingAt > one_year_ago,
            Maintenances.Type == "دورية"
        ).all()
        
        repair_count = len(repair_maintenances)
        periodic_count = len(periodic_maintenances)
        
        result = {
            "retire": False,
            "reason": "",
            "priority": "ضعيفه"
        }
        
        # تقييم معدل صيانات الإصلاح
        if repair_count >= 2:  # تخفيف من 3 إلى 2
            result["retire"] = True
            result["reason"] = f"الجهاز خضع لـ {repair_count} صيانات إصلاح خلال آخر 6 أشهر، وهو معدل مرتفع جداً"
            result["priority"] = "عالية"
            return result
        elif repair_count >= 1:  # تخفيف من 2 إلى 1
            result["retire"] = True
            result["reason"] = f"الجهاز خضع لـ {repair_count} صيانات إصلاح خلال آخر 6 أشهر، وهو معدل مرتفع"
            result["priority"] = "متوسطه"
            return result
        
        # تقييم معدل الصيانات الدورية
        if periodic_count >= 3:  # تخفيف من 4 إلى 3
            result["retire"] = True
            result["reason"] = f"الجهاز خضع لـ {periodic_count} صيانات دورية خلال آخر سنة، وهو معدل مرتفع جداً"
            result["priority"] = "عالية"
            return result
        elif periodic_count >= 2:  # تخفيف من 3 إلى 2
            result["retire"] = True
            result["reason"] = f"الجهاز خضع لـ {periodic_count} صيانات دورية خلال آخر سنة، وهو معدل مرتفع"
            result["priority"] = "متوسطه"
            return result
        
        # إذا كان هناك مزيج من الصيانات الإصلاحية والدورية
        combined_score = repair_count * 2 + periodic_count  # الصيانات الإصلاحية تؤثر بشكل أكبر
        if combined_score >= 3:  # تخفيف من 5 إلى 3
            result["retire"] = True
            result["reason"] = f"الجهاز خضع لـ {repair_count} صيانات إصلاح و {periodic_count} صيانات دورية، مما يشير إلى تدهور حالته"
            result["priority"] = "عالية"
            return result
        elif combined_score >= 2:  # تخفيف من 3 إلى 2
            result["retire"] = True
            result["reason"] = f"الجهاز خضع لـ {repair_count} صيانات إصلاح و {periodic_count} صيانات دورية، مما يشير إلى حاجته للمراقبة"
            result["priority"] = "متوسطه"
            return result
        elif combined_score >= 1:
            result["retire"] = False
            result["reason"] = f"الجهاز خضع لـ {repair_count} صيانات إصلاح و {periodic_count} صيانات دورية، وهو معدل يستدعي المراقبة"
            result["priority"] = "ضعيفه"
            return result
        
        return None
    
    @staticmethod
    def _evaluate_by_maintenance_cost(device):
        """تقييم بناء على تكلفة الصيانة مقارنة بتكلفة الشراء"""
        if device.PurchaseCost <= 0:
            return None
        
        # حساب إجمالي تكاليف الصيانة
        maintenance_costs = db.session.query(func.sum(Maintenances.Cost)).filter(
            Maintenances.DeviceId == device.Id
        ).scalar() or 0
        
        # حساب نسبة تكاليف الصيانة إلى تكلفة الشراء
        cost_ratio = (float(maintenance_costs) / float(device.PurchaseCost)) * 100
        
        yearly_cost_avg = 0
        device_age_years = (datetime.now() - device.PurchaseDate).days / 365 if device.PurchaseDate else 1
        if device_age_years > 0:
            yearly_cost_avg = float(maintenance_costs) / device_age_years
        
        # تقريب القيم العشرية إلى رقمين عشريين
        cost_ratio = round(cost_ratio, 2)
        yearly_cost_avg = round(yearly_cost_avg, 2)
        maintenance_costs_rounded = round(float(maintenance_costs), 2)
        purchase_cost_rounded = round(float(device.PurchaseCost), 2)
        
        result = {
            "retire": False,
            "reason": "",
            "priority": "ضعيفه",
            "financial_analysis": {
                "purchase_cost": purchase_cost_rounded,
                "total_maintenance_cost": maintenance_costs_rounded,
                "cost_ratio": cost_ratio,
                "yearly_maintenance_avg": yearly_cost_avg
            }
        }
        
        if cost_ratio >= 60:  # تخفيف من 70% إلى 60%
            result["retire"] = True
            result["reason"] = f"تكاليف الصيانة ({maintenance_costs_rounded:.2f}) تجاوزت 60% من تكلفة الشراء ({purchase_cost_rounded:.2f})"
            result["priority"] = "عالية"
        elif cost_ratio >= 40:  # تخفيف من 50% إلى 40%
            result["retire"] = True
            result["reason"] = f"تكاليف الصيانة ({maintenance_costs_rounded:.2f}) تجاوزت 40% من تكلفة الشراء ({purchase_cost_rounded:.2f})"
            result["priority"] = "متوسطه"
        elif cost_ratio >= 30:  # تخفيف من 40% إلى 30%
            result["retire"] = False
            result["reason"] = f"تكاليف الصيانة ({maintenance_costs_rounded:.2f}) تجاوزت 30% من تكلفة الشراء ({purchase_cost_rounded:.2f})"
            result["priority"] = "ضعيفه"
        else:
            return None
        
        return result
    
    @staticmethod
    def _get_recommendations(device, evaluation_result):
        """توليد نصائح وتوصيات بناء على نتائج التقييم"""
        recommendations = []
        
        if evaluation_result["should_retire"]:
            recommendations.append("يوصى باستبدال الجهاز بدلاً من إجراء المزيد من الصيانات")
            
            # تحقق من قطع الغيار المتبقية
            spare_parts = SpareParts.query.filter_by(DeviceId=device.Id).all()
            if spare_parts:
                total_parts_value = sum(float(part.Cost) * part.Quantity for part in spare_parts)
                # تقريب قيمة قطع الغيار لأقرب رقمين عشريين
                total_parts_value = round(total_parts_value, 2)
                recommendations.append(f"يرجى ملاحظة أن هناك قطع غيار متبقية للجهاز بقيمة إجمالية {total_parts_value:.2f}")
            
            # تحقق من ساعات التشغيل
            if device.TotalOperatingHours > 0:
                cost_per_hour = float(device.PurchaseCost) / device.TotalOperatingHours
                # تقريب تكلفة الساعة لأقرب رقمين عشريين
                cost_per_hour = round(cost_per_hour, 2)
                recommendations.append(f"متوسط تكلفة الساعة الواحدة من عمر الجهاز: {cost_per_hour:.2f}")
        else:
            recommendations.append("يمكن الاستمرار في صيانة الجهاز حيث أن تكلفة الصيانة لا تزال أقل من تكلفة الاستبدال")
        
        return recommendations