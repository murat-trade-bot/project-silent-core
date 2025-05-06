ef get_dynamic_position_size(atr_value, base_position_pct):
    if atr_value is None:
        return base_position_pct
    if atr_value > 100:
        return base_position_pct * 0.5
    elif atr_value < 30:
        return base_position_pct * 1.5
    else:
        return base_position_pct 
