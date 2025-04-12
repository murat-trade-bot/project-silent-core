import requests

class GlobalRiskAnalyzer:
    def __init__(self):
        self.url = "https://api.alternative.me/fng/"

    def fetch_fear_index(self):
        try:
            r = requests.get(self.url, timeout=5)
            data = r.json()
            return int(data["data"][0]["value"])
        except:
            return None

    def evaluate_risk_level(self):
        fear = self.fetch_fear_index()
        if fear is None:
            return "neutral"
        if fear < 25:
            return "extreme_risk"
        elif fear < 50:
            return "high_risk"
        elif fear < 75:
            return "moderate"
        else:
            return "low_risk"

    def composite_risk_score(self):
        score = self.fetch_fear_index() or 50
        return score 