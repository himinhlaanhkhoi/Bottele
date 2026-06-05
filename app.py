import asyncio
import websockets
import json
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, jsonify
from flask_cors import CORS
import os
import signal
import sys
import socket
import requests
import re

app = Flask(__name__)
CORS(app)
PORT = int(os.environ.get('PORT', 1234))

# Global variables
current_result = {
    "phien": None,
    "xuc_xac_1": None,
    "xuc_xac_2": None,
    "xuc_xac_3": None,
    "tong": None,
    "ket_qua": "",
    "thoi_gian": ""
}

current_session_id = None
ws_connection = None
reconnect_delay = 2.5
start_time = time.time()
websocket_running = True

# Hàm lấy thời gian Việt Nam (UTC+7)
def get_vietnam_time():
    utc7_time = datetime.utcnow() + timedelta(hours=7)
    return utc7_time.strftime("%d-%m-%Y %H:%M:%S") + " UTC+7"

def parse_token_data(token_text):
    """Parse token data từ file token.txt"""
    try:
        info_match = re.search(r'"info"\x07([^"]+?)"?', token_text)
        if info_match:
            info_str = info_match.group(1)
            info_str = info_str.replace('\x04', '').replace('\x07', '').replace('\x05', '').replace('\x06', '')
            info_data = json.loads(info_str)
            return info_data
        
        json_match = re.search(r'\{[^{}]*"ipAddress"[^{}]*\}', token_text)
        if json_match:
            return json.loads(json_match.group())
        
        return None
    except Exception as e:
        print(f"[❌] Lỗi parse token: {e}")
        return None

def load_token():
    """Load token từ file token.txt"""
    try:
        with open('token.txt', 'r', encoding='utf-8') as f:
            token_data = f.read().strip()
        
        if not token_data:
            print("[❌] File token.txt trống")
            return None
        
        parsed_data = parse_token_data(token_data)
        if parsed_data:
            print("[✅] Đã load token từ token.txt")
            return parsed_data
        else:
            print("[❌] Không thể parse token từ token.txt")
            return None
            
    except FileNotFoundError:
        print("[❌] Không tìm thấy file token.txt")
        return None
    except Exception as e:
        print(f"[❌] Lỗi đọc token.txt: {e}")
        return None

# Load token data
TOKEN_DATA = load_token()

if TOKEN_DATA:
    WEBSOCKET_URL = f"wss://websocket.azhkthg1.net/websocket?token={TOKEN_DATA.get('wsToken', '')}"
    WS_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Origin": "https://play.sun.pw"
    }
    
    initial_messages = [
        [
            1,
            "MiniGame",
            TOKEN_DATA.get('username', 'GM_quapotjz'),
            "quapit",
            {
                "signature": "05915B436159B8F4E4DFF537639BD014D54EBEFA18CF62A8EB205B4074010AD72AEA9A780D5A8A4E1BD59BBBAFE03902C594B5DA56FD60D099F1FDDCCD48385FCC2760B5B0B4B8E75D39B8E40DF8CB7C01EA58DBEDA32805927473AB71FA9B798B0C2EDC445C3E36E47EF0AAFAD45601D99AAD1EC642FD2B63573A0401D6EC69",
                "expireIn": TOKEN_DATA.get('timestamp', 1774138177205),
                "wsToken": TOKEN_DATA.get('wsToken', ''),
                "accessToken": "7e9a9ecbff1b4a6393b48346f6d8b709",
                "message": "Thành công",
                "refreshToken": TOKEN_DATA.get('refreshToken', ''),
                "info": TOKEN_DATA
            }
        ],
        [6, "MiniGame", "taixiuPlugin", {"cmd": 1005}],
        [6, "MiniGame", "lobbyPlugin", {"cmd": 10001}]
    ]
