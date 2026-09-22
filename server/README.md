# KyteShelf 雲端授權系統 (Cloudflare Workers + KV)

本系統專為 KyteShelf 設計，採用 **Cloudflare 免費方案**（每天 100,000 次請求、$0 維護成本）。
序號開通後客戶端會保存經過簽署的離線憑證，日後打開軟體**100% 離線可用**，且嚴格限制**單組序號最多同時綁定 2 台 Windows 電腦**（換機時只需一鍵解綁）。

---

## 🚀 3 分鐘部署指南

### 第一步：建立 Cloudflare KV 命名空間
1. 登入 [Cloudflare Dashboard](https://dash.cloudflare.com/)。
2. 點擊左側導航欄的 **Storage & Databases** -> **KV**。
3. 點擊 **Create a Namespace**。
4. 輸入名稱：`KYTE_LICENSES`，點擊 **Add**。

### 第二步：建立並發布 Worker
1. 點擊左側導航欄的 **Workers & Pages** -> **Create application** -> **Create Worker**。
2. 名稱輸入 `kyteshelf-license`，點擊 **Deploy**。
3. 部署完成後，點擊右上角 **Edit code**。
4. 將本資料夾內的 `worker.js` 內容**全部複製貼上**覆蓋進編輯器，點擊右上角 **Save and deploy**。

### 第三步：綁定 KV 與環境變數
1. 回到該 Worker 的管理介面（點擊左上方 Worker 名稱返回）。
2. 切換到 **Settings** 分頁：
   - 點擊 **Bindings** -> **Add** -> 選擇 **KV Namespace**：
     - **Variable name**：填入 `KYTE_LICENSES`（必須完全一致）
     - **KV namespace**：選擇剛才建立的 `KYTE_LICENSES`
     - 點擊 **Save**。
   - 點擊 **Variables and Secrets** -> **Add**：
     - `JWT_SECRET`：輸入自訂簽名密鑰（例：`KyteShelf_Secret_2026_@KeySecure`）
     - `ADMIN_SECRET`：輸入管理員密鑰（例：`AdminSuperSecret_2026`）
     - 點擊 **Save**。

> 部署完成後，你的 Worker 網址格式通常為：
> `https://kyteshelf-license.<你的帳號子網域>.workers.dev`

---

## 🛠️ 管理員一鍵產生序號

你可以使用 PowerShell 或 cURL 直接呼叫 Worker API 批次產生序號，直接複製去蝦皮賣場上架或設定自動發卡機器人。

### Windows PowerShell 一鍵產號（產生 10 組序號）：
```powershell
$headers = @{ "X-Admin-Secret" = "AdminSuperSecret_2026"; "Content-Type" = "application/json" }
$body = @{ count = 10; max_devices = 2; note = "蝦皮首批銷售" } | ConvertTo-Json
$response = Invoke-RestMethod -Uri "https://你的Worker網址.workers.dev/api/admin/generate-keys" -Method Post -Headers $headers -Body $body
$response.keys
```

### 產出的序號格式範例：
```text
KYTE-A8K2-9M4D-X7R3
KYTE-C3H7-2W9P-L5K8
KYTE-F6B4-8T1V-Z9Q2
```
每一組序號均支援 2 台電腦同時開通！

---

## 🔍 查詢序號狀態 (客戶換機或客服查詢)
```powershell
$headers = @{ "X-Admin-Secret" = "AdminSuperSecret_2026" }
Invoke-RestMethod -Uri "https://你的Worker網址.workers.dev/api/admin/query-key?key=KYTE-A8K2-9M4D-X7R3" -Headers $headers
```
可看到該序號目前綁定了哪幾台 Windows 裝置代碼與開通時間。
