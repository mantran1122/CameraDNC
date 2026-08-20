'use strict';

// Browser mock — chỉ load khi chạy trên web (không phải Qt app)
// Giả lập QWebChannel + backend để UI render đầy đủ mà không cần Python

if (typeof qt === 'undefined') {

    // Mock QWebChannel
    window.QWebChannel = function(transport, cb) {
        var mockSignal = { connect: function() {} };
        window.backend = {
            demo_started: mockSignal,
            demo_stopped: mockSignal,
            demo_error:   mockSignal,
            app_status:   mockSignal,
            launch:      function(p) { console.log('[mock] launch:', p); },
            open_folder: function()  { console.log('[mock] open_folder'); },
            quit_app:    function()  { console.log('[mock] quit_app');    },
        };
        cb({ objects: { backend: window.backend } });
    };

    window.qt = { webChannelTransport: null };

    // Mock data — đồng bộ với DEMOS/CATEGORIES trong launcher.py
    var MOCK_APP_DATA = {
        demos: [
            { label: "Tìm kiếm thiết bị",      module_path: "", module_name: "SearchDeviceDemo",      class_name: "MyMainWindow",  icon_key: "fa-search",      description: "Quét và phát hiện thiết bị Dahua trong mạng nội bộ.",              category: "Thiết bị",   accent: "#3B82F6", keywords: ["tìm kiếm","thiết bị","mạng","scan","device","network"] },
            { label: "Xem camera trực tiếp",    module_path: "", module_name: "RealPlayDemo",          class_name: "MyMainWindow",  icon_key: "fa-video",       description: "Mở luồng live view từ thiết bị hoặc camera.",                       category: "Camera",     accent: "#06B6D4", keywords: ["camera","live","view","stream","trực tiếp","realplay"] },
            { label: "Chụp ảnh",                module_path: "", module_name: "CaptureDemo",           class_name: "CaptureWnd",    icon_key: "fa-camera",      description: "Chụp snapshot từ luồng camera hiện tại.",                           category: "Camera",     accent: "#06B6D4", keywords: ["chụp","ảnh","snapshot","capture","picture"] },
            { label: "Nghe cảnh báo",            module_path: "", module_name: "AlarmListenDemo",       class_name: "StartListenWnd",icon_key: "fa-bell",        description: "Lắng nghe và kiểm thử sự kiện cảnh báo từ thiết bị.",              category: "Cảnh báo",  accent: "#F59E0B", keywords: ["cảnh báo","alarm","sự kiện","event","listen"] },
            { label: "Xem lại video",            module_path: "", module_name: "PlayBackDemo",          class_name: "MyMainWindow",  icon_key: "fa-play-circle", description: "Truy xuất và phát lại video đã được ghi trên thiết bị.",           category: "Playback",   accent: "#3B82F6", keywords: ["playback","xem lại","video","record","replay"] },
            { label: "Điều khiển thiết bị",     module_path: "", module_name: "DeviceControlDemo",     class_name: "MyMainWindow",  icon_key: "fa-sliders-h",   description: "Thao tác cấu hình và điều khiển thiết bị từ xa.",                  category: "Thiết bị",   accent: "#64748B", keywords: ["điều khiển","control","config","device","thiết bị"] },
            { label: "Nhận diện khuôn mặt",     module_path: "", module_name: "FaceRecognitionDemo",   class_name: "MyMainWindow",  icon_key: "fa-user-circle", description: "Demo tính năng AI nhận diện và phân tích khuôn mặt.",              category: "AI",         accent: "#10B981", keywords: ["face","khuôn mặt","ai","nhận diện","recognition"] },
            { label: "Giao thông thông minh",   module_path: "", module_name: "TrafficDemo",            class_name: "TrafficWnd",    icon_key: "fa-road",        description: "Kiểm thử demo phân tích giao thông thông minh.",                   category: "Giao thông", accent: "#F43F5E", keywords: ["giao thông","traffic","intelligent","xe","biển số"] },
        ],
        categories: ["Tất cả", "Thiết bị", "Camera", "Cảnh báo", "Playback", "AI", "Giao thông"],
    };

    var MOCK_PLATFORM = {
        python:   "3.11.0 (mock)",
        platform: "Windows 11",
        qt:       "5.15.x (mock)",
        sdk:      "v3.052",
    };

    // Gọi initApp sau khi DOM + app.js đã load xong
    window.addEventListener('load', function() {
        if (window.initApp) {
            window.initApp(MOCK_APP_DATA, MOCK_PLATFORM);
        }
    });
}
