# minimal_executor.py

from typing import Dict

class Executor:
    """
    Çok basit stub: verilen aksiyonu alır, loglayıp True döner.
    """
    def execute(self, action: str, data: Dict) -> bool:
        # Burada gerçek API çağrısı yerine basit bir print
        print(f"Executing action: {action} with data: {data}")
        return True
