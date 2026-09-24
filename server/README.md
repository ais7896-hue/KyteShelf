# KyteShelf 雲端授權系統 (Cloudflare Workers + KV)

本系統專為 KyteShelf 設計，採用 **Cloudflare 免費方案**（每天 100,000 次請求、$0 維護成本）。
採用 **「14 天全功能試用 ➔ 基礎免費版 ➔ Pro 買斷解鎖」的無痛成癮商業模式**：
- **第 1 ～ 14 天（新手黃金期）**：全功能無限制開放（無限置物架、無限檔案、ZIP 打包、資料夾監控），讓使用者建立日常肌肉記憶。
- **第 15 天起（溫和降級）**：自動切換為【基礎免費版】（單置物架 / 上限 5 個檔案）。不暴力鎖死，但當使用者需要更多容量或進階功能時，精準彈出 Pro 升級提示。
- **Pro 專業版（序號開通）**：NT$ 399 永久買斷，單組序號支援 2 台電腦同時啟用，支援換機解綁，日常 100% 離線可用。

---

## 📂 系統架構與相關程式碼

| 模組 | 檔案路徑 | 功能說明 |
| :--- | :--- | :--- |
| **Worker 伺服腳本** | [`server/worker.js`](worker.js) | 免費伺服端，提供 `/api/activate`、`/api/deactivate`、批次產號 `/api/admin/generate-keys` 與查詢端點。 |
| **本機授權核心** | [`kyteshelf/license.py`](../kyteshelf/license.py) | 讀取 Windows 唯一硬體識別碼（`MachineGuid`），負責初次連線啟用與 **100% 本地離線 HMAC 簽名驗證**（0ms 驗證、防拷貝、防篡改）。 |
| **授權 UI 視窗** | [`kyteshelf/ui/license_dialog.py`](../kyteshelf/ui/license_dialog.py) | 現代化開通介面：序號輸入、立即開通、裝置上限提示、換機解綁、本機識別碼一鍵複製、蝦皮官方購買直達。 |
| **選單與設定整合** | [`shelf_manager.py`](../kyteshelf/ui/shelf_manager.py), [`hotkey_dialog.py`](../kyteshelf/ui/hotkey_dialog.py) | 托盤右鍵選單動態狀態指示（未啟用 / 已開通），偏好設定頂部即時徽章與直達按鈕。 |

---

## 🚀 3 分鐘部署指南（$0 伺服器成本）

### 第一步：建立 Cloudflare KV 命名空間
1. 登入 [Cloudflare Dashboard](https://dash.cloudflare.com/)。
2. 點擊左側導航欄的 **Storage & Databases** ➔ **KV**。
3. 點擊 **Create a Namespace**。
4. 輸入名稱：`KYTE_LICENSES`，點擊 **Add**。

### 第二步：建立並發布 Worker
1. 點擊左側導航欄的 **Workers & Pages** ➔ **Create application** ➔ **Create Worker**。
2. 名稱輸入 `kyteshelf-license`，點擊 **Deploy**。
3. 部署完成後，點擊右上角 **Edit code**。
4. 將同資料夾內的 [`worker.js`](worker.js) 內容**全部複製並覆蓋貼上**，點擊右上角 **Save and deploy**。

### 第三步：綁定 KV 與環境變數
1. 回到該 Worker 的管理介面（點擊左上方 Worker 名稱返回）。
2. 切換到 **Settings** 分頁：
   - 點擊 **Bindings** ➔ **Add** ➔ 選擇 **KV Namespace**：
     - **Variable name**：填入 `KYTE_LICENSES`（必須完全一致）
     - **KV namespace**：選擇剛才建立的 `KYTE_LICENSES`
     - 點擊 **Save**。
   - 點擊 **Variables and Secrets** ➔ **Add**：
     - `JWT_SECRET`：輸入簽名密鑰（預設：`KyteShelf_Secret_2026_@KeySecure`）
     - `ADMIN_SECRET`：輸入自訂管理員密鑰（例如：`AdminSuperSecret_2026`）
     - 點擊 **Save**。

> **你的正式 Worker API 網址**：  
> `https://kyteshelf-license.ais7896.workers.dev`

---

## 🛠️ 管理員一鍵產生序號（蝦皮賣場上架）

可以使用 Windows PowerShell 或 cURL 直接呼叫 Worker API 批次產生序號，直接複製去蝦皮賣場上架或設定自動發卡機器人。

### Windows PowerShell 一鍵產號（產生 10 組序號）：
```powershell
$headers = @{ "X-Admin-Secret" = "AdminSuperSecret_2026"; "Content-Type" = "application/json" }
$body = @{ count = 10; max_devices = 2; note = "蝦皮首批銷售" } | ConvertTo-Json
$response = Invoke-RestMethod -Uri "https://kyteshelf-license.ais7896.workers.dev/api/admin/generate-keys" -Method Post -Headers $headers -Body $body
$response.keys
```

### 產出的序號格式範例：
```text
KYTE-9H2B-4N8C-Z7W1
KYTE-M3F5-8K1P-A6D2
KYTE-T7V9-2E4X-L8Q3
```
- 每組序號均**嚴格支援同時啟用 2 台 Windows 電腦**。
- 客戶在蝦皮下單後，透過聊聊或自動發卡機器人將序號發送給客戶即可。

---

## 🔍 查詢序號狀態 (客戶換機或客服查詢)
```powershell
$headers = @{ "X-Admin-Secret" = "AdminSuperSecret_2026" }
Invoke-RestMethod -Uri "https://kyteshelf-license.ais7896.workers.dev/api/admin/query-key?key=KYTE-9H2B-4N8C-Z7W1" -Headers $headers
```
可即時查看該序號目前已綁定的電腦名稱、機器 GUID 與啟用時間。

---

## 🛡️ 客戶端防護與換機機制

1. **日常 100% 離線**：
   客戶只有在初次輸入序號時需要連網驗證一次。伺服器簽發一組與該電腦硬體識別碼（MachineGuid）綁定的 HMAC 憑證並保存在本地 `%APPDATA%\KyteShelf\license.dat`。往後每次啟動軟體均在 0ms 內純本地驗證，斷網環境完全不受影響。

2. **防拷貝防篡改**：
   若有人將 `license.dat` 拷貝至其他電腦，軟體啟動時會比對本機硬體 GUID，只要與憑證內的 GUID 不符便會立即判定無效並降級為免費模式。

3. **換機解綁流程**：
   - 當客戶更換新電腦時，只需在舊電腦打開 KyteShelf「軟體授權」視窗，點擊「**🔄 解除此電腦綁定**」。
   - 伺服器會將舊電腦自綁定名單剔除並釋放名額，舊電腦本機憑證隨即銷毀。
   - 客戶隨後即可在新電腦輸入同一組原序號直接開通。

---

## 💬 蝦皮聊聊自動發卡 / 出貨訊息範本

```text
感謝您購買 KyteShelf 專業版！🎉

【您的專屬授權序號】：
KYTE-XXXX-XXXX-XXXX

【啟用說明】：
1. 請至官方網站或 GitHub Releases 下載最新版安裝檔並完成安裝。
2. 啟動軟體後，在桌面右下角常駐圖示點右鍵 ➔ 點選「軟體授權 / 開通專業版」。
3. 貼上您的授權序號，點擊「立即驗證並開通」即可永久解鎖專業版！

💡 本組序號支援您個人的 2 台 Windows 電腦同時啟用。
💡 首次啟用成功後日常 100% 支援離線運行；未來若更換電腦，可在軟體內點擊「解除綁定」即可將名額移至新電腦。
```
