import asyncio
import websockets
import json
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, jsonify
from flask_cors import CORS
import os
import sys

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
websocket_running = True

# Hàm lấy thời gian Việt Nam (UTC+7)
def get_vietnam_time():
    utc7_time = datetime.utcnow() + timedelta(hours=7)
    return utc7_time.strftime("%d-%m-%Y %H:%M:%S") + " UTC+7"

# Token cứng - đã được parse sẵn từ file token.txt của bạn
TOKEN_DATA = {
    "username": "GM_quapotjz",
    "userId": "a28a0f06-e88f-44b7-a268-5f6dad949fbf",
    "wsToken": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJnZW5kZXIiOjAsImNhblZpZXdTdGF0IjpmYWxzZSwiZGlzcGxheU5hbWUiOiJsb2xtYW1heXN1MTIiLCJib3QiOjAsImlzTWVyY2hhbnQiOmZhbHNlLCJ2ZXJpZmllZEJhbmtBY2NvdW50IjpmYWxzZSwicGxheUV2ZW50TG9iYnkiOmZhbHNlLCJjdXN0b21lcklkIjozMzkxMDEyNTEsImFmZklkIjoiR0VNV0lOIiwiYmFubmVkIjpmYWxzZSwiYnJhbmQiOiJnZW0iLCJlbWFpbCI6IiIsInRpbWVzdGFtcCI6MTc4MDAyOTM1NDQ2NiwibG9ja0dhbWVzIjpbXSwiYW1vdW50IjowLCJsb2NrQ2hhdCI6ZmFsc2UsInBob25lVmVyaWZpZWQiOmZhbHNlLCJpcEFkZHJlc3MiOiIxLjU1LjEyNC4yNDUiLCJtdXRlIjpmYWxzZSwiYXZhdGFyIjoiaHR0cHM6Ly9pbWFnZXMuc3dpbnNob3AubmV0L2ltYWdlcy9hdmF0YXIvYXZhdGFyXzA5LnBuZyIsInBsYXRmb3JtSWQiOjQsInVzZXJJZCI6ImEyOGEwZjA2LWU4OGYtNDRiNy1hMjY4LTVmNmRhZDk0OWZiZiIsImVtYWlsVmVyaWZpZWQiOm51bGwsInJlZ1RpbWUiOjE3NzMxMDY2NDkxOTksInBob25lIjoiIiwiZGVwb3NpdCI6ZmFsc2UsInVzZXJuYW1lIjoiR01fcXVhcG90anoifQ.ER8BPMgIwYfyhpD0siOyNmI3E9Qd7R0o1X7Zan86DjU",
    "ipAddress": "1.55.124.245",
    "timestamp": 1780029354479,
    "refreshToken": "26b930ec6dc04d7db5c2b362a1baac87.7549ba6185d4467380ee447589380061"
}

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

async def connect_websocket():
    """Kết nối WebSocket và lấy dữ liệu"""
    global current_session_id, current_result, websocket_running
    
    reconnect_delay = 2.5
    
    while websocket_running:
        try:
            print("[🔄] Đang kết nối WebSocket Sun.Win...")
            
            # Thử kết nối với timeout
            ws_connection = await asyncio.wait_for(
                websockets.connect(WEBSOCKET_URL, extra_headers=WS_HEADERS),
                timeout=30
            )
            
            print("[✅] WebSocket đã kết nối thành công!")
            
            # Gửi các tin nhắn khởi tạo
            for i, msg in enumerate(initial_messages):
                await asyncio.sleep(i * 0.6)
                await ws_connection.send(json.dumps(msg))
                print(f"[📤] Đã gửi tin nhắn {i+1}")
            
            print("[👂] Đang lắng nghe dữ liệu tài xỉu...")
            
            # Lắng nghe dữ liệu
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
                        
                        # Lưu session ID
                        if cmd == 1008 and sid:
                            current_session_id = sid
                            print(f"[🎮] Phiên mới: {sid}")
                        
                        # Nhận kết quả xúc xắc
                        if cmd == 1003 and gBB and d1 is not None:
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
                            
                            print(f"[🎲] KẾT QUẢ: {d1} - {d2} - {d3} | Tổng: {total} | {result} | {get_vietnam_time()}")
                            current_session_id = None
                            
                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    print(f"[⚠️] Lỗi xử lý tin nhắn: {e}")
                    
        except asyncio.TimeoutError:
            print("[❌] Kết nối WebSocket timeout, thử lại sau...")
            await asyncio.sleep(reconnect_delay)
        except websockets.exceptions.ConnectionClosed:
            print("[⚠️] WebSocket đóng kết nối, đang kết nối lại...")
            await asyncio.sleep(reconnect_delay)
        except Exception as e:
            print(f"[❌] Lỗi WebSocket: {e}, thử lại sau...")
            await asyncio.sleep(reconnect_delay)

# Flask routes
@app.route('/api/tx', methods=['GET'])
def get_tx_result():
    """Lấy kết quả tài xỉu mới nhất"""
    if current_result["tong"] is None:
        return jsonify({
            "status": "waiting",
            "message": "Đang chờ dữ liệu từ WebSocket...",
            "data": current_result
        })
    return jsonify(current_result)

@app.route('/', methods=['GET'])
def index():
    """Trang chủ"""
    return jsonify({
        "name": "Sun.Win Tài Xỉu Data Stream",
        "version": "2.0",
        "status": "running",
        "message": "API đang hoạt động",
        "endpoints": {
            "/api/tx": "Lấy kết quả tài xỉu mới nhất",
            "/health": "Kiểm tra trạng thái"
        },
        "thoi_gian": get_vietnam_time(),
        "current_user": TOKEN_DATA.get('username', 'GM_quapotjz')
    })

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "has_data": current_result["tong"] is not None,
        "last_update": current_result["thoi_gian"],
        "uptime": time.time()
    })

def run_websocket():
    """Chạy WebSocket trong thread riêng"""
    asyncio.run(connect_websocket())

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🎲 Sun.Win Tài Xỉu Data Stream v2.0")
    print("="*60)
    print(f"👤 Username: {TOKEN_DATA.get('username', 'Unknown')}")
    print(f"🆔 User ID: {TOKEN_DATA.get('userId', 'Unknown')}")
    print(f"📡 Port: {PORT}")
    print("="*60)
    
    # Chạy WebSocket trong thread riêng
    ws_thread = threading.Thread(target=run_websocket, daemon=True)
    ws_thread.start()
    
    # Chạy Flask
    print("[🚀] Khởi động Flask server...")
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
