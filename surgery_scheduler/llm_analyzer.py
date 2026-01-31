class SurgeryLLMAnalyzer:
    def analyze_size(self, surgery_type):
        stype = surgery_type.upper()
        # 模擬 AI 判斷：小型術式回傳 Small (120min)，其餘 Large
        small_keywords = ["PORT-A", "REMOVAL", "TRIGGER", " biopsy", "清創"]
        if any(k in stype for k in small_keywords):
            return "Small", 120
        return "Large", 180

    def batch_analyze(self, data):
        for item in data:
            size, duration = self.analyze_size(item.get('surgery_type', ''))
            item['ai_size'] = size
            item['estimated_duration'] = duration
        return data
