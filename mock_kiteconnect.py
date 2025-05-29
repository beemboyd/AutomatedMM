"""
Mock implementation of KiteConnect for testing
"""

class KiteConnect:
    def __init__(self, api_key):
        self.api_key = api_key
        self.access_token = None
        
    def set_access_token(self, access_token):
        self.access_token = access_token
        
    def instruments(self, exchange):
        return [
            {"tradingsymbol": "SBIN", "instrument_token": 779521},
            {"tradingsymbol": "RELIANCE", "instrument_token": 256265},
            {"tradingsymbol": "INFY", "instrument_token": 408065},
        ]
        
    def historical_data(self, token, from_date, to_date, interval):
        # Return mock historical data
        return [
            {"date": "2025-04-20T09:15:00+05:30", "open": 100, "high": 105, "low": 99, "close": 103, "volume": 1000},
            {"date": "2025-04-20T09:30:00+05:30", "open": 103, "high": 108, "low": 102, "close": 107, "volume": 1200},
            {"date": "2025-04-20T09:45:00+05:30", "open": 107, "high": 110, "low": 105, "close": 108, "volume": 1300},
            {"date": "2025-04-20T10:00:00+05:30", "open": 108, "high": 112, "low": 108, "close": 110, "volume": 1400},
            {"date": "2025-04-20T10:15:00+05:30", "open": 110, "high": 115, "low": 109, "close": 114, "volume": 1500},
            {"date": "2025-04-20T10:30:00+05:30", "open": 114, "high": 118, "low": 113, "close": 116, "volume": 1600},
            {"date": "2025-04-20T10:45:00+05:30", "open": 116, "high": 120, "low": 115, "close": 118, "volume": 1700},
            {"date": "2025-04-20T11:00:00+05:30", "open": 118, "high": 122, "low": 117, "close": 120, "volume": 1800},
            {"date": "2025-04-20T11:15:00+05:30", "open": 120, "high": 125, "low": 119, "close": 122, "volume": 1900},
            {"date": "2025-04-20T11:30:00+05:30", "open": 122, "high": 126, "low": 121, "close": 125, "volume": 2000},
            {"date": "2025-04-20T11:45:00+05:30", "open": 125, "high": 128, "low": 124, "close": 127, "volume": 2100},
            {"date": "2025-04-20T12:00:00+05:30", "open": 127, "high": 130, "low": 126, "close": 129, "volume": 2200},
            {"date": "2025-04-20T12:15:00+05:30", "open": 129, "high": 132, "low": 128, "close": 131, "volume": 2300},
            {"date": "2025-04-20T12:30:00+05:30", "open": 131, "high": 134, "low": 130, "close": 132, "volume": 2400},
            {"date": "2025-04-20T12:45:00+05:30", "open": 132, "high": 135, "low": 131, "close": 133, "volume": 2500},
            {"date": "2025-04-20T13:00:00+05:30", "open": 133, "high": 136, "low": 132, "close": 134, "volume": 2600},
            {"date": "2025-04-20T13:15:00+05:30", "open": 134, "high": 137, "low": 133, "close": 135, "volume": 2700},
            {"date": "2025-04-20T13:30:00+05:30", "open": 135, "high": 138, "low": 134, "close": 136, "volume": 2800},
            {"date": "2025-04-20T13:45:00+05:30", "open": 136, "high": 139, "low": 135, "close": 137, "volume": 2900},
            {"date": "2025-04-20T14:00:00+05:30", "open": 137, "high": 140, "low": 136, "close": 138, "volume": 3000},
            {"date": "2025-04-20T14:15:00+05:30", "open": 138, "high": 141, "low": 137, "close": 139, "volume": 3100},
            {"date": "2025-04-20T14:30:00+05:30", "open": 139, "high": 142, "low": 138, "close": 140, "volume": 3200},
            {"date": "2025-04-20T14:45:00+05:30", "open": 140, "high": 143, "low": 139, "close": 141, "volume": 3300},
            {"date": "2025-04-20T15:00:00+05:30", "open": 141, "high": 144, "low": 140, "close": 142, "volume": 3400},
            {"date": "2025-04-20T15:15:00+05:30", "open": 142, "high": 145, "low": 141, "close": 143, "volume": 3500},
            {"date": "2025-04-20T15:30:00+05:30", "open": 143, "high": 146, "low": 142, "close": 144, "volume": 3600},
            {"date": "2025-04-21T09:15:00+05:30", "open": 144, "high": 147, "low": 143, "close": 145, "volume": 3700},
            {"date": "2025-04-21T09:30:00+05:30", "open": 145, "high": 148, "low": 144, "close": 146, "volume": 3800},
            {"date": "2025-04-21T09:45:00+05:30", "open": 146, "high": 149, "low": 145, "close": 147, "volume": 3900},
            {"date": "2025-04-21T10:00:00+05:30", "open": 147, "high": 150, "low": 146, "close": 148, "volume": 4000},
            {"date": "2025-04-21T10:15:00+05:30", "open": 148, "high": 151, "low": 147, "close": 149, "volume": 4100},
            {"date": "2025-04-21T10:30:00+05:30", "open": 149, "high": 152, "low": 148, "close": 150, "volume": 4200},
            {"date": "2025-04-21T10:45:00+05:30", "open": 150, "high": 153, "low": 149, "close": 151, "volume": 4300},
            {"date": "2025-04-21T11:00:00+05:30", "open": 151, "high": 154, "low": 150, "close": 152, "volume": 4400},
            {"date": "2025-04-21T11:15:00+05:30", "open": 152, "high": 155, "low": 151, "close": 153, "volume": 4500},
            {"date": "2025-04-21T11:30:00+05:30", "open": 153, "high": 156, "low": 152, "close": 154, "volume": 4600},
            {"date": "2025-04-21T11:45:00+05:30", "open": 154, "high": 157, "low": 153, "close": 155, "volume": 4700},
            {"date": "2025-04-21T12:00:00+05:30", "open": 155, "high": 158, "low": 154, "close": 156, "volume": 4800},
            {"date": "2025-04-21T12:15:00+05:30", "open": 156, "high": 159, "low": 155, "close": 157, "volume": 4900},
            {"date": "2025-04-21T12:30:00+05:30", "open": 157, "high": 160, "low": 156, "close": 158, "volume": 5000},
            {"date": "2025-04-21T12:45:00+05:30", "open": 158, "high": 161, "low": 157, "close": 159, "volume": 5100},
            {"date": "2025-04-21T13:00:00+05:30", "open": 159, "high": 162, "low": 158, "close": 160, "volume": 5200},
            {"date": "2025-04-21T13:15:00+05:30", "open": 160, "high": 163, "low": 159, "close": 161, "volume": 5300},
            {"date": "2025-04-21T13:30:00+05:30", "open": 161, "high": 164, "low": 160, "close": 162, "volume": 5400},
            {"date": "2025-04-21T13:45:00+05:30", "open": 162, "high": 165, "low": 161, "close": 163, "volume": 5500},
            {"date": "2025-04-21T14:00:00+05:30", "open": 163, "high": 166, "low": 162, "close": 164, "volume": 5600},
            {"date": "2025-04-21T14:15:00+05:30", "open": 164, "high": 167, "low": 163, "close": 165, "volume": 5700},
            {"date": "2025-04-21T14:30:00+05:30", "open": 165, "high": 168, "low": 164, "close": 166, "volume": 5800},
            {"date": "2025-04-21T14:45:00+05:30", "open": 166, "high": 169, "low": 165, "close": 167, "volume": 5900},
            {"date": "2025-04-21T15:00:00+05:30", "open": 167, "high": 170, "low": 166, "close": 168, "volume": 6000},
            {"date": "2025-04-21T15:15:00+05:30", "open": 168, "high": 171, "low": 167, "close": 169, "volume": 6100},
            {"date": "2025-04-21T15:30:00+05:30", "open": 169, "high": 172, "low": 168, "close": 170, "volume": 6200},
            {"date": "2025-04-22T09:15:00+05:30", "open": 170, "high": 173, "low": 169, "close": 171, "volume": 6300},
            {"date": "2025-04-22T09:30:00+05:30", "open": 171, "high": 174, "low": 170, "close": 172, "volume": 6400},
            {"date": "2025-04-22T09:45:00+05:30", "open": 172, "high": 175, "low": 171, "close": 173, "volume": 6500},
            {"date": "2025-04-22T10:00:00+05:30", "open": 173, "high": 176, "low": 172, "close": 174, "volume": 6600},
            {"date": "2025-04-22T10:15:00+05:30", "open": 174, "high": 177, "low": 173, "close": 175, "volume": 6700},
            {"date": "2025-04-22T10:30:00+05:30", "open": 175, "high": 178, "low": 174, "close": 176, "volume": 6800},
            {"date": "2025-04-22T10:45:00+05:30", "open": 176, "high": 179, "low": 175, "close": 177, "volume": 6900},
            {"date": "2025-04-22T11:00:00+05:30", "open": 177, "high": 180, "low": 176, "close": 178, "volume": 7000},
        ]
    
    def ltp(self, instruments):
        # Return mock last traded price
        if isinstance(instruments, str):
            exchange, symbol = instruments.split(":")
            return {instruments: {"last_price": 178.50, "instrument_token": 779521}}
        elif isinstance(instruments, list):
            result = {}
            for instrument in instruments:
                exchange, symbol = instrument.split(":")
                result[instrument] = {"last_price": 178.50, "instrument_token": 779521}
            return result
    
    def positions(self):
        return {
            "net": [
                {
                    "tradingsymbol": "SBIN",
                    "exchange": "NSE",
                    "instrument_token": 779521,
                    "product": "MIS",
                    "quantity": 10,
                    "average_price": 170.0,
                }
            ]
        }
    
    def orders(self):
        return [
            {
                "status": "COMPLETE",
                "tradingsymbol": "SBIN",
                "exchange": "NSE",
                "instrument_token": 779521,
                "product": "MIS",
                "quantity": 10,
                "average_price": 170.0,
            }
        ]
    
    def place_order(self, variety, exchange, tradingsymbol, transaction_type, quantity, order_type, product, validity):
        return "123456"  # Mock order ID

class KiteTicker:
    MODE_FULL = "full"
    
    def __init__(self, api_key, access_token):
        self.api_key = api_key
        self.access_token = access_token
        self.on_ticks = None
        self.on_connect = None
        self.on_close = None
        self.on_error = None
        
    def connect(self, threaded=False):
        if self.on_connect:
            self.on_connect(self, {"status": "connected"})
            
    def subscribe(self, tokens):
        # Simulate receiving ticks after subscription
        if self.on_ticks:
            ticks = [
                {
                    "instrument_token": tokens[0],
                    "last_price": 178.50,
                }
            ]
            self.on_ticks(self, ticks)
            
    def set_mode(self, mode, tokens):
        pass
        
    def close(self):
        if self.on_close:
            self.on_close(self, 1000, "Normal closure")