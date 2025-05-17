from flask_restful import Resource
from devices_suggestion.services import DeviceSuggestionService

class SuggestDeviceResource(Resource):
    def get(self, device_id):
        success, result = DeviceSuggestionService.get_device_suggestions(device_id)
        
        if not success:
            return {"message": result}, 404 if "غير موجود" in result else 500
            
        return result, 200