else:
    print("[❌] Không thể load token, sử dụng token mặc định (có thể không hoạt động)")
    WEBSOCKET_URL = "wss://websocket.azhkthg1.net/websocket?token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJnZW5kZXIiOjAsImNhblZpZXdTdGF0IjpmYWxzZSwiZGlzcGxheU5hbWUiOiJsb2xtYW1heXN1MTIiLCJib3QiOjAsImlzTWVyY2hhbnQiOmZhbHNlLCJ2ZXJpZmllZEJhbmtBY2NvdW50IjpmYWxzZSwicGxheUV2ZW50TG9iYnkiOmZhbHNlLCJjdXN0b21lcklkIjozMzkxMDEyNTEsImFmZklkIjoiR0VNV0lOIiwiYmFubmVkIjpmYWxzZSwiYnJhbmQiOiJnZW0iLCJlbWFpbCI6IiIsInRpbWVzdGFtcCI6MTc3NDEzODE3NzIwNCwibG9ja0dhbWVzIjpbXSwiYW1vdW50IjowLCJsb2NrQ2hhdCI6ZmFsc2UsInBob25lVmVyaWZpZWQiOmZhbHNlLCJpcEFkZHJlc3MiOiIyNDA1OjQ4MDI6NGU0Mjo0MTcwOjcxMDQ6YjY0Njo2Nzg5Ojg2NDgiLCJtdXRlIjpmYWxzZSwiYXZhdGFyIjoiaHR0cHM6Ly9pbWFnZXMuc3dpbnNob3AubmV0L2ltYWdlcy9hdmF0YXIvYXZhdGFyXzA5LnBuZyIsInBsYXRmb3JtSWQiOjQsInVzZXJJZCI6ImEyOGEwZjA2LWU4OGYtNDRiNy1hMjY4LTVmNmRhZDk0OWZiZiIsImVtYWlsVmVyaWZpZWQiOm51bGwsInJlZ1RpbWUiOjE3NzMxMDY2NDkxOTksInBob25lIjoiIiwiZGVwb3NpdCI6ZmFsc2UsInVzZXJuYW1lIjoiR01fcXVhcG90anoifQ.3ycgvK1-PwRpBqANZJ3li00kpuzV6Ike6ZjYPthf3X0"
    WS_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Origin": "https://play.sun.pw"
    }
    initial_messages = [
        [
            1,
            "MiniGame",
            "GM_quapotjz",
            "quapit",
            {
                "signature": "05915B436159B8F4E4DFF537639BD014D54EBEFA18CF62A8EB205B4074010AD72AEA9A780D5A8A4E1BD59BBBAFE03902C594B5DA56FD60D099F1FDDCCD48385FCC2760B5B0B4B8E75D39B8E40DF8CB7C01EA58DBEDA32805927473AB71FA9B798B0C2EDC445C3E36E47EF0AAFAD45601D99AAD1EC642FD2B63573A0401D6EC69",
                "expireIn": 1774138177205,
                "wsToken": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJnZW5kZXIiOjAsImNhblZpZXdTdGF0IjpmYWxzZSwiZGlzcGxheU5hbWUiOiJsb2xtYW1heXN1MTIiLCJib3QiOjAsImlzTWVyY2hhbnQiOmZhbHNlLCJ2ZXJpZmllZEJhbmtBY2NvdW50IjpmYWxzZSwicGxheUV2ZW50TG9iYnkiOmZhbHNlLCJjdXN0b21lcklkIjozMzkxMDEyNTEsImFmZklkIjoiR0VNV0lOIiwiYmFubmVkIjpmYWxzZSwiYnJhbmQiOiJnZW0iLCJlbWFpbCI6IiIsInRpbWVzdGFtcCI6MTc3NDEzODE3NzIwNCwibG9ja0dhbWVzIjpbXSwiYW1vdW50IjowLCJsb2NrQ2hhdCI6ZmFsc2UsInBob25lVmVyaWZpZWQiOmZhbHNlLCJpcEFkZHJlc3MiOiIyNDA1OjQ4MDI6NGU0Mjo0MTcwOjcxMDQ6YjY0Njo2Nzg5Ojg2NDgiLCJtdXRlIjpmYWxzZSwiYXZhdGFyIjoiaHR0cHM6Ly9pbWFnZXMuc3dpbnNob3AubmV0L2ltYWdlcy9hdmF0YXIvYXZhdGFyXzA5LnBuZyIsInBsYXRmb3JtSWQiOjQsInVzZXJJZCI6ImEyOGEwZjA2LWU4OGYtNDRiNy1hMjY4LTVmNmRhZDk0OWZiZiIsImVtYWlsVmVyaWZpZWQiOm51bGwsInJlZ1RpbWUiOjE3NzMxMDY2NDkxOTksInBob25lIjoiIiwiZGVwb3NpdCI6ZmFsc2UsInVzZXJuYW1lIjoiR01fcXVhcG90anoifQ.3ycgvK1-PwRpBqANZJ3li00kpuzV6Ike6ZjYPthf3X0",
                "accessToken": "7e9a9ecbff1b4a6393b48346f6d8b709",
                "message": "Thành công",
                "refreshToken": "950f5b9974dd4f4c982a3681af9acbc7.f0d252e72ee64f07bd5819d6ca54bba1",
                "info": {
                    "ipAddress": "2405:4802:4e42:4170:7104:b646:6789:8648",
                    "wsToken": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJnZW5kZXIiOjAsImNhblZpZXdTdGF0IjpmYWxzZSwiZGlzcGxheU5hbWUiOiJsb2xtYW1heXN1MTIiLCJib3QiOjAsImlzTWVyY2hhbnQiOmZhbHNlLCJ2ZXJpZmllZEJhbmtBY2NvdW50IjpmYWxzZSwicGxheUV2ZW50TG9iYnkiOmZhbHNlLCJjdXN0b21lcklkIjozMzkxMDEyNTEsImFmZklkIjoiR0VNV0lOIiwiYmFubmVkIjpmYWxzZSwiYnJhbmQiOiJnZW0iLCJlbWFpbCI6IiIsInRpbWVzdGFtcCI6MTc3NDEzODE3NzIwNCwibG9ja0dhbWVzIjpbXSwiYW1vdW50IjowLCJsb2NrQ2hhdCI6ZmFsc2UsInBob25lVmVyaWZpZWQiOmZhbHNlLCJpcEFkZHJlc3MiOiIyNDA1OjQ4MDI6NGU0Mjo0MTcwOjcxMDQ6YjY0Njo2Nzg5Ojg2NDgiLCJtdXRlIjpmYWxzZSwiYXZhdGFyIjoiaHR0cHM6Ly9pbWFnZXMuc3dpbnNob3AubmV0L2ltYWdlcy9hdmF0YXIvYXZhdGFyXzA5LnBuZyIsInBsYXRmb3JtSWQiOjQsInVzZXJJZCI6ImEyOGEwZjA2LWU4OGYtNDRiNy1hMjY4LTVmNmRhZDk0OWZiZiIsImVtYWlsVmVyaWZpZWQiOm51bGwsInJlZ1RpbWUiOjE3NzMxMDY2NDkxOTksInBob25lIjoiIiwiZGVwb3NpdCI6ZmFsc2UsInVzZXJuYW1lIjoiR01fcXVhcG90anoifQ.3ycgvK1-PwRpBqANZJ3li00kpuzV6Ike6ZjYPthf3X0",
                    "locale": "vi",
                    "userId": "a28a0f06-e88f-44b7-a268-5f6dad949fbf",
                    "username": "GM_quapotjz",
                    "timestamp": 1774138177205,
                    "refreshToken": "950f5b9974dd4f4c982a3681af9acbc7.f0d252e72ee64f07bd5819d6ca54bba1"
                }
            }
        ],
        [6, "MiniGame", "taixiuPlugin", {"cmd": 1005}],
        [6, "MiniGame", "lobbyPlugin", {"cmd": 10001}]
    ]

