/**
 * KyteShelf Cloudflare Worker 授權驗證與序號管理系統
 * 
 * 免費方案：每天 100,000 次請求、$0 伺服器費用
 * 依賴：Cloudflare Workers + KV (Namespace: KYTE_LICENSES)
 * 
 * 環境變數 (可在 Worker Settings -> Variables 設置)：
 * - JWT_SECRET: 用於簽署離線授權 Token 的密鑰 (例如: "KyteShelf_Secret_2026_@KeySecure")
 * - ADMIN_SECRET: 管理員產生序號的密鑰 (例如: "AdminSuperSecret_2026")
 */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    // CORS Headers
    const corsHeaders = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, X-Admin-Secret",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }

    try {
      // 1. 客戶端啟用端點
      if (path === "/api/activate" && request.method === "POST") {
        return await handleActivate(request, env, corsHeaders);
      }

      // 2. 客戶端解除綁定端點 (換機)
      if (path === "/api/deactivate" && request.method === "POST") {
        return await handleDeactivate(request, env, corsHeaders);
      }

      // 3. 管理端點：批次產生序號 (需帶 X-Admin-Secret)
      if (path === "/api/admin/generate-keys" && request.method === "POST") {
        return await handleAdminGenerate(request, env, corsHeaders);
      }

      // 4. 管理端點：查詢序號使用狀況
      if (path === "/api/admin/query-key" && request.method === "GET") {
        return await handleAdminQuery(request, env, corsHeaders);
      }

      // 首頁/健康檢查
      return new Response(
        JSON.stringify({ status: "ok", service: "KyteShelf License API", version: "1.0.0" }),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    } catch (err) {
      return new Response(
        JSON.stringify({ success: false, message: "伺服器內部錯誤：" + err.message }),
        { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }
  },
};

/**
 * 啟用授權
 */
async function handleActivate(request, env, corsHeaders) {
  const body = await request.json();
  const rawKey = body.key ? body.key.trim().toUpperCase() : "";
  const machineId = body.machine_id ? body.machine_id.trim() : "";
  const machineName = body.machine_name || "Windows Device";

  if (!rawKey || !machineId) {
    return jsonResponse(
      { success: false, message: "請提供序號 (key) 與機器識別碼 (machine_id)" },
      400,
      corsHeaders
    );
  }

  const kvKey = `license:${rawKey}`;
  const recordStr = await env.KYTE_LICENSES.get(kvKey);

  if (!recordStr) {
    return jsonResponse(
      { success: false, message: "無效的授權序號，請確認輸入是否正確" },
      404,
      corsHeaders
    );
  }

  const record = JSON.parse(recordStr);

  if (record.status !== "active") {
    return jsonResponse(
      { success: false, message: "此序號已被停用或作廢，請聯繫官方客服 (support@aisming.com)" },
      403,
      corsHeaders
    );
  }

  const maxDevices = record.max_devices || 2;
  const machines = record.machines || [];

  // 檢查此機器是否已經啟用過
  const existingIdx = machines.findIndex((m) => m.machine_id === machineId);

  if (existingIdx === -1) {
    // 未曾在此機器啟用，檢查是否已滿額
    if (machines.length >= maxDevices) {
      return jsonResponse(
        {
          success: false,
          code: "DEVICE_LIMIT_EXCEEDED",
          message: `此序號已在 ${machines.length} 台電腦上啟用，已達上限（${maxDevices} 台）。如需在目前電腦使用，請先在舊電腦的偏好設定點擊「解除綁定」。`,
        },
        403,
        corsHeaders
      );
    }

    // 加入新設備
    machines.push({
      machine_id: machineId,
      machine_name: machineName,
      activated_at: new Date().toISOString(),
    });

    record.machines = machines;
    await env.KYTE_LICENSES.put(kvKey, JSON.stringify(record));
  }

  // 簽發離線授權 Token (內含 machine_id + key + HMAC 簽名)
  const secretKey = env.JWT_SECRET || "KyteShelf_Default_Fallback_Secret_2026";
  const token = await generateSignedToken(
    {
      key: rawKey,
      machine_id: machineId,
      issued_at: Date.now(),
      type: "lifetime",
    },
    secretKey
  );

  return jsonResponse(
    {
      success: true,
      message: "啟用成功！已綁定至此電腦",
      token: token,
      devices_used: machines.length,
      max_devices: maxDevices,
    },
    200,
    corsHeaders
  );
}

/**
 * 解除綁定 (換機)
 */
async function handleDeactivate(request, env, corsHeaders) {
  const body = await request.json();
  const rawKey = body.key ? body.key.trim().toUpperCase() : "";
  const machineId = body.machine_id ? body.machine_id.trim() : "";

  if (!rawKey || !machineId) {
    return jsonResponse(
      { success: false, message: "請提供序號與機器識別碼" },
      400,
      corsHeaders
    );
  }

  const kvKey = `license:${rawKey}`;
  const recordStr = await env.KYTE_LICENSES.get(kvKey);

  if (!recordStr) {
    return jsonResponse({ success: false, message: "查無此序號" }, 404, corsHeaders);
  }

  const record = JSON.parse(recordStr);
  const machines = record.machines || [];
  const newMachines = machines.filter((m) => m.machine_id !== machineId);

  record.machines = newMachines;
  await env.KYTE_LICENSES.put(kvKey, JSON.stringify(record));

  return jsonResponse(
    {
      success: true,
      message: "已成功解除此電腦綁定，名額已釋放",
      devices_used: newMachines.length,
      max_devices: record.max_devices || 2,
    },
    200,
    corsHeaders
  );
}

/**
 * 管理員批次產生序號
 */
async function handleAdminGenerate(request, env, corsHeaders) {
  const adminSecret = request.headers.get("X-Admin-Secret");
  const expectedSecret = env.ADMIN_SECRET || "AdminSuperSecret_2026";

  if (!adminSecret || adminSecret !== expectedSecret) {
    return jsonResponse({ success: false, message: "管理員密鑰驗證失敗" }, 401, corsHeaders);
  }

  const body = await request.json().catch(() => ({}));
  const count = Math.min(Math.max(body.count || 10, 1), 100);
  const maxDevices = body.max_devices || 2;
  const note = body.note || "Shopee Batch";

  const generatedKeys = [];

  for (let i = 0; i < count; i++) {
    const key = generateLicenseKey();
    const record = {
      key: key,
      created_at: new Date().toISOString(),
      max_devices: maxDevices,
      machines: [],
      status: "active",
      note: note,
    };

    await env.KYTE_LICENSES.put(`license:${key}`, JSON.stringify(record));
    generatedKeys.push(key);
  }

  return jsonResponse(
    {
      success: true,
      count: generatedKeys.length,
      max_devices: maxDevices,
      keys: generatedKeys,
    },
    200,
    corsHeaders
  );
}

/**
 * 管理員查詢序號
 */
async function handleAdminQuery(request, env, corsHeaders) {
  const adminSecret = request.headers.get("X-Admin-Secret");
  const expectedSecret = env.ADMIN_SECRET || "AdminSuperSecret_2026";

  if (!adminSecret || adminSecret !== expectedSecret) {
    return jsonResponse({ success: false, message: "管理員密鑰驗證失敗" }, 401, corsHeaders);
  }

  const url = new URL(request.url);
  const key = (url.searchParams.get("key") || "").trim().toUpperCase();

  if (!key) {
    return jsonResponse({ success: false, message: "請帶入 key 參數" }, 400, corsHeaders);
  }

  const recordStr = await env.KYTE_LICENSES.get(`license:${key}`);
  if (!recordStr) {
    return jsonResponse({ success: false, message: "查無此序號" }, 404, corsHeaders);
  }

  return jsonResponse({ success: true, data: JSON.parse(recordStr) }, 200, corsHeaders);
}

// 輔助函式：產生隨機序號 (KYTE-XXXX-XXXX-XXXX)
function generateLicenseKey() {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"; // 去除易混淆字元 O, 0, I, 1
  let result = "KYTE";
  for (let block = 0; block < 3; block++) {
    let segment = "";
    for (let i = 0; i < 4; i++) {
      segment += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    result += "-" + segment;
  }
  return result;
}

// 輔助函式：產生 HMAC 簽名 Token
async function generateSignedToken(payload, secret) {
  const enc = new TextEncoder();
  const payloadStr = JSON.stringify(payload);
  const payloadB64 = btoa(unescape(encodeURIComponent(payloadStr)));

  const keyData = enc.encode(secret);
  const cryptoKey = await crypto.subtle.importKey(
    "raw",
    keyData,
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );

  const signatureBuffer = await crypto.subtle.sign("HMAC", cryptoKey, enc.encode(payloadB64));
  const signatureB64 = btoa(String.fromCharCode(...new Uint8Array(signatureBuffer)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");

  return `${payloadB64}.${signatureB64}`;
}

function jsonResponse(data, status, headers) {
  return new Response(JSON.stringify(data, null, 2), {
    status: status,
    headers: {
      ...headers,
      "Content-Type": "application/json; charset=utf-8",
    },
  });
}
