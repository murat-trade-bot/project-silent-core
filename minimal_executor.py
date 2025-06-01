class Executor:
    def execute(self, action, context):
        """
        Gerçekçi bir işlem simülasyonu için:
        - action: 'BUY', 'SELL', 'HOLD'
        - context: fiyat, bakiye, pozisyon, coin adı vb.
        Burada loglama, işlem geçmişi kaydı veya ileri seviye analizler yapılabilir.
        """
        print(f"{context.get('symbol')} | {action} | Fiyat: {context.get('price'):.2f} | Pozisyon: {context.get('position'):.6f} | Bakiye: {context.get('balance'):.2f}")