import os
import sys
import json
import time
from datetime import datetime
import requests

APP_ID = os.environ.get("ROLL_APP_ID")
APP_SECRET = os.environ.get("ROLL_APP_SECRET")

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

HEADERS = {
    "app_id": APP_ID,
    "app_secret": APP_SECRET
}

# 星期映射：0=周一, 1=周二, 2=周三, 3=周四, 4=周五, 5=周六, 6=周日
# 注意：福彩3D标识优先尝试 3d，如果不行自动回退 fc3d
SCHEDULE = {
    "3d":    [0, 1, 2, 3, 4, 5, 6],  # 福彩3D（每天）
    "kl8":   [0, 1, 2, 3, 4, 5, 6],  # 快乐8（每天）
    "pl3":   [0, 1, 2, 3, 4, 5, 6],  # 排列3（每天）
    "pl5":   [0, 1, 2, 3, 4, 5, 6],  # 排列5（每天）
    "ssq":   [1, 3, 6],              # 双色球（周二/四/日）
    "qlc":   [0, 2, 4],              # 七乐彩（周一/三/五）
    "cjdlt": [0, 2, 5],              # 超级大乐透（周一/三/六）
    "qxc":   [1, 4, 6],              # 七星彩（周二/五/日）
}

def sync_types():
    """接口一：每天 08:00 拉取彩种类型信息"""
    url = "https://www.mxnzp.com/api/lottery/common/types"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        res = resp.json()
        if res.get("code") == 1 and res.get("data"):
            data = {
                "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data": res["data"]
            }
            with open(os.path.join(DATA_DIR, "types.json"), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("✅ 彩种类型信息更新成功 -> data/types.json")
        else:
            print(f"❌ types 接口返回错误: {res.get('msg')}")
    except Exception as e:
        print(f"❌ types 请求异常: {e}")

def fetch_history_api(code, size=50):
    url = "https://www.mxnzp.com/api/lottery/common/history"
    params = {"code": code, "size": str(size)}
    resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
    return resp.json()

def sync_history(code, size=50):
    """接口二：拉取单个彩种最近开奖，并兼容 3d / fc3d 命名"""
    try:
        res = fetch_history_api(code, size=size)
        
        # 如果是 3d 请求失败，自动切换 fc3d 再试一次
        if res.get("code") != 1 and code == "3d":
            print(f"[3d] 尝试备用标识 fc3d...")
            res_backup = fetch_history_api("fc3d", size=size)
            if res_backup.get("code") == 1:
                res = res_backup

        if res.get("code") != 1 or not res.get("data"):
            print(f"❌ [{code}] 获取失败原因: {res.get('msg')}")
            return

        # 统一输出文件名，3d 保存为 3d.json（或同时另存一份 fc3d.json）
        file_path = os.path.join(DATA_DIR, f"{code}.json")
        existing_list = []
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    existing_list = json.load(f).get("data", [])
            except Exception:
                pass

        # 按期号去重合并并倒序排列
        data_map = {item["expect"]: item for item in existing_list if "expect" in item}
        for item in res["data"]:
            if "expect" in item:
                data_map[item["expect"]] = item

        sorted_list = sorted(data_map.values(), key=lambda x: str(x["expect"]), reverse=True)
        output = {
            "code": code,
            "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "latest": sorted_list[0] if sorted_list else None,
            "data": sorted_list
        }
        
        # 写入文件
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
            
        # 若为 3d，顺便复制一份 fc3d.json 保证你的 App 怎么调都能拿到
        if code == "3d":
            fc3d_path = os.path.join(DATA_DIR, "fc3d.json")
            with open(fc3d_path, "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"✅ [{code}] 更新完成！最新期号: {output['latest']['expect']}，累计历史: {len(sorted_list)} 期")
    except Exception as e:
        print(f"❌ [{code}] 请求异常: {e}")

def run_history_batch(target_codes):
    """按开奖星期筛选并执行"""
    weekday = datetime.now().weekday()
    for code in target_codes:
        if weekday in SCHEDULE.get(code, []):
            sync_history(code)
            time.sleep(2)

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "all"

    if action == "types":
        sync_types()
    elif action == "2130":
        run_history_batch(["3d", "ssq", "qlc"])
    elif action == "2140":
        run_history_batch(["pl3", "pl5", "cjdlt", "qxc"])
    elif action == "2145":
        run_history_batch(["kl8"])
    elif action == "all":
        sync_types()
        for c in SCHEDULE.keys():
            sync_history(c)
            time.sleep(2)
