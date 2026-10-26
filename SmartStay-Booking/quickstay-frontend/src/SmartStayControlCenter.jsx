import React, { useState, useEffect } from "react";
import { QRCodeSVG } from "qrcode.react";
import { useApp } from "./context.jsx";
import "./control-center.css";

const getApiBase = () => "/api";

const UI_TEXT = {
  vi: {
    systemTitle: "Hệ Thống Hướng Dẫn & Quản Lý SmartStay",
    systemSub: "Định vị GPS dẫn đường đến khách sạn, thuyết minh hướng dẫn sử dụng đồ vật và các chức năng đồng bộ.",
    admin: "Quản trị:",
    adminLogin: "Đăng nhập Quản trị viên",
    backClassic: "Quay lại Trang Đặt Phòng Cũ",
    tab1: "1. Định vị GPS & Thuyết minh Hướng dẫn Khách",
    tab2: "2. Đa ngôn ngữ Giao diện (ui_i18n)",
    tab3: "3. Thuyết minh & Gói Offline (audio)",
    tab4: "4. Bản đồ, Fallback & Làm nóng (content)",
    tab5: "5. Cổng Kiểm soát, Chủ nhà & Phân quyền (admin)",
    tab6: "6. Mã QR & Giám Sát Khách (Dashboard)",
    sec1Title: "Mục 1: Định vị GPS Khách Hàng & Dẫn Đường Đến Khách Sạn",
    sec1Sub: "Tự động tính khoảng cách và kích hoạt vùng Geofence trong bán kính 30 mét",
    getGpsBtn: "Lấy vị trí GPS hiện tại của tôi",
    updateGpsBtn: "Cập nhật vị trí GPS",
    gpsStatusLabel: "Trạng thái định vị:",
    selectHotel: "Chọn khách sạn / homestay bạn muốn đến:",
    audioLang: "Ngôn ngữ thuyết minh:",
    distLabel: "Khoảng cách từ bạn đến khách sạn:",
    insideGeofence: "Đã ở trong phạm vi Geofence 30m (Đã đến nơi)",
    outsideGeofence: "Cách phạm vi Geofence",
    openMapBtn: "Mở Chỉ Đường Trên Google Maps",
    listenDirBtn: "Nghe Thuyết Minh Chỉ Đường",
    audioPreparing: "Đang chuẩn bị âm thanh...",
    checkinGuideLabel: "Hướng dẫn nhận phòng:",
    sec2Title: "Mục 2: Thuyết Minh Hướng Dẫn Sử Dụng Đồ Vật Trong Phòng",
    sec2Sub: "Giọng đọc tự nhiên hỗ trợ khách quốc tế và khách trong nước",
    sec2Intro: "Chọn thiết bị hoặc tiện nghi trong phòng quý khách muốn nghe hướng dẫn sử dụng:",
    contentLabel: "Nội dung:",
    playAudioBtn: "Phát Giọng Đọc Thuyết Minh",
    creatingVoice: "Đang tạo giọng đọc...",
    cacheHit: "HIT (Đã lưu sẵn, chi phí 0đ)",
    cacheMiss: "MISS (Vừa tổng hợp mới)",
    cacheLabel: "Bộ nhớ đệm:",
    voiceLabel: "Giọng đọc:",
    // Tab 2
    i18nTitle: "Đa Ngôn Ngữ Giao Diện (/api/v1/ui-bundles/{locale})",
    i18nSub: "5 ngôn ngữ tĩnh và các ngôn ngữ hiếm",
    statusLabel: "Trạng thái:",
    retryBtn: "Thử lại (?retry=true)",
    sourceHashLabel: "Mã băm nguồn (source_hash):",
    fallbackLabel: "Chế độ tạm:",
    fallbackYes: "Có (Đang dùng bản tiếng Anh tạm thời chờ dịch ngầm)",
    fallbackNo: "Không (Bản dịch chuẩn)",
    colKey: "Khóa văn bản (Key)",
    colPreserved: "Nội dung đã bảo toàn biến giữ chỗ (Placeholder)",
    loadingBundle: "Đang tải gói dịch thuật...",
    // Tab 3
    audioFactoryTitle: "Nhà Máy Thuyết Minh & Gói Âm Thanh Ngoại Tuyến (/audio)",
    audioFactorySub: "VOICE_CATALOG_TTL = 6 giờ",
    refreshVoicesBtn: "Làm mới danh mục giọng đọc",
    ttlLabel: "Thời gian hiệu lực danh mục:",
    hours: "giờ",
    minutes: "phút",
    colLang: "Ngôn ngữ",
    colVoiceName: "Tên Giọng Neural",
    colShortCode: "Mã ngắn",
    colProvider: "Nhà cung cấp",
    offlinePackTitle: "Gói Tải Xuống Ngoại Tuyến (/audio/pack-manifest)",
    scanMp3Btn: "Quét danh sách file MP3",
    packVersionLabel: "Phiên bản gói:",
    totalFilesLabel: "Tổng số file:",
    totalSizeLabel: "Dung lượng:",
    colFilename: "Tên tệp",
    colSize: "Kích thước",
    colSha256: "Mã băm SHA-256",
    colDownload: "Đường dẫn",
    downloadBtn: "Tải về",
    noAudioFiles: "Chưa có file âm thanh sẵn trong hệ thống cho ngôn ngữ này.",
    // Tab 4
    mapSyncTitle: "Bản Đồ, 3-Tier Fallback & 3 Luồng Kích Hoạt",
    mapSyncSub: "Delta Sync, ETag, On-demand, Hotset, Warmup",
    hotsetBtn: "Làm nóng vùng lân cận (prepare-hotset)",
    ondemandBtn: "Thuyết minh tức thời Tier 1.5 (on-demand)",
    warmupBtn: "Làm nóng toàn bộ (warmup)",
    checkEtagBtn: "Kiểm tra Delta Sync (ETag 304)",
    colPropName: "Tên cơ sở",
    colPropAddress: "Địa chỉ",
    colPropDist: "Khoảng cách",
    colPropTier: "Phân cấp Fallback",
    colPropRooms: "Hạng phòng",
    // Tab 5
    gateTitle: "Cổng Kiểm Soát Tiếng Anh (AudioTaskManager)",
    refreshTasksBtn: "Cập nhật tác vụ",
    colTaskId: "Mã tác vụ",
    colTaskHotel: "Khách sạn",
    colTaskProgress: "Tiến độ",
    colTaskStatus: "Trạng thái",
    colTaskGate: "Cổng Step-English",
    colTaskControls: "Điều khiển",
    noAudioTasks: "Chưa có tác vụ audio nào trong hệ thống.",
    openGateBtn: "Mở Cổng Step-English",
    pauseBtn: "Dừng",
    resumeBtn: "Tiếp",
    cancelBtn: "Hủy",
    ownerTitle: "Quản Lý Chủ Nhà & Giải Mã CCCD (Fernet v1 + Audit Logs)",
    colRegId: "Mã hồ sơ",
    colRegName: "Tên cơ sở",
    colRegAddr: "Địa chỉ",
    colRegStatus: "Trạng thái",
    colRegCccd: "Số CCCD",
    noRegistrations: "Chưa có hồ sơ chủ nhà đăng ký nào.",
    decryptBtn: "Giải mã CCCD",
    rbacTitle: "Ma Trận 32 Quyền / 9 Miền RBAC (/admin/permissions)",
    colDomain: "Miền quyền",
    colPerms: "Danh mục quyền chi tiết",
    // Tab 6: QR Code
    qrDashboardTitle: "Mã QR Truy Cập & Giám Sát Tình Hình Khách Hàng",
    qrDashboardSub: "Khách quét mã QR để truy cập trực tiếp vào trang web / phòng khách sạn, tình hình quét và truy cập được cập nhật thời gian thực vào Dashboard",
    qrCardTotal: "Tổng lượt quét QR",
    qrCardToday: "Khách quét hôm nay",
    qrCardActive: "Đang trực tuyến",
    qrCardDevice: "Thiết bị hàng đầu",
    qrGenTitle: "Bộ Tạo Mã QR Động & In Standee",
    qrNetworkHost: "Địa chỉ mạng truy cập (Host):",
    qrTargetDest: "Trang đích khi khách quét mã:",
    qrSimulateBtn: "Mô Phỏng 1 Lượt Khách Quét Mã",
    qrDownloadBtn: "Tải Mã QR (SVG)",
    qrPrintBtn: "In Mã QR Đặt Bàn / Lễ Tân",
    qrLogTitle: "Nhật Ký Tình Hình Quét Mã Thời Gian Thực",
    qrClearBtn: "Xóa nhật ký",
    qrColTime: "Thời gian",
    qrColStay: "Cơ sở lưu trú",
    qrColDevice: "Thiết bị",
    qrColIp: "Địa chỉ IP",
    qrColAction: "Hành động khách",
    qrColStatus: "Tình trạng",
  },
  en: {
    systemTitle: "SmartStay Guidance & Management System",
    systemSub: "GPS navigation to hotels, in-room amenities audio guide, and system synchronization.",
    admin: "Admin:",
    adminLogin: "Admin Login",
    backClassic: "Back to Hotel Booking",
    tab1: "1. GPS Navigation & Guest Audio Guide",
    tab2: "2. UI Multi-language (ui_i18n)",
    tab3: "3. Audio Narration & Offline Pack (audio)",
    tab4: "4. Maps, Fallback & Warmup (content)",
    tab5: "5. Control Gate, Owner & RBAC (admin)",
    tab6: "6. QR Code & Live Guest Monitor (Dashboard)",
    sec1Title: "Section 1: Customer GPS Geolocation & Hotel Navigation",
    sec1Sub: "Automatic distance calculation and 30-meter Geofence perimeter detection",
    getGpsBtn: "Get My Current GPS Location",
    updateGpsBtn: "Update GPS Location",
    gpsStatusLabel: "Location Status:",
    selectHotel: "Select destination hotel / homestay:",
    audioLang: "Audio Guide Language:",
    distLabel: "Distance from your location to hotel:",
    insideGeofence: "Inside 30m Geofence perimeter (Arrived)",
    outsideGeofence: "Away from 30m Geofence by",
    openMapBtn: "Open Directions on Google Maps",
    listenDirBtn: "Listen to Audio Directions",
    audioPreparing: "Preparing audio...",
    checkinGuideLabel: "Check-in Instructions:",
    sec2Title: "Section 2: In-Room Amenities & Equipment Audio Guide",
    sec2Sub: "Natural AI voice guide for international and domestic guests",
    sec2Intro: "Select the in-room equipment or amenity you want audio instructions for:",
    contentLabel: "Content:",
    playAudioBtn: "Play Audio Guide",
    creatingVoice: "Synthesizing voice...",
    cacheHit: "HIT (Cached, zero cost)",
    cacheMiss: "MISS (Newly synthesized)",
    cacheLabel: "Cache Status:",
    voiceLabel: "Voice:",
    // Tab 2
    i18nTitle: "UI Multi-language (/api/v1/ui-bundles/{locale})",
    i18nSub: "5 static languages and rare languages",
    statusLabel: "Status:",
    retryBtn: "Retry (?retry=true)",
    sourceHashLabel: "Source Hash (source_hash):",
    fallbackLabel: "Fallback Mode:",
    fallbackYes: "Yes (English fallback pending background translation)",
    fallbackNo: "No (Native translation)",
    colKey: "Text Key",
    colPreserved: "Placeholder-preserved Content",
    loadingBundle: "Loading i18n bundle...",
    // Tab 3
    audioFactoryTitle: "Audio Narration Factory & Offline Pack (/audio)",
    audioFactorySub: "VOICE_CATALOG_TTL = 6 hours",
    refreshVoicesBtn: "Refresh Voice Catalog",
    ttlLabel: "Catalog TTL remaining:",
    hours: "hours",
    minutes: "minutes",
    colLang: "Language",
    colVoiceName: "Neural Voice Name",
    colShortCode: "Short Code",
    colProvider: "Provider",
    offlinePackTitle: "Offline Download Package (/audio/pack-manifest)",
    scanMp3Btn: "Scan MP3 Files",
    packVersionLabel: "Pack Version:",
    totalFilesLabel: "Total Files:",
    totalSizeLabel: "Total Size:",
    colFilename: "Filename",
    colSize: "Size",
    colSha256: "SHA-256 Hash",
    colDownload: "Path",
    downloadBtn: "Download",
    noAudioFiles: "No audio files available yet for this language.",
    // Tab 4
    mapSyncTitle: "Maps, 3-Tier Fallback & 3 Triggers",
    mapSyncSub: "Delta Sync, ETag, On-demand, Hotset, Warmup",
    hotsetBtn: "Warm up vicinity (prepare-hotset)",
    ondemandBtn: "Instant Audio Tier 1.5 (on-demand)",
    warmupBtn: "Warm up all (warmup)",
    checkEtagBtn: "Check Delta Sync (ETag 304)",
    colPropName: "Property Name",
    colPropAddress: "Address",
    colPropDist: "Distance",
    colPropTier: "Fallback Tier",
    colPropRooms: "Room Types",
    // Tab 5
    gateTitle: "English Control Gate (AudioTaskManager)",
    refreshTasksBtn: "Refresh Tasks",
    colTaskId: "Task ID",
    colTaskHotel: "Hotel",
    colTaskProgress: "Progress",
    colTaskStatus: "Status",
    colTaskGate: "Step-English Gate",
    colTaskControls: "Controls",
    noAudioTasks: "No audio tasks found in the system.",
    openGateBtn: "Open Step-English Gate",
    pauseBtn: "Pause",
    resumeBtn: "Resume",
    cancelBtn: "Cancel",
    ownerTitle: "Owner Management & ID Decryption (Fernet v1 + Audit Logs)",
    colRegId: "Registration ID",
    colRegName: "Property Name",
    colRegAddr: "Address",
    colRegStatus: "Status",
    colRegCccd: "ID Number (CCCD)",
    noRegistrations: "No owner registrations found.",
    decryptBtn: "Decrypt ID",
    rbacTitle: "32 Permissions / 9 Domains RBAC Matrix (/admin/permissions)",
    colDomain: "Permission Domain",
    colPerms: "Detailed Permissions",
    // Tab 6: QR Code
    qrDashboardTitle: "QR Code Access & Real-Time Guest Monitor",
    qrDashboardSub: "Guests scan the QR code to access the hotel/stay instantly, and scan activity updates in real-time on the Dashboard",
    qrCardTotal: "Total QR Scans",
    qrCardToday: "Today's Scans",
    qrCardActive: "Active Visitors",
    qrCardDevice: "Top Device",
    qrGenTitle: "Dynamic QR Code Generator & Standee Print",
    qrNetworkHost: "Network Host Access:",
    qrTargetDest: "Destination Page upon Scan:",
    qrSimulateBtn: "Simulate 1 QR Guest Scan",
    qrDownloadBtn: "Download QR (SVG)",
    qrPrintBtn: "Print Standee QR Code",
    qrLogTitle: "Real-Time QR Scan Activity Log",
    qrClearBtn: "Clear Logs",
    qrColTime: "Timestamp",
    qrColStay: "Property",
    qrColDevice: "Device",
    qrColIp: "IP Address",
    qrColAction: "Guest Action",
    qrColStatus: "Status",
  },
};

