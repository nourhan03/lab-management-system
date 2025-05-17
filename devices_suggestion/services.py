from model import Devices, ExperimentDevices
from sqlalchemy import and_, func, not_, or_
from extensions import db
import difflib  #

class DeviceSuggestionService:
    @staticmethod
    def get_device_suggestions(device_id):
        try:
            device = Devices.query.get(device_id)
            
            if not device:
                return False, "الجهاز غير موجود"
            
            excluded_statuses = [
                "قيد الصيانة", " قيد الصيانة", "قيد الصيانة ", " قيد الصيانة ",
                "غير متاح", " غير متاح", "غير متاح ", " غير متاح ",
                "في الصيانة", " في الصيانة", "في الصيانة ", " في الصيانة ",
                "فى الصيانة", " فى الصيانة", "فى الصيانة ", " فى الصيانة "
            ]
            
            similar_devices = Devices.query.filter(
                and_(
                    func.lower(Devices.CategoryName) == func.lower(device.CategoryName),
                    func.lower(Devices.JobDescription) == func.lower(device.JobDescription),
                    Devices.Id != device_id,
                    ~Devices.Status.in_(excluded_statuses)
                )
            ).all()
            
            if not similar_devices:
                return True, {"message": "لا توجد أجهزة مماثلة بنفس الوصف الوظيفي والفئة", "suggested_devices": []}
            
            name_similarity_matches = []
            other_similar_devices = []
            
            for d in similar_devices:
                name_similarity = difflib.SequenceMatcher(None, device.Name, d.Name).ratio()
                
                if name_similarity > 0.5:
                    name_similarity_matches.append({
                        "device": d,
                        "similarity": name_similarity
                    })
                else:
                    other_similar_devices.append(d)
            
            name_similarity_matches.sort(key=lambda x: x["similarity"], reverse=True)
            
            device_experiment_map = {}
            all_suggested_devices = []
            
            source_device_experiments = db.session.query(ExperimentDevices.ExperimentId).filter(
                ExperimentDevices.DeviceId == device_id
            ).all()
            
            source_experiment_ids = [exp[0] for exp in source_device_experiments]
            has_experiments = len(source_experiment_ids) > 0
            
            if has_experiments:
                for d in name_similarity_matches + other_similar_devices:
                    device_to_check = d["device"] if isinstance(d, dict) else d
                    device_experiments = db.session.query(ExperimentDevices.ExperimentId).filter(
                        ExperimentDevices.DeviceId == device_to_check.Id
                    ).all()
                    
                    device_experiment_ids = [exp[0] for exp in device_experiments]
                    common_experiments = [exp_id for exp_id in device_experiment_ids if exp_id in source_experiment_ids]
                    
                    if common_experiments:
                        device_experiment_map[device_to_check.Id] = common_experiments
            
            
            for match in name_similarity_matches:
                d = match["device"]
                device_info = {
                    "id": d.Id,
                    "name": d.Name,
                    "category": d.CategoryName,
                    "job_description": d.JobDescription,
                    "status": d.Status,
                    "use_recommendations": d.UseRecommendations,
                    "safety_recommendations": d.SafetyRecommendations,
                    "name_similarity": round(match["similarity"] * 100)  
                }
                
                if d.Id in device_experiment_map:
                    device_info["common_experiments"] = device_experiment_map[d.Id]
                
                all_suggested_devices.append(device_info)
            
            for d in other_similar_devices:
                device_info = {
                    "id": d.Id,
                    "name": d.Name,
                    "category": d.CategoryName,
                    "job_description": d.JobDescription,
                    "status": d.Status,
                    "use_recommendations": d.UseRecommendations,
                    "safety_recommendations": d.SafetyRecommendations
                }
                
                if d.Id in device_experiment_map:
                    device_info["common_experiments"] = device_experiment_map[d.Id]
                    all_suggested_devices.append(device_info)
            
            if has_experiments:
                for d in other_similar_devices:
                    if d.Id not in device_experiment_map:
                        all_suggested_devices.append({
                            "id": d.Id,
                            "name": d.Name,
                            "category": d.CategoryName,
                            "job_description": d.JobDescription,
                            "status": d.Status,
                            "use_recommendations": d.UseRecommendations,
                            "safety_recommendations": d.SafetyRecommendations
                        })
            
            if not all_suggested_devices:
                return True, {"message": "لا توجد أجهزة مماثلة مناسبة", "suggested_devices": []}
            
            return True, {"suggested_devices": all_suggested_devices}
            
        except Exception as e:
            return False, f"حدث خطأ أثناء البحث عن أجهزة مماثلة: {str(e)}"
