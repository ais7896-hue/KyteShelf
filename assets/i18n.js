/**
 * assets/i18n.js - KyteShelf 官方網站中英雙語字典與切換引擎
 */

const TRANSLATIONS = {
    zh_TW: {
        "page.title": "KyteShelf - 專為 Windows 打造的桌面懸浮拖曳暫存置物架 | Dropover 最佳替代方案",
        "top.badge": "NEW",
        "top.announcement": "KyteShelf v1.4.0 正式發行！全新多國語言 (繁中/英文) 即時切換與國際化支援",

        "nav.features": "核心功能",
        "nav.workflow": "操作流程",
        "nav.guide": "操作指南",
        "nav.suite": "Kyte 全系列",
        "nav.faq": "常見問答",
        "nav.pro": "取得正式版",

        "hero.badge": "專為 Windows 10 / 11 深度調校的桌面效率神器",
        "hero.title_pre": "抓住檔案晃一下，",
        "hero.title_post": "工作流不再手忙腳亂",
        "hero.desc": "不再需要為了搬移檔案把螢幕切得密密麻麻。按住檔案輕晃滑鼠，專屬置物架立即浮現於手邊；中繼收集各處文件，隨放隨走，解放你的雙手。",
        "hero.btn_buy": "取得終身買斷版 (NT$ 399)",
        "hero.btn_installer": "下載安裝版 (v1.4.0)",
        "hero.btn_portable": "免安裝綠色版 (.zip)",

        "shelf.name": "置物架 #1",
        "shelf.item1_title": "首頁主視覺草稿_v3.png",
        "shelf.item1_sub": "📐 1920 × 1080 • 1.4 MB",
        "shelf.item2_title": "2026年度報價預算表.xlsx",
        "shelf.item2_sub": "試算表 • 840 KB",
        "shelf.item3_title": "📝 備忘：週五下午前將合約寄送給法務",
        "shelf.item3_sub": "自黏便箋 (雙擊編輯 • 拖出貼入)",
        "shelf.mode": "複製模式",
        "shelf.paste": "貼上",
        "shelf.select_all": "全選",
        "shelf.clear": "清空",

        "pain.title": "你是否也經歷過這些 Windows 拖放惡夢？",
        "pain.desc": "原本只需幾秒的整理，不該因為繁瑣視窗操作而浪費專注力。",
        "pain.trad_title": "傳統操作方式",
        "pain.trad_1": "為了跨資料夾搬檔案，必須手動並排打開 2 到 3 個檔案總管，畫面凌亂不堪。",
        "pain.trad_2": "按住檔案懸停在工作列等應用程式彈出，手腕緊繃，一不小心手滑掉錯資料夾。",
        "pain.trad_3": "在雙螢幕或超寬螢幕上，滑鼠得死按著檔案橫跨數千像素，嚴重增加操作負擔。",
        "pain.shelf_title": "使用 KyteShelf 後",
        "pain.shelf_1": "抓起檔案輕微晃動滑鼠，置物架立刻在游標旁就位接住檔案，不用切換任何視窗。",
        "pain.shelf_2": "暫存入架後雙手完全放開，從容切換目標軟體，再一口氣拖曳釋放完成傳遞。",
        "pain.shelf_3": "推車式中繼站：隨走隨收，將散落於桌面、下載資料夾與網頁的素材一次打包就緒。",

        "flow.badge": "Intuitive Workflow",
        "flow.title": "如同本能般順暢的操作哲學",
        "flow.desc": "零學習成本，一秒融入你既有的 Windows 桌面使用習慣。",
        "flow.step1_tag": "Step 1",
        "flow.step1_title": "抓住檔案晃動",
        "flow.step1_desc": "在任何檔案或圖片上按住滑鼠左鍵輕晃，或按下 <kbd class='px-1.5 py-0.5 bg-slate-100 rounded text-xs text-slate-700 font-mono'>Ctrl + `</kbd>，置物架自動現身。",
        "flow.step2_tag": "Step 2",
        "flow.step2_title": "萬物隨心暫存",
        "flow.step2_desc": "放開滑鼠檔案即安穩暫存。支援剪貼簿 <kbd class='px-1.5 py-0.5 bg-slate-100 rounded text-xs text-slate-700 font-mono'>Ctrl + V</kbd> 貼上截圖、純文字便箋與網址。",
        "flow.step3_tag": "Step 3",
        "flow.step3_title": "精準拖出清架",
        "flow.step3_desc": "切換到目的地視窗，將項目一次拖入即可完成傳送，置物架自動清空，全程 0 延遲無負擔。",
        "flow.guide_link": "閱讀完整【KyteShelf 圖文操作手冊與常見問題】",

        "detail.badge": "Built For Professionals",
        "detail.title": "專為高效率工作者打造的細節",
        "detail.desc": "不只是一個暫存盒，更是全面升級你桌面的操作中樞。",
        "detail.f1_title": "晃動手勢即刻召喚",
        "detail.f1_desc": "抓取檔案輕微晃動立即展開置物架，五級靈敏度可調，防誤觸演算法保證精確響應。",
        "detail.f2_title": "萬物皆可剪貼簿貼入",
        "detail.f2_desc": "支援 <kbd class='px-1.5 py-0.5 bg-slate-100 rounded text-xs text-slate-700 font-mono'>Ctrl + V</kbd>。截圖點陣圖、網頁圖片網址、文字筆記或檔案，智慧分類自動入架。",
        "detail.f3_title": "0 延遲極速響應架構",
        "detail.f3_desc": "全方位 I/O 非同步優化，高解析大圖懸停與單筆刪除即時反饋，告別視窗延遲與卡頓。",
        "detail.f4_title": "一鍵壓縮打包 ZIP",
        "detail.f4_desc": "收集好各資料夾的分散文件後，點擊底部 ZIP 按鈕原地壓縮存檔，整理歸檔一步到位。",
        "detail.f5_title": "Outlook 附件無縫直串",
        "detail.f5_desc": "深度整合 Windows COM 系統介面，選取項目右鍵即可自動掛載至正在編輯的 Outlook 郵件草稿。",
        "detail.f6_title": "防吞噬與拖曳守護",
        "detail.f6_desc": "手滑在置物架內放開時原檔完好保留不跑版；彈出重命名或設定視窗時自動鎖定，絕不誤隱藏。",

        "down.title": "立即免費下載試用",
        "down.desc": "無須註冊、本機離線運作，安裝後立即親身體驗滑鼠晃動召喚的極致流暢感。",
        "down.btn_installer": "下載 Windows 安裝版 (v1.4.0)",
        "down.btn_portable": "免安裝綠色版 (.zip)",
        "down.btn_buy": "前往購買終身序號",
        "down.f1": "相容 Windows 10 / 11 (64-bit)",
        "down.f2": "本機離線安全無後門",
        "down.f3": "安裝容量僅約 35MB",

        "price.badge": "Simple & Fair Pricing",
        "price.title": "一次買斷，終身受用",
        "price.desc": "拒絕每個月扣款的訂閱制。只需一杯咖啡的價格，讓日常工作效率永久倍增。",
        "price.tag": "終身個人正式授權",
        "price.period": "/ 永久使用",
        "price.feat1": "永久解鎖全部專業功能（ZIP壓縮、Outlook串接、圖片批次處理）",
        "price.feat2": "單組授權支援同時啟用 2 台個人 Windows 裝置",
        "price.feat3": "享有一年內免費維護與 Bug 修復（若未來 OS 大型改版需重構，新版另行販售）",
        "price.feat4": "純淨無廣告、本機離線運作、零個人資料上傳",
        "price.btn_shopee": "台灣蝦皮官方賣場購買 (即時發號)",
        "price.sub": "支援超商繳費、ATM轉帳、信用卡分期｜下單後系統自動即時發送授權序號",

        "faq.title": "常見問答",
        "faq.desc": "關於 KyteShelf 的授權、功能與相容性說明。",
        "faq.q1": "Q：支援哪些 Windows 作業系統？",
        "faq.a1": "KyteShelf 專為 64 位元的 Windows 10 (1809 以上) 與最新 Windows 11 深度設計與測試，全面相容系統原生深色（Dark Mode）與淺色主題。",
        "faq.q2": "Q：防毒軟體或 Windows Defender 會警示嗎？",
        "faq.a2": "由於本軟體使用 Windows 原生滑鼠勾點（Global Mouse Hook）來偵測「按住晃動召喚」手勢，少數防毒軟體可能初次會跳出安全提示。KyteShelf 採用純粹本機離線架構，不含任何聯網竊取程式碼，請安心點擊「允許執行」。",
        "faq.q3": "Q：更換新電腦或系統重灌後序號還能用嗎？",
        "faq.a3": "可以！每組正版序號允許同時綁定 2 台裝置。若您重灌電腦或更換硬體配備，可透過蝦皮聊聊或官方客服信箱 (<a href='mailto:support@aisming.com' class='text-blue-600 hover:underline font-semibold'>support@aisming.com</a>) 聯繫，將免費為您重置授權額度。",
        "faq.q4": "Q：購買後如何取得序號與開通？",
        "faq.a4": "在蝦皮官方賣場下單結帳後，自動發號系統會在 1 分鐘內透過聊聊私訊發送專屬正式版序號與軟體安裝引導，輸入後即可立即解鎖完整功能。",
        "faq.q5": "Q：一次性買斷的維護期與後續更新政策是什麼？",
        "faq.a5": "本商品為一次性買斷，享有一年內免費維護與 Bug 修復。若未來作業系統大型改版（如 Windows 升級）導致軟體需重構，新版本將另行販售。",

        "footer.slogan": "© 2026 KyteShelf. All rights reserved. 專為提升桌面工作效率而生。",
        "footer.terms": "服務條款",
        "footer.privacy": "隱私權政策",
        "footer.support": "技術支援"
    },

    en_US: {
        "page.title": "KyteShelf - The Next-Gen Floating Drag & Drop Staging Shelf for Windows | Best Dropover Alternative",
        "top.badge": "NEW",
        "top.announcement": "KyteShelf v1.4.0 Released! Brand-new multi-language (Traditional Chinese & English) support.",

        "nav.features": "Features",
        "nav.workflow": "Workflow",
        "nav.guide": "User Guide",
        "nav.suite": "Kyte Suite",
        "nav.faq": "FAQ",
        "nav.pro": "Get Pro License",

        "hero.badge": "Engineered for Windows 10 & 11 Desktop Productivity",
        "hero.title_pre": "Shake Your File to Summon,",
        "hero.title_post": "Effortless Desktop Flow",
        "hero.desc": "Never clutter your monitor with side-by-side Explorer windows again. Hold any file, shake your cursor, and your dedicated staging shelf pops up instantly right beside your hand. Stash, collect, and drop freely.",
        "hero.btn_buy": "Get Perpetual License (NT$ 399)",
        "hero.btn_installer": "Download Installer (v1.4.0)",
        "hero.btn_portable": "Portable .zip Edition",

        "shelf.name": "Shelf #1",
        "shelf.item1_title": "Hero_Draft_v3.png",
        "shelf.item1_sub": "📐 1920 × 1080 • 1.4 MB",
        "shelf.item2_title": "Budget_Estimate_2026.xlsx",
        "shelf.item2_sub": "Spreadsheet • 840 KB",
        "shelf.item3_title": "📝 Note: Send legal contract draft before Friday",
        "shelf.item3_sub": "Sticky Note (Double-click to edit • Drag to paste)",
        "shelf.mode": "Copy Mode",
        "shelf.paste": "Paste",
        "shelf.select_all": "Select All",
        "shelf.clear": "Clear",

        "pain.title": "Tired of These Common Windows Drag & Drop Headaches?",
        "pain.desc": "Organizing files should take seconds, not strain your wrists and focus.",
        "pain.trad_title": "Traditional Dragging",
        "pain.trad_1": "Cluttering your screen by manually tiling 2 to 3 File Explorer windows side-by-side.",
        "pain.trad_2": "Hovering tense fingers over taskbar icons waiting for target apps to pop up, risking accidental drops.",
        "pain.trad_3": "Dragging across multi-monitor or ultra-wide screens over thousands of pixels with mouse buttons held down.",
        "pain.shelf_title": "With KyteShelf",
        "pain.shelf_1": "Shake your mouse slightly while holding files—KyteShelf appears beside your cursor instantly.",
        "pain.shelf_2": "Release your mouse into the shelf, comfortably navigate to your destination app, then drop files.",
        "pain.shelf_3": "Virtual mobile cart: Collect files from browser downloads, chat apps, and folders all into one staging shelf.",

        "flow.badge": "Intuitive Workflow",
        "flow.title": "A Natural & Intuitive Operating Rhythm",
        "flow.desc": "Zero learning curve. Integrates seamlessly into your existing Windows desktop habits.",
        "flow.step1_tag": "Step 1",
        "flow.step1_title": "Shake to Summon",
        "flow.step1_desc": "Hold left-click on any file and shake the cursor gently, or press <kbd class='px-1.5 py-0.5 bg-slate-100 rounded text-xs text-slate-700 font-mono'>Ctrl + `</kbd> to summon the shelf.",
        "flow.step2_tag": "Step 2",
        "flow.step2_title": "Stash Anything",
        "flow.step2_desc": "Release mouse to stage files safely. Supports clipboard <kbd class='px-1.5 py-0.5 bg-slate-100 rounded text-xs text-slate-700 font-mono'>Ctrl + V</kbd> to paste screenshots, notes, or URLs.",
        "flow.step3_tag": "Step 3",
        "flow.step3_title": "Drag Out & Clean",
        "flow.step3_desc": "Switch to your destination window and drag staged items out. The shelf clears automatically with zero latency.",
        "flow.guide_link": "Read Full User Manual & Documentation",

        "detail.badge": "Built For Professionals",
        "detail.title": "Thoughtfully Crafted for Power Users",
        "detail.desc": "More than a temporary buffer—a comprehensive desktop productivity accelerator.",
        "detail.f1_title": "Instant Shake Gesture",
        "detail.f1_desc": "Shake mouse while holding items to reveal the shelf. Features 5-level sensitivity and anti-misclick algorithms.",
        "detail.f2_title": "Universal Clipboard Ingest",
        "detail.f2_desc": "Hit <kbd class='px-1.5 py-0.5 bg-slate-100 rounded text-xs text-slate-700 font-mono'>Ctrl + V</kbd> to paste screenshots, remote image URLs, notes, or files automatically.",
        "detail.f3_title": "Zero-Latency Performance",
        "detail.f3_desc": "Comprehensive asynchronous I/O tuning. High-res image hover zoom and single item deletion respond instantly.",
        "detail.f4_title": "One-Click ZIP Packaging",
        "detail.f4_desc": "Collect files from scattered directories and click the ZIP button to bundle them into a zip archive on the spot.",
        "detail.f5_title": "Direct Outlook Attachment",
        "detail.f5_desc": "Deeply integrated with Windows COM APIs. Right-click selected items to attach them directly into active Outlook drafts.",
        "detail.f6_title": "Drop Protection & Lock",
        "detail.f6_desc": "Releasing inside shelf preserves original files. Dialogs automatically lock shelf to prevent unexpected hiding.",

        "down.title": "Download Free Trial Now",
        "down.desc": "No registration required. 100% offline local processing. Experience the fluid shake-to-summon gesture firsthand.",
        "down.btn_installer": "Download Windows Setup (v1.4.0)",
        "down.btn_portable": "Download Portable (.zip)",
        "down.btn_buy": "Purchase Perpetual License",
        "down.f1": "Compatible with Windows 10 / 11 (64-bit)",
        "down.f2": "100% Local & Safe Without Backdoors",
        "down.f3": "Ultra-lightweight (~35MB install footprint)",

        "price.badge": "Simple & Fair Pricing",
        "price.title": "One-Time Purchase, Perpetual Use",
        "price.desc": "No recurring monthly fees. Multiplied productivity for the price of a cup of coffee.",
        "price.tag": "Lifetime Commercial License",
        "price.period": "/ Perpetual License",
        "price.feat1": "Permanent unlock of all Pro features (ZIP bundling, Outlook drop, batch resizing)",
        "price.feat2": "Single license key supports concurrent activation on 2 personal Windows devices",
        "price.feat3": "Includes 1 year of free maintenance & bug fixes (major OS rewrites sold separately)",
        "price.feat4": "Zero ads, 100% local offline processing, zero cloud telemetry",
        "price.btn_shopee": "Official Shopee Store Purchase (Instant Key Delivery)",
        "price.sub": "Automated instant digital delivery upon checkout",

        "faq.title": "Frequently Asked Questions",
        "faq.desc": "Answers regarding licensing, compatibility, and features.",
        "faq.q1": "Q: Which Windows versions are supported?",
        "faq.a1": "KyteShelf is built specifically for 64-bit Windows 10 (version 1809+) and Windows 11, with native support for both Dark Mode and Light Mode.",
        "faq.q2": "Q: Will antivirus or Windows Defender flag KyteShelf?",
        "faq.a2": "Because KyteShelf uses native Windows Global Mouse Hooks to detect shake gestures, some antivirus tools may prompt initially. KyteShelf runs 100% offline with zero malicious telemetry. Please add it to trusted applications.",
        "faq.q3": "Q: Can I use my license after changing or reinstalling PCs?",
        "faq.a3": "Yes! Each license key permits 2 concurrent device activations. If you upgrade hardware, contact support (<a href='mailto:support@aisming.com' class='text-blue-600 hover:underline font-semibold'>support@aisming.com</a>) for a free quota reset.",
        "faq.q4": "Q: How do I receive and activate my key after purchase?",
        "faq.a4": "Upon checkout, the automated delivery system sends your license key and installation instructions within 1 minute. Enter it in the app to unlock all features immediately.",
        "faq.q5": "Q: What is the maintenance period and update policy for perpetual purchases?",
        "faq.a5": "Licenses are one-time perpetual purchases including one year of free maintenance and bug fixes. If future major operating system overhauls (such as major Windows version upgrades) necessitate substantial software refactoring, new major releases will be sold separately.",

        "footer.slogan": "© 2026 KyteShelf. All rights reserved. Built to elevate Windows desktop productivity.",
        "footer.terms": "Terms of Service",
        "footer.privacy": "Privacy Policy",
        "footer.support": "Technical Support"
    }
};