export default function SmartStayControlCenter({ onSwitchToClassic }) {
  const appContext = useApp();
  const lang = appContext?.lang || "vi";
  const tr = UI_TEXT[lang] || UI_TEXT.vi;

  const [activeTab, setActiveTab] = useState(() => {
    return window.location.hash.includes("tab=qr") ? "qr" : "guide";
  });

  // State cho Tab QR & Giám sát khách hàng
  const [qrHost, setQrHost] = useState("http://172.20.10.3:4173");
  const [customHost, setCustomHost] = useState("");
  const [qrTarget, setQrTarget] = useState("/#/?ref=qr");
  const [qrStats, setQrStats] = useState({
    total_scans: 2,
    today_scans: 2,
    active_visitors: 2,
    top_device: "Mobile",
    recent_scans: [],
  });

  // Quản trị viên token
  const [adminToken, setAdminToken] = useState(() => localStorage.getItem("smartstay_admin_token") || "");
  const [adminUser, setAdminUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("smartstay_admin_user") || "null");
    } catch {
      return null;
    }
  });

  const apiHeaders = (contentType = true) => {
    const h = { Accept: "application/json" };
    if (contentType) h["Content-Type"] = "application/json";
    if (adminToken) h["Authorization"] = `Bearer ${adminToken}`;
    return h;
  };

  // ========================================================
  // 1. MỤC ĐỊNH VỊ GPS & THUYẾT MINH HƯỚNG DẪN KHÁCH HÀNG
  // ========================================================
  // Vị trí mặc định Sài Gòn (TP. Hồ Chí Minh)
  const [userLat, setUserLat] = useState(10.7769);
  const [userLng, setUserLng] = useState(106.7009);
  const [mapKey, setMapKey] = useState(0);
  const [gpsStatus, setGpsStatus] = useState(
    lang === "en"
      ? "Location: Ho Chi Minh City (Saigon) - 10.7769, 106.7009"
      : "Vị trí của bạn: TP. Hồ Chí Minh (Sài Gòn) - 10.7769, 106.7009"
  );
  const [hotels, setHotels] = useState([]);
  const [selectedHotel, setSelectedHotel] = useState(null);
  const [guideLang, setGuideLang] = useState(lang);

  useEffect(() => {
    setGuideLang(lang);
    setGpsStatus(
      lang === "en"
        ? `Location: Ho Chi Minh City (Saigon) - ${userLat.toFixed(4)}, ${userLng.toFixed(4)}`
        : `Vị trí của bạn: TP. Hồ Chí Minh (Sài Gòn) - ${userLat.toFixed(4)}, ${userLng.toFixed(4)}`
    );
  }, [lang]);

  // Hướng dẫn đồ vật trong phòng
  const [selectedItemKey, setSelectedItemKey] = useState("smart_lock");
  const [guideAudioUrl, setGuideAudioUrl] = useState("");
  const [guideAudioLoading, setGuideAudioLoading] = useState(false);
  const [guideAudioMeta, setGuideAudioMeta] = useState(null);

  const inRoomItems = {
    smart_lock: {
      title: {
        vi: "Khóa cửa thông minh bằng mã PIN",
        en: "Smart Door PIN Lock",
      },
      text: {
        vi: "Để mở khóa cửa thông minh, quý khách vui lòng chạm tay vào màn hình cảm ứng để bật sáng bàn phím. Sau đó nhập đúng 4 chữ số mã PIN được gửi trong tin nhắn và nhấn phím thăng (#). Khi đèn chuyển sang màu xanh và có tiếng bíp, quý khách gạt tay nắm xuống để mở cửa. Khi ra khỏi phòng, cửa sẽ tự động khóa sau 5 giây.",
        en: "To unlock the smart door, please touch the digital keypad to wake it up. Enter your 4-digit PIN code and press the hash key (#). When the green indicator lights up with a chime, push down the handle to open. The door locks automatically after 5 seconds.",
        zh: "如需打开智能门锁，请先轻触数字键盘点亮屏幕。输入您的4位密码并按井号键（#）。听到提示音且指示灯变绿后，向下压把手即可开门。出门后5秒内门锁会自动反锁。",
        ja: "スマートロックを開錠するには、テンキー画面に触れて起動してください。暗証番号を入力し、シャープキー（#）を押します。緑のランプが点灯し電子音が鳴ったら、ドアノブを下げて入室してください。退出後5秒で自動施錠されます。",
        ko: "스마트 도어록을 열려면 터치패드를 가볍게 터치해 활성화해 주세요. 4자리 핀 번호를 입력한 후 샵 버튼(#)을 누르면 신호음과 함께 문이 열립니다. 외출 시 5초 후 자동으로 잠깁니다.",
        fr: "Pour déverrouiller la porte intelligente, touchez le clavier tactile. Entrez votre code PIN à 4 chiffres et appuyez sur la touche dièse (#). Ouvrez lorsque le voyant passe au vert.",
      },
    },
    air_conditioner: {
      title: {
        vi: "Điều khiển Điều hòa / Máy lạnh",
        en: "Air Conditioner Remote",
      },
      text: {
        vi: "Điều khiển điều hòa được đặt trên bàn cạnh giường ngủ. Nhấn nút Nguồn màu đỏ để bật hoặc tắt máy. Sử dụng hai phím mũi tên Lên và Xuống để điều chỉnh nhiệt độ; mức nhiệt độ khuyến nghị để tiết kiệm năng lượng và thoải mái là 25 đến 26 độ C. Nhấn nút Mode để chuyển đổi chế độ làm mát Cool hoặc quạt Fan.",
        en: "The remote control is on the bedside table. Press the red Power button to turn on or off. Use the Up and Down arrows to set your preferred temperature (recommended 25 to 26 degrees Celsius). Press Mode to switch between Cool and Fan.",
        zh: "空调遥控器放置在床头柜上。按红色电源键开机或关机。按上下箭头调节温度，建议设定在25至26摄氏度。按Mode键可在制冷与送风模式间切换。",
        ja: "エアコンのリモコンはベッドサイドにございます。赤い電源ボタンで入切し、上下矢印で温度を設定してください（推奨25〜26度）。Modeボタンで冷房と送風を切り替えられます。",
        ko: "에어컨 리모컨은 침대 옆 협탁에 있습니다. 빨간색 전원 버튼을 눌러 켜고 끌 수 있으며, 추천 희망 온도는 25~26도입니다.",
        fr: "La télécommande de la climatisation est sur la table de chevet. Appuyez sur le bouton rouge pour allumer. Réglez la température conseillée entre 25 et 26 degrés.",
      },
    },
    water_heater: {
      title: {
        vi: "Bình nước nóng & Vòi sen phòng tắm",
        en: "Water Heater & Shower",
      },
      text: {
        vi: "Công tắc bình nước nóng nằm ngay bên ngoài cửa phòng tắm. Vui lòng bật công tắc trước khi tắm khoảng 10 đến 15 phút để nước đạt độ nóng thích hợp. Khi sử dụng vòi sen, xoay cần gạt từ từ sang bên trái để lấy nước nóng và sang bên phải để lấy nước lạnh nhằm tránh bị bỏng.",
        en: "The water heater switch is located outside the bathroom door. Please turn it on 10 to 15 minutes before showering. When using the shower lever, turn gently to the left for hot water and to the right for cold water.",
        zh: "热水器开关位于浴室门外。请在洗澡前10至15分钟开启。调节淋浴喷头时，把手向左旋转为热水，向右为冷水，请缓慢调节以免烫伤。",
        ja: "給湯器のスイッチは浴室ドアの外側にあります。シャワーの10〜15分前にお入れください。レバーを左に回すと温水、右に回すと冷水が出ます。",
        ko: "온수기 스위치는 욕실 문 밖에 있습니다. 샤워 10~15분 전에 켜주세요. 수전 레버를 왼쪽으로 돌리면 온수가 나옵니다.",
        fr: "L'interrupteur du chauffe-eau se trouve à côté de la porte de la salle de bain. Allumez-le 10 à 15 minutes avant votre douche.",
      },
    },
    wifi_tv: {
      title: {
        vi: "Mạng Wi-Fi & Smart TV thông minh",
        en: "Wi-Fi & Smart TV",
      },
      text: {
        vi: "Mạng Wi-Fi của phòng là SmartStay Guest, không yêu cầu mật khẩu hoặc mật khẩu in ở mặt sau điều khiển TV. Quý khách sử dụng điều khiển TV thông minh để truy cập nhanh các ứng dụng YouTube và Netflix có sẵn tài khoản khách.",
        en: "The Wi-Fi network name is SmartStay Guest with no password required. Use the smart TV remote control to access YouTube and complimentary Netflix streaming directly.",
        zh: "无线Wi-Fi名称为SmartStay Guest，无需密码即可连接。使用智能电视遥控器可直接观看预装的YouTube和Netflix流媒体服务。",
        ja: "Wi-Fiネットワーク名は SmartStay Guest です。パスワードは不要です。テレビリモコンのホームボタンからYouTubeやNetflixをご利用いただけます。",
        ko: "와이파이 이름은 SmartStay Guest이며 비밀번호 없이 바로 연결 가능합니다. 스마트 TV 리모컨으로 유튜브와 넷플릭스를 이용하실 수 있습니다.",
        fr: "Le réseau Wi-Fi est SmartStay Guest sans mot de passe. Utilisez la télécommande pour profiter de Netflix et YouTube.",
      },
    },
    electric_kettle: {
      title: {
        vi: "Bình đun siêu tốc & Nước uống miễn phí",
        en: "Electric Kettle & Drinking Water",
      },
      text: {
        vi: "Bình đun siêu tốc cùng trà, cà phê và hai chai nước suối miễn phí được chuẩn bị trên kệ bếp. Để đun nước, cho nước sạch vào bình không vượt quá vạch Max, đậy nắp và gạt lẫy công tắc ở phía dưới tay cầm. Bình sẽ tự động ngắt điện khi nước sôi.",
        en: "The electric kettle, tea, coffee, and complimentary bottled water are available on the counter. Fill with water below the Max line and press the lever switch. It shuts off automatically once boiled.",
        zh: "电热水壶、茶包、咖啡及两瓶免费矿泉水备在餐台上。注水请勿超过Max刻度线，按下手柄下方的开关，水开后会自动断电。",
        ja: "電気ケトル、お茶、無料のミネラルウォーターはお部屋のカウンターにございます。規定量まで水を入れてスイッチを下げると、沸騰後に自動停止します。",
        ko: "전기 주전자와 무료 생수, 차가 준비되어 있습니다. 물을 넣고 스위치를 내리면 끓은 후 자동 차단됩니다.",
        fr: "La bouilloire électrique, le thé et les bouteilles d'eau gratuites sont à votre disposition. Remplissez sous la ligne Max et allumez.",
      },
    },
  };

  // Lấy vị trí GPS thực tế của khách hàng
  const handleGetLocation = () => {
    const saigonLat = 10.7769;
    const saigonLng = 106.7009;

    if (!navigator.geolocation) {
      setUserLat(saigonLat);
      setUserLng(saigonLng);
      setMapKey((k) => k + 1);
      setGpsStatus(
        lang === "en"
          ? "Location: Ho Chi Minh City (Saigon) - 10.7769, 106.7009"
          : "Vị trí của bạn: TP. Hồ Chí Minh (Sài Gòn) - 10.7769, 106.7009"
      );
      fetchNearbyHotels(saigonLat, saigonLng);
      return;
    }

    setGpsStatus(lang === "en" ? "Scanning GPS satellite location in Saigon..." : "Đang quét vị trí vệ tinh GPS tại Sài Gòn...");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setUserLat(pos.coords.latitude);
        setUserLng(pos.coords.longitude);
        setMapKey((k) => k + 1);
        setGpsStatus(
          lang === "en"
            ? `Your exact location: ${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)} (Saigon)`
            : `Đã nhận tọa độ thực tế tại Sài Gòn: ${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`
        );
        fetchNearbyHotels(pos.coords.latitude, pos.coords.longitude);
      },
      (err) => {
        setUserLat(saigonLat);
        setUserLng(saigonLng);
        setMapKey((k) => k + 1);
        setGpsStatus(
          lang === "en"
            ? "Your location: Ho Chi Minh City (Saigon) - 10.7769, 106.7009"
            : "Vị trí của bạn: TP. Hồ Chí Minh (Sài Gòn) - 10.7769, 106.7009"
        );
        fetchNearbyHotels(saigonLat, saigonLng);
      },
      { enableHighAccuracy: true, timeout: 3000, maximumAge: 0 }
    );
  };

  // Tải danh sách khách sạn lân cận từ backend
  const fetchNearbyHotels = async (lat = userLat, lng = userLng) => {
    try {
      const res = await fetch(`${getApiBase()}/content/nearby?lat=${lat}&lon=${lng}&radius_m=50000`);
      const data = await res.json();
      if (Array.isArray(data) && data.length > 0) {
        setHotels(data);
        if (!selectedHotel) setSelectedHotel(data[0]);
      } else {
        // Fallback danh sách khách sạn
        const mockHotels = [
          {
            id: "saigon-riverside",
            name: "SmartStay Saigon Riverside Hotel",
            address: "15 Tôn Đức Thắng, Bến Nghé, Quận 1, TP. Hồ Chí Minh",
            latitude: 10.7738,
            longitude: 106.7072,
            distance_m: 650,
            check_in_instructions: "Quý khách đến quầy lễ tân tầng 1 xuất trình CCCD/Hộ chiếu để nhận thẻ phòng từ 14:00.",
          },
          {
            id: "saigon-central",
            name: "SmartStay Central Ben Thanh Villa",
            address: "136 Lê Thánh Tôn, Bến Thành, Quận 1, TP. Hồ Chí Minh",
            latitude: 10.7725,
            longitude: 106.6980,
            distance_m: 25,
            check_in_instructions: "Nhập mã PIN 4 chữ số trên cửa thông minh và bấm # để mở cửa nhận phòng tự động.",
          },
          {
            id: "saigon-heritage",
            name: "SmartStay Landmark Heritage Villa",
            address: "208 Nguyễn Hữu Cảnh, Phường 22, Bình Thạnh, TP. Hồ Chí Minh",
            latitude: 10.7938,
            longitude: 106.7219,
            distance_m: 2800,
            check_in_instructions: "Lấy chìa khóa trong hộp lockbox tại sảnh bằng mật mã 9988.",
          },
        ];
        setHotels(mockHotels);
        if (!selectedHotel) setSelectedHotel(mockHotels[0]);
      }
    } catch {
      // Fallback khi offline
      const mockHotels = [
        {
          id: "saigon-riverside",
          name: "SmartStay Saigon Riverside Hotel",
          address: "15 Tôn Đức Thắng, Bến Nghé, Quận 1, TP. Hồ Chí Minh",
          latitude: 10.7738,
          longitude: 106.7072,
          distance_m: 650,
          check_in_instructions: "Quý khách đến quầy lễ tân tầng 1 xuất trình CCCD/Hộ chiếu để nhận thẻ phòng từ 14:00.",
        },
      ];
      setHotels(mockHotels);
      if (!selectedHotel) setSelectedHotel(mockHotels[0]);
    }
  };

  // Tự động xác thực tài khoản quản trị để gọi các API thuyết minh / quản trị
  const ensureAuthToken = async () => {
    if (adminToken) return adminToken;
    try {
      const res = await fetch(`${getApiBase()}/admin/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: "superadmin",
          password: "-VFzgMKxzLAJB5RzUaN-K0JrffpvD_SU",
          mode: "bearer",
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.access_token) {
          localStorage.setItem("smartstay_admin_token", data.access_token);
          setAdminToken(data.access_token);
          const u = { username: "superadmin", role: "superadmin" };
          localStorage.setItem("smartstay_admin_user", JSON.stringify(u));
          setAdminUser(u);
          return data.access_token;
        }
      }
    } catch {}
    return null;
  };

  useEffect(() => {
    ensureAuthToken();
    fetchNearbyHotels();
  }, []);

  // Gọi API TTS tạo giọng nói
  const playNarration = async (text) => {
    setGuideAudioLoading(true);
    try {
      let token = adminToken;
      if (!token) {
        token = await ensureAuthToken();
      }

      const headers = {
        Accept: "*/*",
        "Content-Type": "application/json",
      };
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      let res = await fetch(`${getApiBase()}/audio/tts`, {
        method: "POST",
        headers,
        body: JSON.stringify({ text, lang: guideLang }),
      });

      // Nếu token hết hạn (401), tự động lấy token mới và gọi lại 1 lần
      if (res.status === 401) {
        localStorage.removeItem("smartstay_admin_token");
        token = await ensureAuthToken();
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
          res = await fetch(`${getApiBase()}/audio/tts`, {
            method: "POST",
            headers,
            body: JSON.stringify({ text, lang: guideLang }),
          });
        }
      }

      if (!res.ok) {
        let msg = "Không thể tải giọng đọc";
        try {
          const errData = await res.json();
          msg = errData.detail || msg;
        } catch {}
        throw new Error(msg);
      }

      const cacheHeader = res.headers.get("X-Cache") || "MISS";
      const voiceHeader = res.headers.get("X-Audio-Voice") || (guideLang === "en" ? "en-US-JennyNeural" : "vi-VN-HoaiMyNeural");
      const blob = await res.blob();
      const audioUrl = URL.createObjectURL(blob);
      setGuideAudioUrl(audioUrl);
      setGuideAudioMeta({
        cache: cacheHeader,
        voice: voiceHeader,
      });
    } catch (e) {
      // Dự phòng Web Speech API để khách hàng luôn luôn nghe được giọng nói chỉ dẫn
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        try {
          window.speechSynthesis.cancel();
          const utter = new SpeechSynthesisUtterance(text);
          utter.lang = guideLang === "vi" ? "vi-VN" : guideLang === "en" ? "en-US" : guideLang;
          window.speechSynthesis.speak(utter);
          setGuideAudioMeta({
            cache: "BROWSER_SPEECH",
            voice: `Web Speech Synthesis (${guideLang.toUpperCase()})`,
          });
          return;
        } catch {}
      }
      alert(
        lang === "en"
          ? `Audio narration error: ${e.message}\n(Click Admin Login at the top if the backend requires admin privileges)`
          : `Lỗi phát thuyết minh: ${e.message}\n(Hãy bấm Đăng nhập Admin ở góc trên nếu backend yêu cầu quyền tạo audio mới)`
      );
    } finally {
      setGuideAudioLoading(false);
    }
  };

  // Thuyết minh chỉ đường
  const handlePlayDirectionsAudio = () => {
    if (!selectedHotel) return;
    const dist = Math.round(selectedHotel.distance_m || 0);
    const distText = dist < 1000 
      ? (guideLang === "en" ? `${dist} meters` : `${dist} mét`)
      : (guideLang === "en" ? `${(dist / 1000).toFixed(1)} km` : `${(dist / 1000).toFixed(1)} ki-lô-mét`);
    const text = guideLang === "en"
      ? `Directions to ${selectedHotel.name}. Located at ${selectedHotel.address}. The distance from your location to the hotel is ${distText}. Please follow the route on the map. When you are within 30 meters, the system will automatically confirm your arrival. Check-in instructions: ${selectedHotel.check_in_instructions || "Check in after 2:00 PM at front desk"}.`
      : `Hướng dẫn đường đi đến ${selectedHotel.name}. Khách sạn tọa lạc tại địa chỉ ${selectedHotel.address}. Khoảng cách từ vị trí hiện tại của quý khách đến khách sạn là ${distText}. Quý khách vui lòng đi theo lộ trình hiển thị trên bản đồ. Khi đến gần trong phạm vi 30 mét, hệ thống sẽ tự động xác nhận quý khách đã tới nơi. Hướng dẫn nhận phòng: ${selectedHotel.check_in_instructions || "Nhận phòng sau 14 giờ tại sảnh lễ tân"}.`;
    playNarration(text);
  };

  // Thuyết minh đồ vật phòng
  const handlePlayInRoomAudio = () => {
    const item = inRoomItems[selectedItemKey];
    if (!item) return;
    const text = item.text[guideLang] || item.text["vi"];
    playNarration(text);
  };

  // ========================================================
  // 2. CÁC TÍNH NĂNG QUẢN TRỊ HỆ THỐNG PHỤ TRỢ (4 PHÂN KHU)
  // ========================================================
  // ui_i18n
  const [i18nBundle, setI18nBundle] = useState(null);
  const [i18nLocale, setI18nLocale] = useState("vi");
  const fetchI18n = async (loc = i18nLocale, retry = false) => {
    try {
      const res = await fetch(`${getApiBase()}/api/v1/ui-bundles/${loc}${retry ? "?retry=true" : ""}`);
      const data = await res.json();
      setI18nBundle(data);
    } catch {}
  };

  useEffect(() => {
    if (activeTab === "i18n") fetchI18n(i18nLocale);
  }, [activeTab, i18nLocale]);

  // audio catalog & manifest
  const [voiceCatalog, setVoiceCatalog] = useState([]);
  const [voiceTtl, setVoiceTtl] = useState(21600);
  const [manifestData, setManifestData] = useState(null);

  const fetchVoices = async (force = false) => {
    try {
      const res = await fetch(`${getApiBase()}/audio/voices${force ? "?force_refresh=true" : ""}`);
      const data = await res.json();
      setVoiceCatalog(data.voices || []);
      setVoiceTtl(data.ttl_seconds || 21600);
    } catch {}
  };

  const fetchManifest = async () => {
    try {
      const res = await fetch(`${getApiBase()}/audio/pack-manifest?lang=${guideLang}`);
      const data = await res.json();
      setManifestData(data);
    } catch {}
  };

  useEffect(() => {
    if (activeTab === "audio") {
      fetchVoices();
      fetchManifest();
    }
  }, [activeTab]);

  // Delta Sync & Fallback
  const [syncNotice, setSyncNotice] = useState("");
  const handleHotset = async () => {
    try {
      const res = await fetch(`${getApiBase()}/localization/prepare-hotset`, {
        method: "POST",
        headers: apiHeaders(),
        body: JSON.stringify({ lat: userLat, lon: userLng, radius_m: 5000, target_langs: ["en", "zh"] }),
      });
      const data = await res.json();
      alert(
        lang === "en"
          ? `Vicinity warmed up: ${data.prepared_count} properties ready, ${data.queued_count} queued.`
          : `Đã làm nóng vùng lân cận: ${data.prepared_count} cơ sở đã sẵn sàng, ${data.queued_count} cơ sở đang xử lý.`
      );
    } catch (e) {
      alert("Error: " + e.message);
    }
  };

  const handleWarmup = async () => {
    try {
      const res = await fetch(`${getApiBase()}/localization/warmup`, {
        method: "POST",
        headers: apiHeaders(),
      });
      const data = await res.json();
      alert(
        lang === "en"
          ? `Warmup launched: Progress ${data.progress_pct}% (Idempotent: ${String(data.idempotent_reused)})`
          : `Đã khởi chạy Warmup toàn bộ: Tiến độ ${data.progress_pct}% (Idempotent: ${String(data.idempotent_reused)})`
      );
    } catch (e) {
      alert(lang === "en" ? "Warmup error (requires admin privileges): " + e.message : "Lỗi Warmup (yêu cầu quyền quản trị): " + e.message);
    }
  };

  const handleCheckEtag = async () => {
    try {
      const oldEtag = localStorage.getItem("smartstay_etag") || "";
      const headers = { ...apiHeaders() };
      if (oldEtag) headers["If-None-Match"] = oldEtag;
      const res = await fetch(`${getApiBase()}/content/sync?lang=${guideLang}`, { headers });
      if (res.status === 304) {
        setSyncNotice(lang === "en" ? "304 Not Modified: Cache is up to date, zero bandwidth used!" : "304 Not Modified: Dữ liệu trên máy bạn đã mới nhất, không tốn thêm băng thông!");
      } else {
        const newEtag = res.headers.get("ETag");
        if (newEtag) localStorage.setItem("smartstay_etag", newEtag);
        setSyncNotice(lang === "en" ? `Sync successful (ETag: ${newEtag?.slice(0, 16)}...)` : `Đồng bộ thành công (ETag: ${newEtag?.slice(0, 16)}...)`);
      }
    } catch (e) {
      setSyncNotice("Sync error: " + e.message);
    }
  };

  // Quản trị viên: AudioTaskManager, Gate & PII
  const [audioTasks, setAudioTasks] = useState([]);
  const [registrations, setRegistrations] = useState([]);
  const [piiValue, setPiiValue] = useState({});
  const [rbacList, setRbacList] = useState(null);

  const fetchAdminData = async () => {
    try {
      const resTasks = await fetch(`${getApiBase()}/audio/tasks`, { headers: apiHeaders() });
      if (resTasks.ok) {
        const d = await resTasks.json();
        setAudioTasks(d.tasks || []);
      }
      const resReg = await fetch(`${getApiBase()}/owner/registrations`, { headers: apiHeaders() });
      if (resReg.ok) {
        const d = await resReg.json();
        setRegistrations(d.items || []);
      }
      const resRbac = await fetch(`${getApiBase()}/admin/permissions`, { headers: apiHeaders() });
      if (resRbac.ok) {
        const d = await resRbac.json();
        setRbacList(d);
      }
    } catch {}
  };

  useEffect(() => {
    if (activeTab === "admin") fetchAdminData();
  }, [activeTab]);

  const handleStepEnglish = async (taskId) => {
    try {
      const res = await fetch(`${getApiBase()}/audio/tasks/${taskId}/step-english`, {
        method: "POST",
        headers: apiHeaders(),
      });
      if (res.ok) {
        alert(lang === "en" ? "Step-English gate opened successfully!" : "Đã mở cổng kiểm định Step-English thành công!");
        fetchAdminData();
      }
    } catch (e) {
      alert("Error: " + e.message);
    }
  };

  const handleTaskControl = async (taskId, action) => {
    try {
      await fetch(`${getApiBase()}/audio/tasks/${taskId}/${action}`, {
        method: "POST",
        headers: apiHeaders(),
      });
      alert(lang === "en" ? `Command ${action} sent for task.` : `Đã gửi lệnh ${action} cho tác vụ.`);
      fetchAdminData();
    } catch (e) {
      alert("Error: " + e.message);
    }
  };

  const handleDecryptCccd = async (regId) => {
    try {
      const res = await fetch(`${getApiBase()}/owner/registrations/${regId}/decrypt-pii`, {
        method: "POST",
        headers: apiHeaders(),
        body: JSON.stringify({ reason: "Customer Verification Audit" }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || (lang === "en" ? "Cannot decrypt ID" : "Không thể giải mã"));
      setPiiValue((p) => ({ ...p, [regId]: data.national_id }));
      alert(lang === "en" ? `Decrypted ID successfully: ${data.national_id}. Logged to audit_logs.` : `Đã giải mã thành công CCCD: ${data.national_id}. Hành động này đã được ghi vào nhật ký kiểm toán (audit_logs).`);
    } catch (e) {
      alert("Error: " + e.message);
    }
  };

  // Đăng nhập SuperAdmin để có token
  const handleAdminLogin = () => {
    const pass = prompt(
      lang === "en" ? "Enter SuperAdmin password:" : "Nhập mật khẩu SuperAdmin:",
      "-VFzgMKxzLAJB5RzUaN-K0JrffpvD_SU"
    );
    if (!pass) return;
    fetch(`${getApiBase()}/admin/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: "superadmin",
        password: pass,
        mode: "bearer",
      }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.access_token) {
          localStorage.setItem("smartstay_admin_token", data.access_token);
          setAdminToken(data.access_token);
          const u = { username: "superadmin", role: "superadmin" };
          localStorage.setItem("smartstay_admin_user", JSON.stringify(u));
          setAdminUser(u);
          alert(lang === "en" ? "SuperAdmin login successful!" : "Đăng nhập SuperAdmin thành công!");
          fetchAdminData();
        } else {
          alert(lang === "en" ? "Invalid password or account: " + (data.detail || "") : "Sai mật khẩu hoặc tài khoản: " + (data.detail || ""));
        }
      })
      .catch((err) => alert(lang === "en" ? "Login error: " + err.message : "Lỗi đăng nhập: " + err.message));
  };

  // Lấy dữ liệu thống kê quét mã QR và tình hình khách hàng
  const fetchQrStats = async () => {
    try {
      const res = await fetch(`${getApiBase()}/analytics/qr-stats`);
      if (res.ok) {
        const data = await res.json();
        setQrStats(data);
      }
    } catch {}
  };

  useEffect(() => {
    fetchQrStats();
    const timer = setInterval(fetchQrStats, 3000);
    return () => clearInterval(timer);
  }, []);

  const handleSimulateScan = async () => {
    try {
      const stay = selectedHotel?.name || "SmartStay Central Ben Thanh Villa";
      const dev = navigator.userAgent.includes("Mobile") ? "Mobile (iPhone / Android)" : "Desktop / Laptop";
      const res = await fetch(`${getApiBase()}/analytics/qr-scan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          stay_id: selectedHotel?.id || "saigon-central",
          stay_name: stay,
          device: dev,
          action: lang === "en" ? "Simulated scan from Dashboard" : "Khách quét mã QR tại quầy tiếp tân",
        }),
      });
      if (res.ok) {
        fetchQrStats();
      }
    } catch (e) {
      alert("Error: " + e.message);
    }
  };

  const handleClearQrLogs = async () => {
    try {
      const res = await fetch(`${getApiBase()}/analytics/qr-clear`, {
        method: "POST",
      });
      if (res.ok) {
        fetchQrStats();
      }
    } catch (e) {
      alert("Error: " + e.message);
    }
  };

  const effectiveHost = customHost.trim() || qrHost;
  const computedQrUrl = `${effectiveHost}${qrTarget}`;

  const handleDownloadQrSvg = () => {
    const svgEl = document.getElementById("smartstay-qr-svg");
    if (!svgEl) return;
    const svgData = new XMLSerializer().serializeToString(svgEl);
    const blob = new Blob([svgData], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `smartstay-qr-${Date.now()}.svg`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handlePrintQr = () => {
    const printWindow = window.open("", "_blank");
    if (!printWindow) return;
    const svgEl = document.getElementById("smartstay-qr-svg");
    const svgHtml = svgEl ? svgEl.outerHTML : "";
    printWindow.document.write(`
      <!DOCTYPE html>
      <html>
        <head>
          <title>SmartStay Standee QR Code</title>
          <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; text-align: center; padding: 40px; margin: 0; background: #fff; }
            .card { max-width: 420px; margin: 0 auto; border: 2px solid #1e3a8a; border-radius: 16px; padding: 36px 24px; box-shadow: 0 4px 16px rgba(0,0,0,0.08); }
            h1 { color: #1e3a8a; font-size: 26px; margin: 0 0 6px 0; letter-spacing: 1px; font-weight: 800; }
            .sub { color: #4b5563; font-size: 14px; margin: 0 0 24px 0; }
            .qr-wrapper { margin: 20px auto; display: inline-block; padding: 14px; background: #fff; border-radius: 12px; border: 1px solid #d1d5db; }
            .url { font-family: monospace; font-size: 13px; color: #4b5563; word-break: break-all; margin-top: 16px; padding: 6px 10px; background: #f3f4f6; border-radius: 6px; }
            .footer { margin-top: 24px; font-size: 14px; color: #111827; font-weight: 700; border-top: 1px dashed #d1d5db; padding-top: 16px; }
          </style>
        </head>
        <body>
          <div class="card">
            <h1>SMARTSTAY</h1>
            <div class="sub">${lang === "en" ? "Scan to view hotel amenities, GPS guide & instant check-in" : "Quét mã để xem phòng, định vị chỉ đường & thuyết minh đồ vật"}</div>
            <div class="qr-wrapper">${svgHtml}</div>
            <div class="url">${computedQrUrl}</div>
            <div class="footer">${selectedHotel?.name || "SmartStay Saigon Hotel & Villa"}</div>
          </div>
          <script>
            window.onload = function() { window.print(); }
          </script>
        </body>
      </html>
    `);
    printWindow.document.close();
  };

  return (
    <div className="control-center-wrapper">
      {/* Header thanh gọn gàng */}
      <div className="control-header">
        <div>
          <h1>{tr.systemTitle}</h1>
          <p>{tr.systemSub}</p>
        </div>
        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          <a
            className="btn btn-gray"
            href="http://localhost:8081"
            target="_blank"
            rel="noreferrer"
            style={{ textDecoration: "none" }}
            title={lang === "en" ? "Open MongoDB Web Manager" : "Mở giao diện quản lý cơ sở dữ liệu MongoDB"}
          >
            {lang === "en" ? "Database UI" : "Bảng Database"}
          </a>
          <button className="btn btn-gray" onClick={handleAdminLogin}>
            {adminUser ? `${tr.admin} ${adminUser.username}` : tr.adminLogin}
          </button>
          {onSwitchToClassic && (
            <button className="btn btn-blue" onClick={onSwitchToClassic}>
              {tr.backClassic}
            </button>
          )}
        </div>
      </div>

      {/* Tabs điều hướng đơn giản */}
      <div className="simple-tabs">
        <button
          className={`simple-tab-btn ${activeTab === "guide" ? "active" : ""}`}
          onClick={() => setActiveTab("guide")}
        >
          {tr.tab1}
        </button>
        <button
          className={`simple-tab-btn ${activeTab === "i18n" ? "active" : ""}`}
          onClick={() => setActiveTab("i18n")}
        >
          {tr.tab2}
        </button>
        <button
          className={`simple-tab-btn ${activeTab === "audio" ? "active" : ""}`}
          onClick={() => setActiveTab("audio")}
        >
          {tr.tab3}
        </button>
        <button
          className={`simple-tab-btn ${activeTab === "map" ? "active" : ""}`}
          onClick={() => setActiveTab("map")}
        >
          {tr.tab4}
        </button>
        <button
          className={`simple-tab-btn ${activeTab === "admin" ? "active" : ""}`}
          onClick={() => setActiveTab("admin")}
        >
          {tr.tab5}
        </button>
        <button
          className={`simple-tab-btn ${activeTab === "qr" ? "active" : ""}`}
          onClick={() => setActiveTab("qr")}
        >
          {tr.tab6}
        </button>
      </div>

      {/* ======================================================== */}
      {/* TAB 1: ĐỊNH VỊ GPS & THUYẾT MINH CHỈ ĐƯỜNG / ĐỒ VẬT */}
      {/* ======================================================== */}
      {activeTab === "guide" && (
        <div>
          {/* MỤC A: ĐỊNH VỊ GPS VÀ CHỈ ĐƯỜNG ĐẾN KHÁCH SẠN */}
          <div className="simple-panel">
            <div className="simple-panel-header">
              <div>
                <h2>{tr.sec1Title}</h2>
                <span className="subtitle">{tr.sec1Sub}</span>
              </div>
              <button className="btn btn-blue" onClick={handleGetLocation}>
                {tr.getGpsBtn}
              </button>
            </div>

            <div className="notice-box">
              {tr.gpsStatusLabel} <b>{gpsStatus}</b>
            </div>

            {/* Bản đồ tương tác định vị trực quan ghim đúng vị trí của bạn */}
            <div style={{ borderRadius: "8px", overflow: "hidden", border: "1px solid #d1d5db", minHeight: "340px", background: "#f3f4f6", marginBottom: "18px" }}>
              <iframe
                key={mapKey}
                title={lang === "en" ? "Interactive map of your location" : "Bản đồ vị trí thực tế của bạn"}
                src={`https://maps.google.com/maps?q=${userLat},${userLng}&hl=${lang}&z=16&output=embed`}
                style={{ width: "100%", height: "100%", minHeight: "340px", border: 0 }}
                loading="lazy"
              />
            </div>

            {/* Chọn khách sạn đích */}
            <div className="form-row">
              <div className="form-group" style={{ flex: 2 }}>
                <label>{tr.selectHotel}</label>
                <select
                  value={selectedHotel?.id || ""}
                  onChange={(e) => {
                    const found = hotels.find((h) => h.id === e.target.value);
                    if (found) setSelectedHotel(found);
                  }}
                >
                  {hotels.map((h) => (
                    <option key={h.id} value={h.id}>
                      {h.name} - {h.address} ({Math.round(h.distance_m || 0)} {lang === "en" ? "meters" : "mét"})
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group" style={{ flex: 1 }}>
                <label>{tr.audioLang}</label>
                <select value={guideLang} onChange={(e) => setGuideLang(e.target.value)}>
                  <option value="vi">{lang === "en" ? "Vietnamese" : "Tiếng Việt"}</option>
                  <option value="en">{lang === "en" ? "English" : "Tiếng Anh"}</option>
                  <option value="zh">{lang === "en" ? "Chinese (Mandarin)" : "中文 (Tiếng Trung)"}</option>
                  <option value="ja">{lang === "en" ? "Japanese" : "日本語 (Tiếng Nhật)"}</option>
                  <option value="ko">{lang === "en" ? "Korean" : "한국어 (Tiếng Hàn)"}</option>
                  <option value="fr">{lang === "en" ? "French" : "Français (Tiếng Pháp)"}</option>
                </select>
              </div>
            </div>

            {selectedHotel && (
              <div style={{ background: "#f9fafb", border: "1px solid #e5e7eb", borderRadius: "6px", padding: "16px", marginTop: "12px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: "10px", alignItems: "center" }}>
                  <div>
                    <h3 style={{ margin: "0 0 4px", fontSize: "16px", color: "#111827" }}>{selectedHotel.name}</h3>
                    <p style={{ margin: "0 0 6px", fontSize: "13px", color: "#4b5563" }}>{selectedHotel.address}</p>
                    <div style={{ fontSize: "13px", color: "#1f2937" }}>
                      {tr.distLabel} <b>{Math.round(selectedHotel.distance_m || 0)} {lang === "en" ? "meters" : "mét"}</b>
                      {Math.round(selectedHotel.distance_m || 0) <= 30 ? (
                        <span className="tag tag-green" style={{ marginLeft: "8px" }}>
                          {tr.insideGeofence}
                        </span>
                      ) : (
                        <span className="tag tag-gray" style={{ marginLeft: "8px" }}>
                          {tr.outsideGeofence} {Math.round(selectedHotel.distance_m || 0) - 30}m
                        </span>
                      )}
                    </div>
                  </div>

                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    <a
                      className="btn btn-blue"
                      href={`https://www.google.com/maps/dir/?api=1&origin=${userLat},${userLng}&destination=${selectedHotel.latitude},${selectedHotel.longitude}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {tr.openMapBtn}
                    </a>

                    <button
                      className="btn btn-green"
                      onClick={handlePlayDirectionsAudio}
                      disabled={guideAudioLoading}
                    >
                      {guideAudioLoading ? tr.audioPreparing : tr.listenDirBtn}
                    </button>
                  </div>
                </div>

                {/* Hướng dẫn nhận phòng */}
                {selectedHotel.check_in_instructions && (
                  <div style={{ marginTop: "12px", paddingTop: "12px", borderTop: "1px solid #e5e7eb", fontSize: "13px", color: "#374151" }}>
                    <b>{tr.checkinGuideLabel}</b> {selectedHotel.check_in_instructions}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* MỤC B: THUYẾT MINH HƯỚNG DẪN SỬ DỤNG ĐỒ VẬT TRONG PHÒNG */}
          <div className="simple-panel">
            <div className="simple-panel-header">
              <div>
                <h2>{tr.sec2Title}</h2>
                <span className="subtitle">{tr.sec2Sub}</span>
              </div>
            </div>

            <p style={{ fontSize: "13px", color: "#4b5563", marginTop: "0" }}>
              {tr.sec2Intro}
            </p>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "10px", marginBottom: "16px" }}>
              {Object.entries(inRoomItems).map(([key, item]) => (
                <button
                  key={key}
                  onClick={() => setSelectedItemKey(key)}
                  style={{
                    padding: "12px 14px",
                    border: selectedItemKey === key ? "2px solid #2563eb" : "1px solid #d1d5db",
                    background: selectedItemKey === key ? "#eff6ff" : "#ffffff",
                    borderRadius: "6px",
                    textAlign: "left",
                    cursor: "pointer",
                    fontSize: "13px",
                    fontWeight: selectedItemKey === key ? "700" : "500",
                    color: selectedItemKey === key ? "#1d4ed8" : "#374151",
                  }}
                >
                  {item.title[lang] || item.title.vi}
                </button>
              ))}
            </div>

            {/* Khung hiển thị nội dung & nút phát âm thanh */}
            <div style={{ background: "#f9fafb", border: "1px solid #e5e7eb", borderRadius: "6px", padding: "18px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", flexWrap: "wrap", gap: "10px" }}>
                <span style={{ fontSize: "14px", fontWeight: "700", color: "#111827" }}>
                  {tr.contentLabel} {inRoomItems[selectedItemKey]?.title[lang] || inRoomItems[selectedItemKey]?.title.vi} ({guideLang.toUpperCase()})
                </span>

                <button
                  className="btn btn-green"
                  onClick={handlePlayInRoomAudio}
                  disabled={guideAudioLoading}
                >
                  {guideAudioLoading ? tr.creatingVoice : tr.playAudioBtn}
                </button>
              </div>

              <div style={{ background: "#ffffff", padding: "14px", borderRadius: "6px", border: "1px solid #e5e7eb", fontSize: "14px", lineHeight: "1.6", color: "#1f2937", marginBottom: "14px" }}>
                {inRoomItems[selectedItemKey]?.text[guideLang] || inRoomItems[selectedItemKey]?.text["vi"]}
              </div>

              {/* Trình phát âm thanh nếu đã tạo */}
              {guideAudioUrl && (
                <div>
                  <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "8px" }}>
                    <span className={guideAudioMeta?.cache === "HIT" ? "tag tag-green" : "tag tag-yellow"}>
                      {tr.cacheLabel} {guideAudioMeta?.cache === "HIT" ? tr.cacheHit : tr.cacheMiss}
                    </span>
                    <span style={{ fontSize: "12px", color: "#6b7280" }}>
                      {tr.voiceLabel} {guideAudioMeta?.voice || "Neural AI Voice"}
                    </span>
                  </div>
                  <audio controls src={guideAudioUrl} autoPlay style={{ width: "100%", height: "40px" }} />
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* TAB 2: ĐA NGÔN NGỮ GIAO DIỆN (ui_i18n) */}
      {/* ======================================================== */}
      {activeTab === "i18n" && (
        <div className="simple-panel">
          <div className="simple-panel-header">
            <div>
              <h2>{tr.i18nTitle.replace("{locale}", i18nLocale)}</h2>
              <span className="subtitle">{tr.i18nSub}</span>
            </div>
            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              <span className={i18nBundle?.status === "ready" ? "tag tag-green" : "tag tag-yellow"}>
                {tr.statusLabel} {i18nBundle?.status?.toUpperCase() || "PENDING"}
              </span>
              <button className="btn btn-gray" onClick={() => fetchI18n(i18nLocale, true)}>
                {tr.retryBtn}
              </button>
            </div>
          </div>

          <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginBottom: "16px" }}>
            {["vi", "en", "zh", "ja", "ko", "fr", "de", "es"].map((l) => (
              <button
                key={l}
                className={`btn ${i18nLocale === l ? "btn-blue" : "btn-gray"}`}
                onClick={() => setI18nLocale(l)}
              >
                {l.toUpperCase()}
              </button>
            ))}
          </div>

          <div className="notice-box">
            {tr.sourceHashLabel} <b>{i18nBundle?.source_hash || (lang === "en" ? "Loading..." : "Đang tải...")}</b> | {tr.fallbackLabel} {i18nBundle?.is_fallback ? tr.fallbackYes : tr.fallbackNo}
          </div>

          <div className="table-container">
            <table className="simple-table">
              <thead>
                <tr>
                  <th>{tr.colKey}</th>
                  <th>{tr.colPreserved}</th>
                </tr>
              </thead>
              <tbody>
                {i18nBundle?.messages ? (
                  Object.entries(i18nBundle.messages).map(([k, v]) => (
                    <tr key={k}>
                      <td><code>{k}</code></td>
                      <td>{v}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={2}>{tr.loadingBundle}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* TAB 3: THUYẾT MINH & GÓI OFFLINE (audio) */}
      {/* ======================================================== */}
      {activeTab === "audio" && (
        <div className="simple-panel">
          <div className="simple-panel-header">
            <div>
              <h2>{tr.audioFactoryTitle}</h2>
              <span className="subtitle">{tr.audioFactorySub}</span>
            </div>
            <button className="btn btn-gray" onClick={() => fetchVoices(true)}>
              {tr.refreshVoicesBtn}
            </button>
          </div>

          <p style={{ fontSize: "13px", color: "#4b5563" }}>
            {tr.ttlLabel} <b>{Math.floor(voiceTtl / 3600)} {tr.hours} {Math.floor((voiceTtl % 3600) / 60)} {tr.minutes}</b>
          </p>

          <div className="table-container" style={{ marginBottom: "20px" }}>
            <table className="simple-table">
              <thead>
                <tr>
                  <th>{tr.colLang}</th>
                  <th>{tr.colVoiceName}</th>
                  <th>{tr.colShortCode}</th>
                  <th>{tr.colProvider}</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { lang: "vi", voice: "vi-VN-HoaiMyNeural", short: "HoaiMyNeural" },
                  { lang: "en", voice: "en-US-JennyNeural", short: "JennyNeural" },
                  { lang: "zh", voice: "zh-CN-XiaoxiaoNeural", short: "XiaoxiaoNeural" },
                  { lang: "ja", voice: "ja-JP-NanamiNeural", short: "NanamiNeural" },
                  { lang: "ko", voice: "ko-KR-SunHiNeural", short: "SunHiNeural" },
                ].map((row) => (
                  <tr key={row.voice}>
                    <td><span className="tag tag-blue">{row.lang.toUpperCase()}</span></td>
                    <td>{row.voice}</td>
                    <td><code>{row.short}</code></td>
                    <td>edge-tts</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="simple-panel-header">
            <h2>{tr.offlinePackTitle}</h2>
            <button className="btn btn-blue" onClick={fetchManifest}>
              {tr.scanMp3Btn}
            </button>
          </div>

          {manifestData && (
            <div>
              <p style={{ fontSize: "13px" }}>
                {tr.packVersionLabel} <b>{manifestData.pack_version}</b> | {tr.totalFilesLabel} <b>{manifestData.total_files}</b> | {tr.totalSizeLabel} <b>{Math.round(manifestData.total_bytes / 1024)} KB</b>
              </p>
              {manifestData.files?.length > 0 ? (
                <div className="table-container">
                  <table className="simple-table">
                    <thead>
                      <tr>
                        <th>{tr.colFilename}</th>
                        <th>{tr.colSize}</th>
                        <th>{tr.colSha256}</th>
                        <th>{tr.colDownload}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {manifestData.files.map((f) => (
                        <tr key={f.filename}>
                          <td>{f.filename}</td>
                          <td>{Math.round(f.size_bytes / 1024)} KB</td>
                          <td><small>{f.sha256}</small></td>
                          <td>
                            <a href={`${getApiBase()}${f.audio_url}`} target="_blank" rel="noreferrer">
                              {tr.downloadBtn}
                            </a>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div style={{ fontSize: "13px", color: "#6b7280" }}>{tr.noAudioFiles}</div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ======================================================== */}
      {/* TAB 4: BẢN ĐỒ, FALLBACK & ĐỒNG BỘ */}
      {/* ======================================================== */}
      {activeTab === "map" && (
        <div className="simple-panel">
          <div className="simple-panel-header">
            <div>
              <h2>{tr.mapSyncTitle}</h2>
              <span className="subtitle">{tr.mapSyncSub}</span>
            </div>
          </div>

          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginBottom: "16px" }}>
            <button className="btn btn-blue" onClick={handleHotset}>
              {tr.hotsetBtn}
            </button>
            <button className="btn btn-green" onClick={() => {
              if (selectedHotel) {
                fetch(`${getApiBase()}/localizations/on-demand`, {
                  method: "POST",
                  headers: apiHeaders(),
                  body: JSON.stringify({ poi_id: selectedHotel.id, lang: guideLang }),
                }).then(r => r.json()).then(d => alert("On-demand result: " + JSON.stringify(d)));
              } else alert(lang === "en" ? "Please select a hotel" : "Chưa chọn khách sạn");
            }}>
              {tr.ondemandBtn}
            </button>
            <button className="btn btn-blue" onClick={handleWarmup}>
              {tr.warmupBtn}
            </button>
            <button className="btn btn-gray" onClick={handleCheckEtag}>
              {tr.checkEtagBtn}
            </button>
          </div>

          {syncNotice && <div className="success-box">{syncNotice}</div>}

          <div className="table-container">
            <table className="simple-table">
              <thead>
                <tr>
                  <th>{tr.colPropName}</th>
                  <th>{tr.colPropAddress}</th>
                  <th>{tr.colPropDist}</th>
                  <th>{tr.colPropTier}</th>
                  <th>{tr.colPropRooms}</th>
                </tr>
              </thead>
              <tbody>
                {hotels.map((h) => (
                  <tr key={h.id}>
                    <td><b>{h.name}</b></td>
                    <td>{h.address}</td>
                    <td>{Math.round(h.distance_m || 0)}m</td>
                    <td>
                      <span className="tag tag-green">
                        Tier {h.fallback_tier || 1}
                      </span>
                    </td>
                    <td>
                      {h.menu_items?.map((m) => (
                        <span key={m.id || m.name} style={{ marginRight: "6px", fontSize: "12px" }}>
                          {m.name} ({Number(m.price).toLocaleString()}đ)
                        </span>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* TAB 5: QUẢN TRỊ, CHỦ NHÀ & PHÂN QUYỀN */}
      {/* ======================================================== */}
      {activeTab === "admin" && (
        <div>
          {/* Cổng tiếng Anh & Task manager */}
          <div className="simple-panel">
            <div className="simple-panel-header">
              <h2>{tr.gateTitle}</h2>
              <button className="btn btn-gray" onClick={fetchAdminData}>
                {tr.refreshTasksBtn}
              </button>
            </div>

            <div className="table-container" style={{ marginBottom: "20px" }}>
              <table className="simple-table">
                <thead>
                  <tr>
                    <th>{tr.colTaskId}</th>
                    <th>{tr.colTaskHotel}</th>
                    <th>{tr.colTaskProgress}</th>
                    <th>{tr.colTaskStatus}</th>
                    <th>{tr.colTaskGate}</th>
                    <th>{tr.colTaskControls}</th>
                  </tr>
                </thead>
                <tbody>
                  {audioTasks.length === 0 ? (
                    <tr>
                      <td colSpan={6} style={{ textAlign: "center", color: "#6b7280" }}>
                        {tr.noAudioTasks}
                      </td>
                    </tr>
                  ) : (
                    audioTasks.map((t) => (
                      <tr key={t.id}>
                        <td><code>{t.id?.slice(0, 8)}...</code></td>
                        <td>{t.poi_id?.slice(0, 8)}...</td>
                        <td>{t.progress_pct || 0}%</td>
                        <td><span className="tag tag-blue">{t.status}</span></td>
                        <td>
                          <button className="btn btn-blue" onClick={() => handleStepEnglish(t.id)}>
                            {tr.openGateBtn}
                          </button>
                        </td>
                        <td>
                          <div style={{ display: "flex", gap: "4px" }}>
                            <button className="btn btn-gray" onClick={() => handleTaskControl(t.id, "pause")}>{tr.pauseBtn}</button>
                            <button className="btn btn-gray" onClick={() => handleTaskControl(t.id, "resume")}>{tr.resumeBtn}</button>
                            <button className="btn btn-red" onClick={() => handleTaskControl(t.id, "cancel")}>{tr.cancelBtn}</button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Duyệt hồ sơ chủ nhà & Giải mã CCCD */}
            <div className="simple-panel-header">
              <h2>{tr.ownerTitle}</h2>
            </div>

            <div className="table-container">
              <table className="simple-table">
                <thead>
                  <tr>
                    <th>{tr.colRegId}</th>
                    <th>{tr.colRegName}</th>
                    <th>{tr.colRegAddr}</th>
                    <th>{tr.colRegStatus}</th>
                    <th>{tr.colRegCccd}</th>
                  </tr>
                </thead>
                <tbody>
                  {registrations.length === 0 ? (
                    <tr>
                      <td colSpan={5} style={{ textAlign: "center", color: "#6b7280" }}>
                        {tr.noRegistrations}
                      </td>
                    </tr>
                  ) : (
                    registrations.map((r) => (
                      <tr key={r.id}>
                        <td><code>{r.id?.slice(0, 8)}...</code></td>
                        <td>{r.property_name}</td>
                        <td>{r.property_address}</td>
                        <td><span className="tag tag-green">{r.status}</span></td>
                        <td>
                          {piiValue[r.id] ? (
                            <b>{piiValue[r.id]}</b>
                          ) : (
                            <button className="btn btn-gray" onClick={() => handleDecryptCccd(r.id)}>
                              {tr.decryptBtn}
                            </button>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Ma trận 32 quyền */}
            {rbacList && (
              <div style={{ marginTop: "20px" }}>
                <div className="simple-panel-header">
                  <h2>{tr.rbacTitle}</h2>
                </div>
                <div className="table-container">
                  <table className="simple-table">
                    <thead>
                      <tr>
                        <th>{tr.colDomain}</th>
                        <th>{tr.colPerms}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(rbacList.domains || {}).map(([d, perms]) => (
                        <tr key={d}>
                          <td><b>{d.toUpperCase()}</b> ({perms.length})</td>
                          <td>
                            {perms.map((p) => (
                              <code key={p} style={{ marginRight: "6px" }}>{p}</code>
                            ))}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* TAB 6: MÃ QR TRUY CẬP & GIÁM SÁT TÌNH HÌNH KHÁCH HÀNG */}
      {/* ======================================================== */}
      {activeTab === "qr" && (
        <div>
          {/* TIÊU ĐỀ PHÂN KHU & THỐNG KÊ */}
          <div className="simple-panel">
            <div className="simple-panel-header">
              <div>
                <h2>{tr.qrDashboardTitle}</h2>
                <span className="subtitle">{tr.qrDashboardSub}</span>
              </div>
              <button className="btn btn-blue" onClick={fetchQrStats}>
                {lang === "en" ? "Refresh Dashboard" : "Cập nhật dữ liệu"}
              </button>
            </div>

            {/* 4 THẺ THỐNG KÊ TỔNG QUAN */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px", marginBottom: "24px" }}>
              <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "8px", padding: "16px 20px" }}>
                <div style={{ fontSize: "13px", color: "#64748b", fontWeight: "600", marginBottom: "6px" }}>{tr.qrCardTotal}</div>
                <div style={{ fontSize: "28px", fontWeight: "800", color: "#1e3a8a" }}>{qrStats.total_scans ?? 0}</div>
              </div>

              <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "8px", padding: "16px 20px" }}>
                <div style={{ fontSize: "13px", color: "#64748b", fontWeight: "600", marginBottom: "6px" }}>{tr.qrCardToday}</div>
                <div style={{ fontSize: "28px", fontWeight: "800", color: "#059669" }}>{qrStats.today_scans ?? 0}</div>
              </div>

              <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "8px", padding: "16px 20px" }}>
                <div style={{ fontSize: "13px", color: "#64748b", fontWeight: "600", marginBottom: "6px" }}>{tr.qrCardActive}</div>
                <div style={{ fontSize: "28px", fontWeight: "800", color: "#d97706" }}>{qrStats.active_visitors ?? 0}</div>
              </div>

              <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "8px", padding: "16px 20px" }}>
                <div style={{ fontSize: "13px", color: "#64748b", fontWeight: "600", marginBottom: "6px" }}>{tr.qrCardDevice}</div>
                <div style={{ fontSize: "20px", fontWeight: "700", color: "#334155", marginTop: "6px" }}>{qrStats.top_device || "Mobile"}</div>
              </div>
            </div>

            {/* BỘ TẠO MÃ QR ĐỘNG & TÙY CHỌN MẠNG */}
            <div style={{ borderTop: "1px solid #e5e7eb", paddingTop: "20px", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "24px", alignItems: "start" }}>
              {/* Cột trái: Cài đặt Host & Đường dẫn */}
              <div>
                <h3 style={{ fontSize: "16px", fontWeight: "700", margin: "0 0 16px 0", color: "#111827" }}>{tr.qrGenTitle}</h3>
                
                <div className="form-group" style={{ marginBottom: "14px" }}>
                  <label>{tr.qrNetworkHost}</label>
                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginBottom: "8px" }}>
                    <button
                      className={`btn ${qrHost === "http://172.20.10.3:4173" && !customHost ? "btn-blue" : "btn-gray"}`}
                      onClick={() => { setQrHost("http://172.20.10.3:4173"); setCustomHost(""); }}
                    >
                      Wi-Fi LAN (172.20.10.3)
                    </button>
                    <button
                      className={`btn ${qrHost === "http://localhost:4173" && !customHost ? "btn-blue" : "btn-gray"}`}
                      onClick={() => { setQrHost("http://localhost:4173"); setCustomHost(""); }}
                    >
                      Localhost (127.0.0.1)
                    </button>
                  </div>
                  <input
                    type="text"
                    value={customHost}
                    onChange={(e) => setCustomHost(e.target.value)}
                    placeholder={lang === "en" ? "Or enter custom domain (e.g. https://myhotel.com)" : "Hoặc nhập tên miền tùy chỉnh (vd: https://khachsan.vn)"}
                  />
                </div>

                <div className="form-group" style={{ marginBottom: "16px" }}>
                  <label>{tr.qrTargetDest}</label>
                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    <button
                      className={`btn ${qrTarget === "/#/?ref=qr" ? "btn-blue" : "btn-gray"}`}
                      onClick={() => setQrTarget("/#/?ref=qr")}
                    >
                      {lang === "en" ? "Home (?ref=qr)" : "Trang chủ (?ref=qr)"}
                    </button>
                    <button
                      className={`btn ${qrTarget === "/#/control?tab=guide" ? "btn-blue" : "btn-gray"}`}
                      onClick={() => setQrTarget("/#/control?tab=guide")}
                    >
                      {lang === "en" ? "GPS & Voice Guide" : "Chỉ đường GPS & Thuyết minh"}
                    </button>
                    <button
                      className={`btn ${qrTarget === "/#/rooms" ? "btn-blue" : "btn-gray"}`}
                      onClick={() => setQrTarget("/#/rooms")}
                    >
                      {lang === "en" ? "Hotel Rooms" : "Danh sách phòng"}
                    </button>
                  </div>
                </div>

                <div className="notice-box" style={{ wordBreak: "break-all" }}>
                  <b>URL:</b> <a href={computedQrUrl} target="_blank" rel="noreferrer" style={{ color: "#1d4ed8" }}>{computedQrUrl}</a>
                </div>

                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginTop: "12px" }}>
                  <button className="btn btn-blue" onClick={handleSimulateScan}>
                    {tr.qrSimulateBtn}
                  </button>
                  <button className="btn btn-green" onClick={handlePrintQr}>
                    {tr.qrPrintBtn}
                  </button>
                  <button className="btn btn-gray" onClick={handleDownloadQrSvg}>
                    {tr.qrDownloadBtn}
                  </button>
                </div>
              </div>

              {/* Cột phải: Khung hiển thị Mã QR */}
              <div style={{ background: "#f9fafb", border: "1px solid #e5e7eb", borderRadius: "8px", padding: "24px", textAlign: "center" }}>
                <div style={{ background: "#ffffff", padding: "16px", borderRadius: "8px", display: "inline-block", boxShadow: "0 2px 8px rgba(0,0,0,0.06)", border: "1px solid #e2e8f0" }}>
                  <QRCodeSVG
                    id="smartstay-qr-svg"
                    value={computedQrUrl}
                    size={200}
                    level="H"
                    includeMargin={true}
                  />
                </div>
                <div style={{ fontSize: "13px", color: "#64748b", marginTop: "12px" }}>
                  {lang === "en"
                    ? "Guests scanning this QR code with their mobile camera will be redirected to the target page and logged automatically."
                    : "Khách dùng camera điện thoại quét mã này sẽ mở trực tiếp trang web và ghi nhận vào bảng nhật ký bên dưới."}
                </div>
              </div>
            </div>
          </div>

          {/* BẢNG NHẬT KÝ QUÉT MÃ THỜI GIAN THỰC */}
          <div className="simple-panel">
            <div className="simple-panel-header">
              <div>
                <h2>{tr.qrLogTitle}</h2>
                <span className="subtitle">
                  {lang === "en" ? "Real-time automatic sync every 3 seconds" : "Tự động đồng bộ mỗi 3 giây"}
                </span>
              </div>
              <button className="btn btn-gray" onClick={handleClearQrLogs}>
                {tr.qrClearBtn}
              </button>
            </div>

            <div className="table-container">
              <table className="simple-table">
                <thead>
                  <tr>
                    <th>{tr.qrColTime}</th>
                    <th>{tr.qrColStay}</th>
                    <th>{tr.qrColDevice}</th>
                    <th>{tr.qrColIp}</th>
                    <th>{tr.qrColAction}</th>
                    <th>{tr.qrColStatus}</th>
                  </tr>
                </thead>
                <tbody>
                  {(!qrStats.recent_scans || qrStats.recent_scans.length === 0) ? (
                    <tr>
                      <td colSpan={6} style={{ textAlign: "center", color: "#6b7280", padding: "20px" }}>
                        {lang === "en" ? "No QR scan activity recorded yet." : "Chưa có lượt quét QR nào được ghi nhận."}
                      </td>
                    </tr>
                  ) : (
                    qrStats.recent_scans.map((s, idx) => (
                      <tr key={idx}>
                        <td><code>{s.scanned_at || "Vừa xong"}</code></td>
                        <td><b>{s.stay_name || "SmartStay Saigon Riverside"}</b></td>
                        <td>{s.device || "Mobile"}</td>
                        <td><code>{s.ip || "127.0.0.1"}</code></td>
                        <td>{s.action || "Quét mã QR truy cập hệ thống"}</td>
                        <td>
                          <span className="tag tag-green">
                            {lang === "en" ? "Connected" : "Đã kết nối"}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
