from flask_restful import Resource, reqparse
from flask import jsonify, make_response, request
from .services import FutureNeedsService


class FutureNeedsResource(Resource):
    """واجهة API للاحتياجات المستقبلية من قطع الغيار"""
    
    def get(self):
        """
        الحصول على قائمة قطع الغيار المطلوب شراؤها مستقبلاً
        
        يمكن تصفية النتائج باستخدام المعلمات التالية:
        - priority: الأولوية (عالية، متوسطة، منخفضة)
        - reason: سبب الاحتياج (منخفض المخزون، قرب انتهاء الصلاحية، معدل استهلاك عالي، مطلوبة للصيانة القادمة)
        """
        # استخدام args بدلاً من RequestParser
        priority = request.args.get('priority')
        reason = request.args.get('reason')
        
        # إذا تم تحديد معلمة الأولوية
        if priority:
            if priority not in ["عالية", "متوسطة", "منخفضة"]:
                return {'status': 'error', 'message': "الأولوية غير صالحة"}, 400
            
            result = FutureNeedsService.get_parts_by_priority(priority)
            if 'error' in result:
                return {'status': 'error', 'message': result['error']}, 400
            
            response = make_response(jsonify(result))
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response
        
        # إذا تم تحديد معلمة السبب
        if reason:
            valid_reasons = ["منخفض المخزون", "قرب انتهاء الصلاحية", "معدل استهلاك عالي", "مطلوبة للصيانة القادمة"]
            if reason not in valid_reasons:
                return {'status': 'error', 'message': "السبب غير صالح"}, 400
            
            result = FutureNeedsService.get_parts_by_reason(reason)
            if 'error' in result:
                return {'status': 'error', 'message': result['error']}, 400
            
            response = make_response(jsonify(result))
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response
        
        # بدون تصفية، استرجاع كل الاحتياجات
        result = FutureNeedsService.get_future_spare_parts_needs()
        response = make_response(jsonify(result))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response
