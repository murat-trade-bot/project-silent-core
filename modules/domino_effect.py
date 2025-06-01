from core.logger import BotLogger

logger = BotLogger()

def detect_domino_effect(prices, threshold=50):
    """
    Son 10 fiyat içindeki ani büyük değişimi (domino etkisi) tespit eder.
    prices: Fiyatların listesi (float/int)
    threshold: Domino etkisi için mutlak değişim eşiği (varsayılan: 50)
    """
    if len(prices) < 10:
        logger.warning("DominoEffect: Yeterli veri yok (en az 10 fiyat gerekli).")
        return False
    change = prices[-1] - prices[-10]
    if abs(change) > threshold:
        logger.info(f"DominoEffect: Domino etkisi tespit edildi! Değişim: {change}")
        return True
    logger.info(f"DominoEffect: Domino etkisi yok. Değişim: {change}")
    return False