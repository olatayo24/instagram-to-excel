from openpyxl import Workbook
import os
path = os.environ.get("PRICES_XLSX", os.path.join("data","prices.xlsx"))
os.makedirs(os.path.dirname(path), exist_ok=True)
wb = Workbook()
ws = wb.active
ws.title = "Prices"
ws.append(["product","price"])
ws.append(["AirPods","₦120,000"])
ws.append(["iPhone 14","₦950,000"])
ws.append(["PS5","₦780,000"])
wb.save(path)
print("Created:", path)