async def connect_websocket():
    """Kết nối WebSocket"""
    global ws_connection, current_session_id, current_result, websocket_running
    
    while websocket_running:
        try:
            print("[🔄] Đang kết nối WebSocket...")
            
            ws_connection = await websockets.connect(
                WEBSOCKET_URL,
                extra_headers=WS_HEADERS,
                ping_interval=15,
                ping_timeout=10
            )
            
            print("[✅] WebSocket connected to Sun.Win")
            
            for i, msg in enumerate(initial_messages):
                await asyncio.sleep(i * 0.6)
                await ws_connection.send(json.dumps(msg))
            
            async for message in ws_connection:
                try:
                    data = json.loads(message)
                    
                    if not isinstance(data, list) or len(data) < 2:
                        continue
                    
                    if isinstance(data[1], dict):
                        cmd = data[1].get('cmd')
                        sid = data[1].get('sid')
                        d1 = data[1].get('d1')
                        d2 = data[1].get('d2')
                        d3 = data[1].get('d3')
                        gBB = data[1].get('gBB')
                        
                        if cmd == 1008 and sid:
                            current_session_id = sid
                            print(f"[🎮] Phiên mới: {sid}")
                        
                        if cmd == 1003 and gBB:
                            if d1 is None or d2 is None or d3 is None:
                                continue
                            
                            total = d1 + d2 + d3
                            result = "Tài" if total > 10 else "Xỉu"
                            
                            current_result = {
                                "phien": current_session_id,
                                "xuc_xac_1": d1,
                                "xuc_xac_2": d2,
                                "xuc_xac_3": d3,
                                "tong": total,
                                "ket_qua": result,
                                "thoi_gian": get_vietnam_time()
                            }
                            
                            print(f"[🎲] Phiên {current_result['phien']}: {d1}-{d2}-{d3} = {total} ({result}) - {current_result['thoi_gian']}")
                            
                            current_session_id = None
                            
                except json.JSONDecodeError as e:
                    print(f"[❌] Lỗi parse JSON: {e}")
                except Exception as e:
                    print(f"[❌] Lỗi xử lý message: {e}")
                    
        except websockets.exceptions.ConnectionClosed as e:
            print(f"[⚠️] WebSocket đóng: {e}")
            await asyncio.sleep(reconnect_delay)
        except Exception as e:
            print(f"[❌] Lỗi kết nối WebSocket: {e}")
            await asyncio.sleep(reconnect_delay)

