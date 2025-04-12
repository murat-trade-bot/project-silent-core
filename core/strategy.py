class Strategy:
    def __init__(self):
        self.current_mode = "neutral"
        self.risk_level = "neutral"
        self.liquidity_pressure = "neutral"
        self.rsi_15m = None
        self.macd_15m = None
        self.macd_signal_15m = None
        self.rsi_1h = None
        self.macd_1h = None
        self.macd_signal_1h = None
        self.atr = None

    def update_context(self, mode, risk, pressure,
                       rsi_15m=None, macd_15m=None, macd_signal_15m=None,
                       rsi_1h=None, macd_1h=None, macd_signal_1h=None,
                       atr=None):
        self.current_mode = mode
        self.risk_level = risk
        self.liquidity_pressure = pressure
        self.rsi_15m = rsi_15m
        self.macd_15m = macd_15m
        self.macd_signal_15m = macd_signal_15m
        self.rsi_1h = rsi_1h
        self.macd_1h = macd_1h
        self.macd_signal_1h = macd_signal_1h
        self.atr = atr

    def decide_trade(self):
        score = 0
        reasons = []

        if self.risk_level == "extreme_risk":
            score -= 2
            reasons.append("ExtremeRisk")
        if self.liquidity_pressure == "buy_pressure":
            score += 1
            reasons.append("BuyPressure")
        elif self.liquidity_pressure == "sell_pressure":
            score -= 1
            reasons.append("SellPressure")

        if self.rsi_1h is not None:
            if self.rsi_1h > 70:
                score -= 1
                reasons.append("RSI1h>70")
            elif self.rsi_1h < 30:
                score += 1
                reasons.append("RSI1h<30")

        if self.macd_1h is not None and self.macd_signal_1h is not None:
            if self.macd_1h > self.macd_signal_1h:
                score += 1
                reasons.append("MACD1h>Signal")
            else:
                score -= 1
                reasons.append("MACD1h<Signal")

        if self.rsi_15m is not None:
            if self.rsi_15m < 30:
                score += 1
                reasons.append("RSI15m<30")
            elif self.rsi_15m > 70:
                score -= 1
                reasons.append("RSI15m>70")

        if self.macd_15m is not None and self.macd_signal_15m is not None:
            if self.macd_15m > self.macd_signal_15m:
                score += 1
                reasons.append("MACD15m>Signal")
            else:
                score -= 1
                reasons.append("MACD15m<Signal")

        if self.atr is not None and self.atr < 50:
            score *= 0.5
            reasons.append("LowVolatility")

        if score >= 2:
            return {"action": "BUY", "reason": "|".join(reasons)}
        elif score <= -2:
            return {"action": "SELL", "reason": "|".join(reasons)}
        else:
            return {"action": "HOLD", "reason": "|".join(reasons)} 