from datetime import datetime, timedelta
from sqlalchemy import func, case, desc
from model import Devices, SpareParts, Maintenances, db

class FutureNeedsService:
    """خدمة تحديد الاحتياجات المستقبلية من قطع الغيار"""
    
    @staticmethod
    def get_future_spare_parts_needs():
        """
        تحديد قطع الغيار المطلوب شراؤها مستقبلاً بناءً على المعايير التالية:
        1. قطع الغيار منخفضة المخزون
        2. قطع الغيار التي تقارب انتهاء الصلاحية
        3. قطع الغيار ذات معدل الاستهلاك العالي
        4. قطع الغيار المطلوبة للصيانات القادمة
        """
        # تعريف المتغيرات الزمنية
        today = datetime.now()
        one_month = today + timedelta(days=30)
        two_months = today + timedelta(days=60)
        
        # 1. قطع الغيار منخفضة المخزون
        low_stock_parts = SpareParts.query.filter(
            SpareParts.Quantity <= (SpareParts.MinimumQuantity * 1.2)  # أقل من أو يساوي الحد الأدنى + 20%
        ).all()
        
        # 2. قطع الغيار التي تقارب انتهاء الصلاحية
        expiring_parts = SpareParts.query.filter(
            SpareParts.ExpiryDate.isnot(None),
            SpareParts.ExpiryDate <= two_months,
            SpareParts.Quantity > 0  # فقط القطع التي لا زال هناك مخزون منها
        ).all()
        
        # 3. قطع الغيار ذات معدل الاستهلاك العالي
        high_consumption_parts = []
        parts_with_restock_date = SpareParts.query.filter(
            SpareParts.LastRestockDate.isnot(None),
            SpareParts.Quantity > 0
        ).all()
        
        for part in parts_with_restock_date:
            if part.LastRestockDate:
                days_since_restock = (today - part.LastRestockDate).days
                if days_since_restock > 0:
                    # تقدير الكمية الأصلية عند آخر تخزين
                    # (هذا تقدير بسيط، قد تحتاج لتحسينه إذا كان لديك بيانات أكثر دقة)
                    estimated_original_quantity = part.Quantity * 1.5  # تقدير بسيط
                    consumed_quantity = estimated_original_quantity - part.Quantity
                    
                    # حساب معدل الاستهلاك اليومي
                    daily_consumption_rate = consumed_quantity / days_since_restock if days_since_restock > 0 else 0
                    
                    # تقدير عدد الأيام حتى نفاد المخزون
                    days_until_empty = part.Quantity / daily_consumption_rate if daily_consumption_rate > 0 else 999
                    
                    # إذا كان سينفد في أقل من 45 يوم، أضفه للقائمة
                    if days_until_empty <= 45:
                        part.estimated_days = round(days_until_empty, 2)
                        part.consumption_rate = round(daily_consumption_rate, 2)
                        high_consumption_parts.append(part)
        
        # 4. قطع الغيار المطلوبة للصيانات القادمة
        # الحصول على الصيانات المجدولة في المستقبل القريب
        upcoming_maintenances = Maintenances.query.filter(
            Maintenances.Status.in_(["مجدولة", "قيد التنفيذ", "تم الجدولة"]),
            Maintenances.SchedulingAt > today,
            Maintenances.SchedulingAt <= two_months
        ).all()
        
        # قطع الغيار المرتبطة بالأجهزة التي لديها صيانات قادمة
        maintenance_related_parts = []
        for maintenance in upcoming_maintenances:
            if maintenance.DeviceId:
                device_parts = SpareParts.query.filter_by(DeviceId=maintenance.DeviceId).all()
                for part in device_parts:
                    # تجنب التكرار
                    if part not in maintenance_related_parts:
                        maintenance_related_parts.append(part)
        
        # دمج وترتيب النتائج
        all_parts_list = []
        
        # 1. إضافة قطع الغيار منخفضة المخزون مع التفاصيل
        for part in low_stock_parts:
            stock_percentage = (part.Quantity / part.MinimumQuantity * 100) if part.MinimumQuantity > 0 else 0
            
            # تحديد مستوى الأولوية بناءً على نسبة المخزون
            if part.Quantity <= part.MinimumQuantity:
                priority = "عالية"
                days_to_action = 0  # بحاجة للشراء فوراً
            else:
                priority = "متوسطة"
                # تقدير عدد الأيام قبل الوصول للحد الأدنى (تقدير بسيط)
                days_to_action = round((part.Quantity - part.MinimumQuantity) * 2, 2)
            
            # حساب الكمية المقترح شراؤها
            suggested_quantity = max(part.MinimumQuantity * 2 - part.Quantity, 5)
            
            part_info = {
                "id": part.PartId,
                "name": part.PartName,
                "current_quantity": part.Quantity,
                "minimum_quantity": part.MinimumQuantity,
                "device_id": part.DeviceId,
                "device_name": FutureNeedsService._get_device_name(part.DeviceId),
                "lab_id": part.LaboratoryId,
                "unit": part.Unit,
                "cost": round(float(part.Cost), 2),
                "expiry_date": part.ExpiryDate.strftime('%Y-%m-%d') if part.ExpiryDate else None,
                "priority": priority,
                "reason": "منخفض المخزون",
                "stock_percentage": round(stock_percentage, 2),
                "days_to_action": days_to_action,
                "suggested_quantity": suggested_quantity,
                "total_cost_estimation": round(float(part.Cost) * suggested_quantity, 2)
            }
            all_parts_list.append(part_info)
        
        # 2. إضافة قطع الغيار التي تقارب انتهاء الصلاحية
        for part in expiring_parts:
            # تجنب التكرار
            if part.PartId not in [p["id"] for p in all_parts_list]:
                days_to_expiry = (part.ExpiryDate - today).days if part.ExpiryDate else 999
                
                # تحديد الأولوية بناءً على قرب انتهاء الصلاحية
                if days_to_expiry <= 15:
                    priority = "عالية"
                elif days_to_expiry <= 30:
                    priority = "متوسطة"
                else:
                    priority = "منخفضة"
                
                # الكمية المقترح شراؤها (لاستبدال المخزون الحالي)
                suggested_quantity = max(part.Quantity, part.MinimumQuantity)
                
                part_info = {
                    "id": part.PartId,
                    "name": part.PartName,
                    "current_quantity": part.Quantity,
                    "minimum_quantity": part.MinimumQuantity,
                    "device_id": part.DeviceId,
                    "device_name": FutureNeedsService._get_device_name(part.DeviceId),
                    "lab_id": part.LaboratoryId,
                    "unit": part.Unit,
                    "cost": round(float(part.Cost), 2),
                    "expiry_date": part.ExpiryDate.strftime('%Y-%m-%d') if part.ExpiryDate else None,
                    "priority": priority,
                    "reason": "قرب انتهاء الصلاحية",
                    "days_to_action": days_to_expiry,
                    "suggested_quantity": suggested_quantity,
                    "total_cost_estimation": round(float(part.Cost) * suggested_quantity, 2)
                }
                all_parts_list.append(part_info)
        
        # 3. إضافة قطع الغيار ذات معدل الاستهلاك العالي
        for part in high_consumption_parts:
            # تجنب التكرار
            if part.PartId not in [p["id"] for p in all_parts_list]:
                days_to_empty = getattr(part, 'estimated_days', 999)
                
                # تحديد الأولوية بناءً على سرعة نفاد المخزون
                if days_to_empty <= 15:
                    priority = "عالية"
                elif days_to_empty <= 30:
                    priority = "متوسطة"
                else:
                    priority = "منخفضة"
                
                # الكمية المقترح شراؤها بناءً على معدل الاستهلاك
                consumption_rate = getattr(part, 'consumption_rate', 0.1)
                suggested_quantity = max(round(consumption_rate * 60), part.MinimumQuantity)  # شراء ما يكفي لمدة شهرين
                
                part_info = {
                    "id": part.PartId,
                    "name": part.PartName,
                    "current_quantity": part.Quantity,
                    "minimum_quantity": part.MinimumQuantity,
                    "device_id": part.DeviceId,
                    "device_name": FutureNeedsService._get_device_name(part.DeviceId),
                    "lab_id": part.LaboratoryId,
                    "unit": part.Unit,
                    "cost": round(float(part.Cost), 2),
                    "expiry_date": part.ExpiryDate.strftime('%Y-%m-%d') if part.ExpiryDate else None,
                    "priority": priority,
                    "reason": "معدل استهلاك عالي",
                    "days_to_action": days_to_empty,
                    "consumption_rate": getattr(part, 'consumption_rate', 0),
                    "suggested_quantity": suggested_quantity,
                    "total_cost_estimation": round(float(part.Cost) * suggested_quantity, 2)
                }
                all_parts_list.append(part_info)
        
        # 4. إضافة قطع الغيار المطلوبة للصيانات القادمة
        for part in maintenance_related_parts:
            # تجنب التكرار
            if part.PartId not in [p["id"] for p in all_parts_list]:
                # تحديد حاجة الصيانة للقطع بناءً على المخزون الحالي
                if part.Quantity < part.MinimumQuantity:
                    priority = "عالية"
                    days_to_action = 0
                elif part.Quantity < part.MinimumQuantity * 1.5:
                    priority = "متوسطة"
                    days_to_action = 15
                else:
                    priority = "منخفضة"
                    days_to_action = 30
                
                # الكمية المقترح شراؤها (الحد الأدنى + إضافة للصيانة)
                suggested_quantity = max(part.MinimumQuantity - part.Quantity + 3, 3)
                
                part_info = {
                    "id": part.PartId,
                    "name": part.PartName,
                    "current_quantity": part.Quantity,
                    "minimum_quantity": part.MinimumQuantity,
                    "device_id": part.DeviceId,
                    "device_name": FutureNeedsService._get_device_name(part.DeviceId),
                    "lab_id": part.LaboratoryId,
                    "unit": part.Unit,
                    "cost": round(float(part.Cost), 2),
                    "expiry_date": part.ExpiryDate.strftime('%Y-%m-%d') if part.ExpiryDate else None,
                    "priority": priority,
                    "reason": "مطلوبة للصيانة القادمة",
                    "days_to_action": days_to_action,
                    "suggested_quantity": suggested_quantity,
                    "total_cost_estimation": round(float(part.Cost) * suggested_quantity, 2)
                }
                all_parts_list.append(part_info)
        
        # ترتيب القائمة النهائية حسب الأولوية ثم حسب عدد الأيام للإجراء
        priority_order = {"عالية": 0, "متوسطة": 1, "منخفضة": 2}
        final_sorted_list = sorted(all_parts_list, 
                                   key=lambda x: (priority_order.get(x["priority"], 3), x["days_to_action"]))
        
        # إحصائيات إجمالية
        total_parts_needed = len(final_sorted_list)
        total_estimated_cost = sum(item["total_cost_estimation"] for item in final_sorted_list)
        high_priority_count = sum(1 for item in final_sorted_list if item["priority"] == "عالية")
        
        # تجميع النتائج
        response = {
            "summary": {
                "total_parts_needed": total_parts_needed,
                "high_priority_count": high_priority_count,
                "total_estimated_cost": round(total_estimated_cost, 2),
                "date_generated": today.strftime('%Y-%m-%d')
            },
            "parts_to_purchase": final_sorted_list
        }
        
        return response
    
    @staticmethod
    def _get_device_name(device_id):
        """الحصول على اسم الجهاز من معرفه"""
        device = Devices.query.filter_by(Id=device_id).first()
        return device.Name if device else "غير معروف"
    
    @staticmethod
    def get_parts_by_priority(priority):
        """استرجاع قطع الغيار المطلوبة حسب الأولوية"""
        if priority not in ["عالية", "متوسطة", "منخفضة"]:
            return {"error": "الأولوية غير صالحة"}
        
        all_needs = FutureNeedsService.get_future_spare_parts_needs()
        filtered_parts = [part for part in all_needs["parts_to_purchase"] if part["priority"] == priority]
        
        # تحديث الملخص
        total_estimated_cost = sum(item["total_cost_estimation"] for item in filtered_parts)
        
        result = {
            "summary": {
                "total_parts_needed": len(filtered_parts),
                "high_priority_count": len(filtered_parts) if priority == "عالية" else 0,
                "total_estimated_cost": round(total_estimated_cost, 2),
                "date_generated": datetime.now().strftime('%Y-%m-%d'),
                "filter_applied": f"الأولوية: {priority}"
            },
            "parts_to_purchase": filtered_parts
        }
        
        return result
    
    @staticmethod
    def get_parts_by_reason(reason):
        """استرجاع قطع الغيار المطلوبة حسب السبب"""
        valid_reasons = ["منخفض المخزون", "قرب انتهاء الصلاحية", "معدل استهلاك عالي", "مطلوبة للصيانة القادمة"]
        
        if reason not in valid_reasons:
            return {"error": "السبب غير صالح"}
        
        all_needs = FutureNeedsService.get_future_spare_parts_needs()
        filtered_parts = [part for part in all_needs["parts_to_purchase"] if part["reason"] == reason]
        
        # تحديث الملخص
        total_estimated_cost = sum(item["total_cost_estimation"] for item in filtered_parts)
        high_priority_count = sum(1 for item in filtered_parts if item["priority"] == "عالية")
        
        result = {
            "summary": {
                "total_parts_needed": len(filtered_parts),
                "high_priority_count": high_priority_count,
                "total_estimated_cost": round(total_estimated_cost, 2),
                "date_generated": datetime.now().strftime('%Y-%m-%d'),
                "filter_applied": f"السبب: {reason}"
            },
            "parts_to_purchase": filtered_parts
        }
        
        return result 