# Flask routes
@app.route('/api/tx', methods=['GET'])
def get_tx_result():
    """Endpoint lấy kết quả tài xỉu mới nhất"""
    return jsonify(current_result)

@app.route('/', methods=['GET'])
def index():
    """Trang chủ"""
    uptime = int(time.time() - start_time)
    return jsonify({
        "name": "Sun.Win Tài Xỉu Data Stream",
        "version": "1.0",
        "status": "running",
        "uptime_seconds": uptime,
        "endpoints": {
            "/api/tx": "Lấy kết quả tài xỉu mới nhất"
        },
        "thoi_gian": get_vietnam_time(),
        "current_user": TOKEN_DATA.get('username') if TOKEN_DATA else "Unknown"
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint không tồn tại. Chỉ có /api/tx"}), 404

def signal_handler(sig, frame):
    """Xử lý tín hiệu dừng"""
    global websocket_running
    print("\n[👋] Đang tắt server...")
    websocket_running = False
    sys.exit(0)

# Chạy WebSocket trong thread riêng
def run_websocket():
    asyncio.run(connect_websocket())

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("\n" + "="*60)
    print("🎲 Sun.Win Tài Xỉu Data Stream")
    print("="*60)
    if TOKEN_DATA:
        print(f"👤 Đang dùng token của: {TOKEN_DATA.get('username', 'Unknown')}")
        print(f"🆔 User ID: {TOKEN_DATA.get('userId', 'Unknown')}")
        print(f"🌐 IP: {TOKEN_DATA.get('ipAddress', 'Unknown')}")
    print(f"📡 Server running on port: {PORT}")
    print("="*60)
    print("🔌 Đang kết nối WebSocket Sun.Win...")
    print("="*60)
    print("📊 API Endpoint:")
    print(f"   🎯 /api/tx - Lấy kết quả tài xỉu mới nhất")
    print("="*60 + "\n")
    
    # Chạy WebSocket trong thread riêng
    ws_thread = threading.Thread(target=run_websocket, daemon=True)
    ws_thread.start()
    
    # Chạy Flask server (blocking)
    app.run(host='0.0.0.0', port=PORT, debug=False)