let currentLang = 'zh_TW';

function getInitialLanguage() {
    const saved = localStorage.getItem('kyte_shelf_lang');
    if (saved && (saved === 'zh_TW' || saved === 'en_US')) {
        return saved;
    }
    const sysLang = navigator.language || navigator.userLanguage || '';
    if (sysLang.toLowerCase().includes('zh')) {
        return 'zh_TW';
    }
    return 'en_US';
}

function applyLanguage(lang) {
    currentLang = lang;
    localStorage.setItem('kyte_shelf_lang', lang);
    document.documentElement.lang = lang === 'zh_TW' ? 'zh-TW' : 'en';

    const dict = TRANSLATIONS[lang] || TRANSLATIONS.zh_TW;

    if (dict["page.title"]) {
        document.title = dict["page.title"];
    }

    const elements = document.querySelectorAll('[data-i18n]');
    elements.forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (dict[key]) {
            el.innerHTML = dict[key];
        }
    });

    const langBtnText = document.getElementById('lang-btn-text');
    if (langBtnText) {
        langBtnText.textContent = lang === 'zh_TW' ? 'EN' : '繁中';
    }
}

function toggleLanguage() {
    const nextLang = currentLang === 'zh_TW' ? 'en_US' : 'zh_TW';
    applyLanguage(nextLang);
}

document.addEventListener('DOMContentLoaded', () => {
    const initial = getInitialLanguage();
    applyLanguage(initial);

    const toggleBtn = document.getElementById('lang-toggle-btn');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', toggleLanguage);
    }
});
