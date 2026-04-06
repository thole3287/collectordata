// Alpine.js data và functions
function app() {
    return {
        // State
        sidebarOpen: true,
        activeTab: 'visualization',
        urlInput: '',
        urlDownloadPlatform: 'youtube', // New
        bypassKeywordCheck: false, // New state for bypass checkbox
        keywordDownloadPlatform: 'youtube', // New
        selectedKeywordId: '',
        activeKeywords: [],
        selectedKeyword: null,
        numVideos: 1,
        downloading: false,
        videos: [],

        // Video Inference State
        inferenceUploadFile: null,
        inferenceLoading: false,
        inferenceStatus: null, // 'pending', 'processing', 'completed', 'failed'
        inferenceResultUrl: null,
        inferenceError: null,
        inferencePollingInterval: null,
        inferenceEnableCounting: false,
        inferenceLineY: null,
        inferenceCounts: {},
        inferenceProgress: 0,
        // Camera & Metadata
        inferenceCameraList: [],
        inferenceSelectedCameraId: '',
        analyticsFilterCamera: '',
        analyticsFilterStart: '',
        analyticsFilterEnd: '',
        analyticsFilterCamDate: '',
        inferenceSelectedCamera: null,
        inferenceRecordDate: '',
        // Live Preview & FPS
        inferencePreviewUrl: null,
        inferencePreviewTimestamp: 0,
        inferenceProcessingFps: 0,
        inferenceGallerySnapshots: [],
        inferenceFrameCount: 0,
        inferenceVideoFps: 0,
        inferenceTotalFrames: 0,
        // Traffic Stats History
        inferenceHistory: [],
        inferenceHistoryTotal: 0,
        inferenceHistoryPage: 1,
        inferenceHistoryTotalPages: 1,
        inferenceHistoryLoading: false,
        inferenceHistoryDateFilter: '',
        // Gallery lightbox
        inferenceSnapshotModal: false,
        inferenceSnapshotModalUrl: '',
        // Preview refresh interval (separate from status polling)
        inferencePreviewRefreshInterval: null,
        // Congestion threshold (user-configurable)
        inferenceCongestionThreshold: 200,
        inferenceCachedAnalytics: null,  // cache API response to redraw without re-fetching

        async downloadByUrl() {
            if (!this.urlInput.trim()) return;

            this.downloading = true;
            try {
                const urls = this.urlInput.split('\n').filter(url => url.trim());
                const response = await fetch('/api/download/url', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        urls,
                        platform: this.urlDownloadPlatform,
                        bypass_keyword_check: this.bypassKeywordCheck
                    })
                });
                const data = await response.json();

                if (response.ok) {
                    this.showNotify(data.message, 'success');
                    this.urlInput = '';
                    this.loadVideos(); // Reload list
                } else {
                    this.showNotify(data.error || 'Có lỗi xảy ra', 'error');
                }
            } catch (error) {
                this.showNotify('Lỗi kết nối: ' + error.message, 'error');
            } finally {
                this.downloading = false;
            }
        },

        async downloadByKeyword() {
            if (!this.selectedKeywordId) return;

            this.downloading = true;
            try {
                const response = await fetch('/api/download/keyword', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        keyword: this.selectedKeyword.keyword,
                        num_videos: this.numVideos,
                        platform: this.keywordDownloadPlatform
                    })
                });
                const data = await response.json();

                if (response.ok) {
                    this.showNotify(data.message, 'success');
                    this.loadVideos(); // Reload list
                } else {
                    this.showNotify(data.error || 'Có lỗi xảy ra', 'error');
                }
            } catch (error) {
                this.showNotify('Lỗi kết nối: ' + error.message, 'error');
            } finally {
                this.downloading = false;
            }
        },
        totalVideos: 0,
        currentPage: 1,
        perPage: 10,
        totalPages: 0,
        searchQuery: '',
        vizData: {},
        charts: {},
        keywords: [],
        videosTableBody: '',
        keywordsTableBody: '',
        vizKeywordsTableBody: '',
        // Camera Collector state
        cameraSchedulerRunning: false,
        cameraLastCollection: null,
        cameraStats: { total_attempts: 0, successful: 0, failed: 0 },
        activeCameras: [],
        allCameras: [],
        filteredCameraList: [],
        cameraSearchQuery: '',
        selectedCameraId: '',
        selectedCameraName: '',
        addingCamera: false,
        cameraLoading: false,
        cameraRecentImages: [],
        showCameraImageModal: false,
        selectedCameraImage: null,
        latestCameraImage: null,
        cameraAutoRefreshInterval: null,

        // Edit keyword state
        editingKeyword: null,
        showEditKeywordModal: false,
        newKeyword: {
            keyword: '',
            num_videos: 1,
            description: ''
        },
        addingKeyword: false,
        showNotification: false,
        notificationMessage: '',
        notificationMessage: '',
        notificationType: 'success',

        // Gallery State
        galleryMode: 'grouped', // 'grouped' | 'flat'
        galleryGroups: [],
        galleryTotalGroups: 0,
        galleryGroupFrames: {}, // { video_id: [frames] }
        galleryExpandedGroups: [], // [video_id, ...]

        galleryFrames: [],
        galleryFilterLabelStatus: 'all', // all | labeled | unlabeled
        galleryPage: 1,
        galleryPerPage: 10, // Groups per page
        galleryTotalPages: 0,
        galleryTotalFrames: 0,
        galleryLoading: false,
        showGalleryModal: false,
        selectedGalleryFrame: null,
        isVisualized: false, 
        isEditing: false,
        annotationClass: '2', 
        annotationBoxes: [], 
        annotationSelectedIdx: -1,
        annotationIsDrawing: false,
        annotationStartX: 0,
        annotationStartY: 0,
        annotationCurrentX: 0,
        annotationCurrentY: 0,
        annotationSaving: false,
        annotationDirty: false,
        annotationOriginalTxt: '',

        toggleVisualized() {
            if (!this.selectedGalleryFrame) return;
            this.isVisualized = !this.isVisualized;

            // Stop editing if it was on
            this.isEditing = false;

            if (this.isVisualized) {
                this.loadAnnotationsFromTxt();
            } else {
                // Clear canvas if no longer visualizing
                const canvas = document.getElementById('annotationCanvas');
                if (canvas) {
                    const ctx = canvas.getContext('2d');
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                }
            }
        },

        startEditing() {
            if (!this.selectedGalleryFrame) return;
            this.isEditing = true;
            this.annotationSelectedIdx = -1;
            this.loadAnnotationsFromTxt();
        },

        openGalleryModal(frame) {
            this.selectedGalleryFrame = frame;
            this.isVisualized = false;
            this.isEditing = false;
            this.annotationBoxes = [];
            this.showGalleryModal = true;
            // Fetch content if needed
            this.fetchRawLabels();
        },

        stopEditing() {
            this.isEditing = false;
            this.annotationSelectedIdx = -1;
            // If isVisualized is still true, we keep the boxes but in read-only mode
            if (!this.isVisualized) {
                this.annotationBoxes = [];
                const canvas = document.getElementById('annotationCanvas');
                if (canvas) {
                    const ctx = canvas.getContext('2d');
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                }
            }
        },

        async loadAnnotationsFromTxt() {
            const refs = this.selectedGalleryFrame.storage_refs || {};
            if (!refs.label_key) {
                this.annotationBoxes = [];
                this.annotationOriginalTxt = '';
                setTimeout(() => this.initAnnotationCanvas(), 100);
                return;
            }

            try {
                const url = `/api/dataset/label-content?bucket=${refs.bucket || 'dataset'}&key=${refs.label_key}`;
                const response = await fetch(url);
                const data = await response.json();
                if (response.ok) {
                    this.annotationOriginalTxt = data.content;
                    this.parseYoloTxt(data.content);
                }
            } catch (e) { console.error(e); }
            
            setTimeout(() => this.initAnnotationCanvas(), 100);
        },

        parseYoloTxt(content) {
            const boxes = [];
            content.trim().split('\n').forEach(line => {
                const parts = line.trim().split(/\s+/);
                if (parts.length >= 5) {
                    boxes.push({
                        cls: parseInt(parts[0]),
                        cx: parseFloat(parts[1]),
                        cy: parseFloat(parts[2]),
                        w: parseFloat(parts[3]),
                        h: parseFloat(parts[4]),
                        conf: parts[5] ? parseFloat(parts[5]) : 1.0
                    });
                }
            });
            this.annotationBoxes = boxes;
        },

        initAnnotationCanvas() {
            const canvas = document.getElementById('annotationCanvas');
            const img = document.getElementById('galleryModalBaseImg');
            if (!canvas || !img) return;

            if (!img.complete) {
                img.onload = () => this.initAnnotationCanvas();
                return;
            }

            // Sync canvas size with image display size
            canvas.width = img.clientWidth;
            canvas.height = img.clientHeight;
            // Position canvas exactly over image
            canvas.style.left = img.offsetLeft + 'px';
            canvas.style.top = img.offsetTop + 'px';

            this.drawAnnotations();
        },

        drawAnnotations() {
            const canvas = document.getElementById('annotationCanvas');
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            const colors = { 0: '#ff4d4d', 1: '#4dff4d', 2: '#4da6ff', 3: '#ffff4d', 5: '#ff4dff', 7: '#ffa64d' };
            const classNames = { 0: 'person', 1: 'bicycle', 2: 'car', 3: 'motorcycle', 5: 'bus', 7: 'truck' };

            this.annotationBoxes.forEach((box, index) => {
                const isSelected = index === this.annotationSelectedIdx;
                const w = box.w * canvas.width;
                const h = box.h * canvas.height;
                const x = (box.cx * canvas.width) - (w / 2);
                const y = (box.cy * canvas.height) - (h / 2);

                ctx.strokeStyle = colors[box.cls] || '#ffffff';
                ctx.lineWidth = isSelected ? 3 : 1.5;
                ctx.strokeRect(x, y, w, h);

                // Small Label
                ctx.font = '10px sans-serif';
                const label = classNames[box.cls] || box.cls;
                const tw = ctx.measureText(label).width;
                ctx.fillStyle = colors[box.cls] || '#ffffff';
                ctx.fillRect(x, y - 12, tw + 4, 12);
                ctx.fillStyle = '#000';
                ctx.fillText(label, x + 2, y - 3);

                if (isSelected) {
                    ctx.setLineDash([4, 4]);
                    ctx.strokeStyle = '#fff';
                    ctx.strokeRect(x-2, y-2, w+4, h+4);
                    ctx.setLineDash([]);
                }
            });

            if (this.annotationIsDrawing) {
                ctx.strokeStyle = '#fff';
                ctx.setLineDash([4, 4]);
                const x = Math.min(this.annotationStartX, this.annotationCurrentX);
                const y = Math.min(this.annotationStartY, this.annotationCurrentY);
                const w = Math.abs(this.annotationStartX - this.annotationCurrentX);
                const h = Math.abs(this.annotationStartY - this.annotationCurrentY);
                ctx.strokeRect(x, y, w, h);
                ctx.setLineDash([]);
            }
        },

        annotationMouseDown(e) {
            const canvas = document.getElementById('annotationCanvas');
            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            let found = -1;
            for (let i = this.annotationBoxes.length - 1; i >= 0; i--) {
                const b = this.annotationBoxes[i];
                const bw = b.w * canvas.width;
                const bh = b.h * canvas.height;
                const bx = (b.cx * canvas.width) - (bw / 2);
                const by = (b.cy * canvas.height) - (bh / 2);
                if (x >= bx && x <= bx + bw && y >= by && y <= by + bh) {
                    found = i; break;
                }
            }

            if (found !== -1) {
                this.annotationSelectedIdx = found;
                this.annotationIsDrawing = false;
            } else {
                this.annotationSelectedIdx = -1;
                this.annotationIsDrawing = true;
                this.annotationStartX = x; this.annotationStartY = y;
                this.annotationCurrentX = x; this.annotationCurrentY = y;
            }
            this.drawAnnotations();
        },

        annotationMouseMove(e) {
            if (!this.annotationIsDrawing) return;
            const canvas = document.getElementById('annotationCanvas');
            const rect = canvas.getBoundingClientRect();
            this.annotationCurrentX = e.clientX - rect.left;
            this.annotationCurrentY = e.clientY - rect.top;
            this.drawAnnotations();
        },

        annotationMouseUp(e) {
            if (!this.annotationIsDrawing) return;
            const canvas = document.getElementById('annotationCanvas');
            const wPx = Math.abs(this.annotationStartX - this.annotationCurrentX);
            const hPx = Math.abs(this.annotationStartY - this.annotationCurrentY);

            if (wPx > 5 && hPx > 5) {
                const cxPx = (this.annotationStartX + this.annotationCurrentX) / 2;
                const cyPx = (this.annotationStartY + this.annotationCurrentY) / 2;
                this.annotationBoxes.push({
                    cls: parseInt(this.annotationClass),
                    cx: cxPx / canvas.width, cy: cyPx / canvas.height,
                    w: wPx / canvas.width, h: hPx / canvas.height,
                    conf: 1.0
                });
                this.annotationDirty = true;
            }
            this.annotationIsDrawing = false;
            this.drawAnnotations();
        },

        deleteSelectedAnnotation() {
            if (this.annotationSelectedIdx === -1) return;
            this.annotationBoxes.splice(this.annotationSelectedIdx, 1);
            this.annotationSelectedIdx = -1;
            this.annotationDirty = true;
            this.drawAnnotations();
        },

        async saveAnnotations() {
            this.annotationSaving = true;
            const refs = this.selectedGalleryFrame.storage_refs || {};
            const content = this.annotationBoxes
                .map(b => `${b.cls} ${b.cx.toFixed(6)} ${b.cy.toFixed(6)} ${b.w.toFixed(6)} ${b.h.toFixed(6)} ${b.conf.toFixed(6)}`)
                .join('\n');

            try {
                const res = await fetch('/api/dataset/label-content', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        bucket: refs.bucket || 'dataset', key: refs.label_key, content,
                        frame_id: this.selectedGalleryFrame.id, platform: this.selectedGalleryFrame.platform
                    })
                });

                if (res.ok) {
                    const data = await res.json();
                    this.selectedGalleryFrame.label_summary = data.label_summary;
                    this.annotationDirty = false;
                    this.showNotify("Đã lưu nhãn thành công", "success");
                    
                    if (refs.visualized_key) {
                        const regRes = await fetch('/api/dataset/regenerate-visualized', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                bucket: refs.bucket || 'dataset', image_key: refs.key,
                                label_key: refs.label_key, vis_key: refs.visualized_key
                            })
                        });
                        
                        if (regRes.ok) {
                            // Chờ 1 giây để MinIO hoàn tất đồng bộ file trước khi tải lại
                            setTimeout(() => {
                                const timestamp = new Date().getTime();
                                if (this.selectedGalleryFrame.visualized_url) {
                                    let baseUrl = this.selectedGalleryFrame.visualized_url.split('?')[0];
                                    this.selectedGalleryFrame.visualized_url = `${baseUrl}?t=${timestamp}`;
                                    
                                    // Nếu đang bật chế độ Show AI thì cập nhật trực tiếp image_url
                                    if (this.isVisualized) {
                                        this.selectedGalleryFrame.image_url = this.selectedGalleryFrame.visualized_url;
                                    }
                                }
                                this.showNotify("Ảnh AI đã được cập nhật bản mới nhất", "success");
                            }, 1000);
                        }
                    }
                }
            } catch (e) { 
                console.error(e);
                this.showNotify("Lỗi khi lưu: " + e.message, "error"); 
            } finally { 
                this.annotationSaving = false; 
            }
        },

        async fetchRawLabels() {
            if (!this.selectedGalleryFrame || this.selectedGalleryFrame.raw_labels) return;

            const refs = this.selectedGalleryFrame.storage_refs || {};
            if (!refs.label_key) {
                this.selectedGalleryFrame.raw_labels = "No label file reference found.";
                return;
            }

            this.selectedGalleryFrame.raw_labels = "Loading...";

            try {
                const url = `/api/dataset/label-content?bucket=${refs.bucket || 'dataset'}&key=${refs.label_key}`;
                const response = await fetch(url);
                const data = await response.json();

                if (response.ok) {
                    this.selectedGalleryFrame.raw_labels = data.content;
                } else {
                    this.selectedGalleryFrame.raw_labels = "Error loading labels: " + (data.error || "Unknown error");
                }
            } catch (e) {
                this.selectedGalleryFrame.raw_labels = "Network error: " + e.message;
            }
        },

        // Gallery Dashboard State
        galleryStats: {},
        galleryFilterPlatform: 'all',
        gallerySearchQuery: '',
        galleryCharts: {},
        // Settings State
        activeProfile: 'day', // 'day', 'night', 'rain'
        settings: {
            enabled_camera: false,
            enabled_video: false,
            enabled_augmentation: true,
            rotation_angle: 15,
            profiles: {
                day: { mean_intensity: "", clahe_clip_limit: 1.0, gamma: 1.0, denoise_strength: 0, hue_shift: 0, saturation_scale: 1.0, contrast_scale: 1.0, resize_640: false },
                night: { mean_intensity: "", clahe_clip_limit: 1.0, gamma: 1.2, denoise_strength: 3.0, hue_shift: 0, saturation_scale: 1.0, contrast_scale: 1.1, resize_640: false },
                rain: { mean_intensity: "", clahe_clip_limit: 2.0, gamma: 1.0, denoise_strength: 0, hue_shift: 0, saturation_scale: 1.1, contrast_scale: 1.2, resize_640: false }
            }
        },
        settingsSaving: false,
        settingsPreviewFile: null,
        previewLoading: false,
        originalPreviewImage: null,
        processedPreviewImage: null,
        previewMetrics: {},
        previewDebounceTimer: null,
        previewDetectedProfile: null, // New state for info

        showOutlierModal: false,
        selectedOutlier: null,

        formatFileSize(bytes) {
            if (!bytes) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        },

        async loadGalleryStats() {
            try {
                const response = await fetch('/api/dataset/stats');
                if (response.ok) {
                    this.galleryStats = await response.json();
                    this.showNotify('Stats Loaded: ' + (this.galleryStats.timeline?.length || 0) + ' items', 'success');
                    // Delay to ensure DOM is visible/layout computed
                    setTimeout(() => {
                        this.drawGalleryInterface();
                    }, 100);
                }
            } catch (error) {
                console.error("Failed to load stats", error);
            }
        },

        downloadChartData(type) {
            let data = [];
            let filename = '';
            let headers = [];

            if (type === 'trend') {
                filename = 'trend_data.csv';
                headers = ['Date', 'Count'];
                if (this.galleryStats.timeline) {
                    data = this.galleryStats.timeline.map(x => ({
                        Date: x.date,
                        Count: x.count
                    }));
                }
            } else if (type === 'platform') {
                filename = 'platform_data.csv';
                headers = ['Platform', 'Count'];
                if (this.galleryStats.platforms) {
                    data = Object.entries(this.galleryStats.platforms).map(([k, v]) => ({
                        Platform: k,
                        Count: v
                    }));
                }
            } else if (type === 'object') {
                filename = 'object_data.csv';
                headers = ['Object', 'Count'];
                if (this.galleryStats.objects) {
                    data = Object.entries(this.galleryStats.objects).map(([k, v]) => ({
                        Object: k,
                        Count: v
                    }));
                }
            } else if (type === 'model') {
                filename = 'model_data.csv';
                headers = ['Model', 'Count'];
                if (this.galleryStats.models) {
                    data = Object.entries(this.galleryStats.models).map(([k, v]) => ({
                        Model: k,
                        Count: v
                    }));
                }
            }

            if (!data.length) {
                this.showNotify('Không có dữ liệu để tải xuống', 'error');
                return;
            }

            this.exportToCSV(data, headers, filename);
        },

        downloadVizChartData(type) {
            let data = [];
            let filename = '';
            let headers = [];

            if (type === 'platform') {
                filename = 'platform_distribution.csv';
                headers = ['Platform', 'Count'];
                if (this.vizData.by_platform) {
                    data = this.vizData.by_platform.map(x => ({
                        Platform: x.platform,
                        Count: x.count
                    }));
                }
            } else if (type === 'method') {
                filename = 'download_method.csv';
                headers = ['Method', 'Count'];
                if (this.vizData.by_method) {
                    data = this.vizData.by_method.map(x => ({
                        Method: x.method,
                        Count: x.count
                    }));
                }
            } else if (type === 'weather') {
                filename = 'weather_distribution.csv';
                headers = ['Weather', 'Count'];
                if (this.vizData.by_weather) {
                    data = this.vizData.by_weather.map(x => ({
                        Weather: x.weather,
                        Count: x.count
                    }));
                }
            } else if (type === 'resolution') {
                filename = 'resolution_distribution.csv';
                headers = ['Resolution', 'Count'];
                if (this.vizData.by_resolution) {
                    data = this.vizData.by_resolution.map(x => ({
                        Resolution: x.resolution,
                        Count: x.count
                    }));
                }
            } else if (type === 'duration') {
                filename = 'duration_distribution.csv';
                headers = ['Duration Range', 'Count'];
                if (this.vizData.by_duration) {
                    data = this.vizData.by_duration.map(x => ({
                        'Duration Range': x.range,
                        Count: x.count
                    }));
                }
            } else if (type === 'time') {
                filename = 'video_over_time.csv';
                headers = ['Date', 'Count'];
                if (this.vizData.by_date) {
                    data = this.vizData.by_date.map(x => ({
                        Date: x.date,
                        Count: x.count
                    }));
                }
            } else if (type === 'keyword') {
                filename = 'keyword_wordcloud.csv';
                headers = ['Keyword', 'Count', 'Platforms', 'Frame Count', 'Labeled Count'];
                if (this.vizData.by_keyword) {
                    data = this.vizData.by_keyword.map(x => ({
                        Keyword: x.keyword,
                        Count: x.count,
                        Platforms: (x.platforms || []).join('; '),
                        'Frame Count': x.frame_count || 0,
                        'Labeled Count': x.labeled_count || 0
                    }));
                }
            }

            if (!data.length) {
                this.showNotify('Không có dữ liệu để tải xuống', 'error');
                return;
            }

            this.exportToCSV(data, headers, filename);
        },
        exportToCSV(data, headers, filename) {
            const csvContent = [
                headers.join(','),
                ...data.map(row => headers.map(header => row[header]).join(','))
            ].join('\n');

            const blob = new Blob([csvContent], {
                type: 'text/csv;charset=utf-8;'
            });
            const link = document.createElement('a');
            if (link.download !== undefined) {
                const url = URL.createObjectURL(blob);
                link.setAttribute('href', url);
                link.setAttribute('download', filename);
                link.style.visibility = 'hidden';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }
        },

        drawGalleryInterface() {
            // Debug Notification
            this.showNotify('Executing Draw Interface...', 'info');
            console.log("Draw Interface Started");
            try {
                // 1. Trend Chart
                const trendEl = document.getElementById('galleryTrendChart');
                if (!trendEl) this.showNotify('Trend Canvas Not Found!', 'error');

                if (trendEl) {
                    const existing = Chart.getChart(trendEl);
                    if (existing) existing.destroy();

                    if (this.galleryStats.timeline && this.galleryStats.timeline.length > 0) {
                        new Chart(trendEl, {
                            type: 'line',
                            data: {
                                labels: this.galleryStats.timeline.map(x => x.date),
                                datasets: [{
                                    label: 'Frames Collected',
                                    data: this.galleryStats.timeline.map(x => x.count),
                                    borderColor: '#3b82f6',
                                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                                    fill: true,
                                    tension: 0.4
                                }]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                plugins: { legend: { display: false } },
                                scales: {
                                    y: { beginAtZero: true, grid: { borderDash: [2, 4] } },
                                    x: { grid: { display: false } }
                                }
                            }
                        });
                    }
                }

                // 2. Platform Chart
                const platEl = document.getElementById('galleryPlatformChart');
                if (platEl) {
                    const existing = Chart.getChart(platEl);
                    if (existing) existing.destroy();

                    if (this.galleryStats.platforms) {
                        const data = this.galleryStats.platforms;
                        new Chart(platEl, {
                            type: 'doughnut',
                            data: {
                                labels: Object.keys(data),
                                datasets: [{
                                    data: Object.values(data),
                                    backgroundColor: ['#ef4444', '#10b981', '#3b82f6', '#f59e0b'],
                                    borderWidth: 0
                                }]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                plugins: {
                                    legend: { position: 'right', labels: { boxWidth: 12 } }
                                },
                                cutout: '70%'
                            }
                        });
                    }
                }
                // 3. Object Stats Chart
                const objEl = document.getElementById('galleryObjectChart');
                if (objEl) {
                    const existing = Chart.getChart(objEl);
                    if (existing) existing.destroy();

                    if (this.galleryStats.objects) {
                        const data = this.galleryStats.objects;
                        new Chart(objEl, {
                            type: 'bar',
                            data: {
                                labels: Object.keys(data),
                                datasets: [{
                                    label: 'Count',
                                    data: Object.values(data),
                                    backgroundColor: '#8b5cf6',
                                    borderRadius: 4
                                }]
                            },
                            options: {
                                indexAxis: 'y',
                                responsive: true,
                                maintainAspectRatio: false,
                                plugins: { legend: { display: false } },
                                scales: { x: { beginAtZero: true } }
                            }
                        });
                    }
                }

                // 4. Model Stats Chart
                const modelEl = document.getElementById('galleryModelChart');
                if (modelEl) {
                    const existing = Chart.getChart(modelEl);
                    if (existing) existing.destroy();

                    if (this.galleryStats.models) {
                        const data = this.galleryStats.models;
                        new Chart(modelEl, {
                            type: 'bar',
                            data: {
                                labels: Object.keys(data),
                                datasets: [{
                                    label: 'Winner Count',
                                    data: Object.values(data),
                                    backgroundColor: ['#f472b6', '#22d3ee', '#a78bfa'],
                                }]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                plugins: { legend: { display: false } },
                                scales: { y: { beginAtZero: true } }
                            }
                        });
                    }
                }

            } catch (e) {
                console.error("Error drawing interface:", e);
                this.showNotify('Chart Error: ' + e.message, 'error');
            }
        },

        async loadGallery() {
            if (this.galleryMode === 'grouped') {
                await this.loadGalleryGroups();
            } else {
                await this.loadGalleryFrames();
            }
        },

        async loadGalleryGroups() {
            this.galleryLoading = true;
            try {
                const params = new URLSearchParams({
                    page: this.galleryPage,
                    per_page: this.galleryPerPage,
                    platform: this.galleryFilterPlatform,
                    search: this.gallerySearchQuery
                });

                if (this.galleryFilterLabelStatus && this.galleryFilterLabelStatus !== 'all') {
                    params.append('label_status', this.galleryFilterLabelStatus);
                }

                const response = await fetch(`/api/dataset/groups?${params}`);
                const data = await response.json();

                if (response.ok) {
                    this.galleryGroups = data.groups || [];
                    this.galleryTotalPages = data.total_pages || 1;
                    this.galleryTotalGroups = data.total_groups || 0;

                    // Refresh stats on first page load
                    if (this.galleryPage === 1) {
                        this.loadGalleryStats();
                    }
                } else {
                    console.error("[DEBUG] Groups API Failed:", data);
                }
            } catch (error) {
                this.showNotify('Lỗi tải groups: ' + error.message, 'error');
            } finally {
                this.galleryLoading = false;
            }
        },

        async toggleGroup(group) {
            // Check if already expanded
            const idx = this.galleryExpandedGroups.indexOf(group.video_id);
            if (idx > -1) {
                // Collapse
                this.galleryExpandedGroups.splice(idx, 1);
            } else {
                // Expand
                this.galleryExpandedGroups.push(group.video_id);
                // Load frames if not present
                if (!this.galleryGroupFrames[group.video_id]) {
                    // Fix: Pass platform to ensure correct DB collection is queried (Camera vs Video)
                    await this.loadGroupFrames(group.video_id, group.platform);
                }
            }
        },

        async loadGroupFrames(videoId, platform = '') {
            try {
                // Fetch up to 100 frames for preview in the group
                const params = new URLSearchParams({
                    video_id: videoId,
                    per_page: 100,
                    platform: platform || this.galleryFilterPlatform,
                });
                if (this.galleryFilterLabelStatus && this.galleryFilterLabelStatus !== 'all') {
                    params.append('label_status', this.galleryFilterLabelStatus);
                }
                const url = `/api/frames?${params.toString()}`;
                const response = await fetch(url);
                const data = await response.json();
                if (response.ok) {
                    // Use Vue.set or re-assign object for reactivity if needed, 
                    // but Alpine usually reacts to property assignment
                    this.galleryGroupFrames[videoId] = data.frames || [];
                }
            } catch (error) {
                console.error("Error loading group frames", error);
            }
        },

        async loadGalleryFrames() {
            this.galleryLoading = true;
            try {
                const params = new URLSearchParams({
                    page: this.galleryPage,
                    per_page: 24, // Flat view has more items
                    platform: this.galleryFilterPlatform,
                    search: this.gallerySearchQuery
                });
                if (this.galleryFilterLabelStatus && this.galleryFilterLabelStatus !== 'all') {
                    params.append('label_status', this.galleryFilterLabelStatus);
                }

                const response = await fetch(`/api/frames?${params}`);
                const data = await response.json();

                if (response.ok) {
                    this.galleryFrames = data.frames || [];
                    this.galleryTotalPages = data.total_pages || 1;
                    this.galleryTotalFrames = data.total_frames || 0;

                    // If we just loaded the gallery, also refresh stats
                    if (this.galleryPage === 1 && !this.galleryStats.total_frames) {
                        this.loadGalleryStats();
                    }
                } else {
                    this.showNotify(data.error || 'Lỗi khi tải gallery', 'error');
                }
            } catch (error) {
                this.showNotify('Lỗi kết nối: ' + error.message, 'error');
            } finally {
                this.galleryLoading = false;
            }
        },

        changeGalleryPage(page) {
            if (page >= 1 && page <= this.galleryTotalPages) {
                this.galleryPage = page;
                this.loadGallery();
            }
        },

        openGalleryModal(frame) {
            this.selectedGalleryFrame = frame;
            this.showGalleryModal = true;
            // Reset toggle nhưng đồng bộ với checkbox mặc định
            this.isVisualized = false;

            // Auto fetch labels if available
            if (frame.label_status === 'labeled') {
                this.fetchRawLabels();

                // Nếu checkbox "Show Bounding Boxes" đang mặc định bật trong template,
                // tự động bật visualized khi có sẵn visualized_url để tránh phải tắt/bật lại
                if (frame.visualized_url) {
                    this.toggleVisualized();
                }
            }
        },

        // Missing state variables fixed
        editKeywordForm: {
            keyword: '',
            num_videos: 1,
            description: ''
        },
        updatingKeyword: false,

        handleInferenceVideoUpload(event) {
            const file = event.target.files[0];
            if (!file) return;
            // Limit size to 100MB
            if (file.size > 100 * 1024 * 1024) {
                this.showNotify('Video quá lớn. Vui lòng chọn file < 100MB', 'error');
                return;
            }
            this.inferenceUploadFile = file;
            this.inferenceStatus = null;
            this.inferenceResultUrl = null;
            this.inferenceError = null;
        },

        resetInference() {
            // Xóa Job đang chạy/kết thúc để upload video mới
            if (this.inferencePollingInterval) clearInterval(this.inferencePollingInterval);
            this.inferenceJobId = null;
            localStorage.removeItem('inference_job_id');
            this.inferenceStatus = null;
            this.inferenceProgress = 0;
            this.inferencePreviewUrl = '';
            this.inferenceResultUrl = '';
            this.inferenceUploadFile = null;
            this.previewLoopStarted = false;
        },

        async submitInferenceVideo() {
            if (!this.inferenceUploadFile) return;

            this.inferenceLoading = true;
            this.inferenceStatus = 'pending';
            this.inferenceProgress = 0;
            this.inferenceResultUrl = null;
            this.inferenceError = null;
            this.inferenceCounts = {};
            this.inferencePreviewUrl = null;
            this.inferenceGallerySnapshots = [];
            this.inferenceProcessingFps = 0;
            this.inferenceFrameCount = 0;
            // Clear preview refresh interval if any
            if (this.inferencePreviewRefreshInterval) {
                clearInterval(this.inferencePreviewRefreshInterval);
                this.inferencePreviewRefreshInterval = null;
            }

            const formData = new FormData();
            formData.append('video', this.inferenceUploadFile);
            formData.append('enable_counting', this.inferenceEnableCounting);
            if (this.inferenceLineY) {
                formData.append('line_y', this.inferenceLineY);
            }
            // Camera & date metadata
            if (this.inferenceSelectedCamera) {
                formData.append('camera_id',   this.inferenceSelectedCamera.camera_id);
                formData.append('camera_name', this.inferenceSelectedCamera.camera_name);
                formData.append('location',    this.inferenceSelectedCamera.location);
            }
            if (this.inferenceRecordDate) {
                formData.append('record_date', this.inferenceRecordDate);
            }

            try {
                const response = await fetch('/api/inference/upload', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (response.ok) {
                    this.showNotify('Đã gửi video vào hàng đợi xử lý', 'success');
                    this.inferenceStatus = 'processing';
                    this.startInferencePolling(data.job_id);
                } else {
                    this.inferenceStatus = 'failed';
                    this.inferenceError = data.error || 'Lỗi server';
                    this.showNotify(this.inferenceError, 'error');
                }
            } catch (error) {
                this.inferenceStatus = 'failed';
                this.inferenceError = error.message;
                this.showNotify('Lỗi kết nối: ' + error.message, 'error');
            } finally {
                this.inferenceLoading = false;
            }
        },

        startInferencePolling(jobId) {
            if (this.inferencePollingInterval) clearInterval(this.inferencePollingInterval);
            
            // Apply chart filters to match the current running video and draw in real-time
            if (this.inferenceSelectedCameraId) this.analyticsFilterCamera = this.inferenceSelectedCameraId;
            const tzOff = new Date().getTimezoneOffset() * 60000;
            const localIsStr = new Date(Date.now() - tzOff).toISOString().slice(0, 16);
            const recDt = this.inferenceRecordDate || localIsStr;
            if (recDt) this.analyticsFilterStart = recDt;
            // Xóa Đích đến để lấy hết mốc thời gian trở về sau
            this.analyticsFilterEnd = '';
            this.loadInferenceAnalytics();
            
            let pollCounter = 0;

            this.inferencePollingInterval = setInterval(async () => {
                pollCounter++;
                try {
                    const response = await fetch(`/api/inference/status/${jobId}`);
                    const data = await response.json();

                    if (response.ok) {
                        this.inferenceStatus = data.status;

                        if (typeof data.progress === 'number') {
                            this.inferenceProgress = Math.round(data.progress);
                        }
                        
                        // Realtime chart fetching 
                        if (data.status === 'processing' && pollCounter % 2 === 0) {
                            this.loadInferenceAnalytics();
                        }

                        // Live preview & FPS
                        if (data.preview_url) {
                            // MJPEG Stream handle by browser natively - NO STUTTER!
                            if (!this.previewLoopStarted) {
                                this.inferencePreviewUrl = `/api/inference/stream/${jobId}`;
                                this.previewLoopStarted = true;
                            }
                        }
                        if (typeof data.processing_fps === 'number') {
                            this.inferenceProcessingFps = data.processing_fps;
                        }
                        if (Array.isArray(data.gallery_snapshots)) {
                            this.inferenceGallerySnapshots = data.gallery_snapshots;
                        }
                        if (typeof data.frame_count === 'number') {
                            this.inferenceFrameCount = data.frame_count;
                        }
                        if (typeof data.video_fps === 'number' && data.video_fps > 0) {
                            this.inferenceVideoFps = data.video_fps;
                        }
                        if (typeof data.total_frames === 'number' && data.total_frames > 0) {
                            this.inferenceTotalFrames = data.total_frames;
                        }

                        if (data.status === 'completed') {
                            this.inferenceResultUrl = data.output_url;
                            if (data.counts) {
                                this.inferenceCounts = data.counts;
                            }
                            clearInterval(this.inferencePollingInterval);
                            if (this.inferencePreviewRefreshInterval) {
                                clearInterval(this.inferencePreviewRefreshInterval);
                                this.inferencePreviewRefreshInterval = null;
                            }
                            this.showNotify('Nhận diện video hoàn tất!', 'success');
                            // Reload history table and charts
                            this.loadInferenceHistory();
                            setTimeout(() => this.loadInferenceAnalytics(), 500);
                        } else if (data.status === 'failed') {
                            this.inferenceError = data.error || 'Lỗi không xác định trong quá trình xử lý.';
                            clearInterval(this.inferencePollingInterval);
                            if (this.inferencePreviewRefreshInterval) {
                                clearInterval(this.inferencePreviewRefreshInterval);
                                this.inferencePreviewRefreshInterval = null;
                            }
                            this.showNotify('Lỗi xử lý video', 'error');
                        }
                    }
                } catch (error) {
                    console.error('Lỗi khi poll trạng thái:', error);
                }
            }, 2000);
        },

        async loadInferenceCameras() {
            try {
                const response = await fetch('/api/inference/cameras');
                const data = await response.json();
                if (data.success) {
                    this.inferenceCameraList = data.cameras;
                }
            } catch (e) {
                console.error('Failed to load camera list', e);
            }
        },

        onInferenceCameraSelect() {
            const cam = this.inferenceCameraList.find(c => c.camera_id === this.inferenceSelectedCameraId);
            this.inferenceSelectedCamera = cam || null;
        },

        async loadInferenceHistory(page = 1) {
            this.inferenceHistoryLoading = true;
            this.inferenceHistoryPage    = page;
            try {
                let url = `/api/inference/history?page=${page}&per_page=10`;
                if (this.inferenceHistoryDateFilter) {
                    url += `&date=${this.inferenceHistoryDateFilter}`;
                }
                const response = await fetch(url);
                const data = await response.json();
                if (data.success) {
                    this.inferenceHistory       = data.records || [];
                    this.inferenceHistoryTotal  = data.total || 0;
                    this.inferenceHistoryTotalPages = data.total_pages || 1;
                }
            } catch (e) {
                console.error('Failed to load inference history', e);
            } finally {
                this.inferenceHistoryLoading = false;
            }
        },

        formatInferenceDate(isoStr) {
            if (!isoStr) return '—';
            try {
                const d = new Date(isoStr);
                return d.toLocaleString('vi-VN', { dateStyle: 'short' });
            } catch { return isoStr; }
        },

        async loadInferenceAnalytics() {
            try {
                const params = new URLSearchParams();
                if (this.analyticsFilterCamera) params.append('camera_id', this.analyticsFilterCamera);
                if (this.analyticsFilterStart) params.append('start', new Date(this.analyticsFilterStart).toISOString());
                if (this.analyticsFilterEnd) params.append('end', new Date(this.analyticsFilterEnd).toISOString());
                if (this.analyticsFilterCamDate) params.append('cam_date', this.analyticsFilterCamDate);

                const qs = params.toString() ? `?${params.toString()}` : '';
                const response = await fetch('/api/inference/analytics' + qs);
                const data = await response.json();
                if (!data.success) return;

                this.inferenceCachedAnalytics = data;  // cache for redraw
                this.drawInferenceCharts(data);
            } catch (e) {
                console.error('Failed to load analytics', e);
            }
        },

        redrawInferenceCharts() {
            if (this.inferenceCachedAnalytics) {
                this.drawInferenceCharts(this.inferenceCachedAnalytics);
            }
        },

        drawInferenceCharts(data) {
            const byHour   = data.by_hour   || [];
            const byCamera = data.by_camera  || [];
            const byCity   = data.by_city    || [];
            // Dùng ngưỡng từ user input (state) thay vì từ API
            const threshold = Number(this.inferenceCongestionThreshold) || 200;

            // ── Màu sắc xe ──────────────────────────────────────────────────
            const COLORS = {
                car:        'rgba(59, 130, 246, 0.85)',   // blue
                motorcycle: 'rgba(249, 115, 22, 0.85)',   // orange
                bus:        'rgba(234, 179, 8, 0.85)',    // yellow
                truck:      'rgba(239, 68, 68, 0.85)',    // red
            };

            // ── 1. CHART: Lưu lượng theo giờ (line chart stacked) ────────
            const hourEl = document.getElementById('inferenceHourChart');
            if (hourEl) {
                const existing = Chart.getChart(hourEl);
                if (existing) existing.destroy();

                const labels = byHour.map(h => h.label);
                // Đường ngưỡng tắc
                const thresholdLine = byHour.map(() => threshold);

                new Chart(hourEl, {
                    type: 'bar',
                    data: {
                        labels,
                        datasets: [
                            { label: 'Xe hơi',  data: byHour.map(h => h.car),        backgroundColor: COLORS.car,        stack: 'a' },
                            { label: 'Xe máy',  data: byHour.map(h => h.motorcycle), backgroundColor: COLORS.motorcycle, stack: 'a' },
                            { label: 'Bus',     data: byHour.map(h => h.bus),        backgroundColor: COLORS.bus,        stack: 'a' },
                            { label: 'Xe tải',  data: byHour.map(h => h.truck),      backgroundColor: COLORS.truck,      stack: 'a' },
                            {
                                label: '⚠️ Ngưỡng tắc đường',
                                data: thresholdLine,
                                type: 'line',
                                borderColor: 'rgba(220,38,38,0.9)',
                                borderWidth: 2,
                                borderDash: [6, 3],
                                pointRadius: 0,
                                fill: false,
                                tension: 0,
                                stack: undefined,
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: { mode: 'index', intersect: false },
                        plugins: {
                            legend: { position: 'top', labels: { boxWidth: 12, font: { size: 11 } } },
                            tooltip: {
                                callbacks: {
                                    afterTitle: (items) => {
                                        const total = items
                                            .filter(i => i.datasetIndex < 4)
                                            .reduce((s, i) => s + i.parsed.y, 0);
                                        return total >= threshold
                                            ? `⚠️ Tổng: ${total} — KHẢ NĂNG TẮC ĐƯỜNG!`
                                            : `Tổng: ${total} xe`;
                                    }
                                }
                            }
                        },
                        scales: {
                            x: { stacked: true, grid: { display: false } },
                            y: { stacked: true, beginAtZero: true, title: { display: true, text: 'Số phương tiện' } }
                        }
                    }
                });
            }

            // ── 2. CHART: Top đường đông xe nhất (horizontal bar) ─────────
            const camEl = document.getElementById('inferenceCameraChart');
            if (camEl && byCamera.length > 0) {
                const existing = Chart.getChart(camEl);
                if (existing) existing.destroy();

                new Chart(camEl, {
                    type: 'bar',
                    data: {
                        labels: byCamera.map(c => c.camera_name),
                        datasets: [
                            { label: 'Xe hơi',  data: byCamera.map(c => c.car),        backgroundColor: COLORS.car        },
                            { label: 'Xe máy',  data: byCamera.map(c => c.motorcycle), backgroundColor: COLORS.motorcycle },
                            { label: 'Bus',     data: byCamera.map(c => c.bus),        backgroundColor: COLORS.bus        },
                            { label: 'Xe tải',  data: byCamera.map(c => c.truck),      backgroundColor: COLORS.truck      },
                        ]
                    },
                    options: {
                        indexAxis: 'y',
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { position: 'top', labels: { boxWidth: 12, font: { size: 11 } } },
                        },
                        scales: {
                            x: { stacked: true, beginAtZero: true },
                            y: { stacked: true }
                        }
                    }
                });
            }

            // ── 3. CHART: Phân bố theo thành phố (doughnut) ───────────────
            const cityEl = document.getElementById('inferenceCityChart');
            if (cityEl && byCity.length > 0) {
                const existing = Chart.getChart(cityEl);
                if (existing) existing.destroy();

                const CITY_COLORS = [
                    '#6366f1','#f59e0b','#10b981','#ef4444','#3b82f6',
                    '#a855f7','#ec4899','#14b8a6','#f97316','#84cc16'
                ];

                new Chart(cityEl, {
                    type: 'doughnut',
                    data: {
                        labels: byCity.map(c => c.city),
                        datasets: [{
                            data: byCity.map(c => c.total),
                            backgroundColor: CITY_COLORS.slice(0, byCity.length),
                            borderWidth: 2,
                            borderColor: '#fff',
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        cutout: '65%',
                        plugins: {
                            legend: { position: 'right', labels: { boxWidth: 12, font: { size: 11 } } },
                            tooltip: {
                                callbacks: {
                                    label: (ctx) => ` ${ctx.label}: ${ctx.parsed.toLocaleString()} xe`
                                }
                            }
                        }
                    }
                });
            }
        },


        init() {
            console.log('App initialized');
            // Load initial data based on active tab
            if (this.activeTab === 'visualization') {
                this.loadVisualization();
            }
            if (this.activeTab === 'settings') {
                this.loadSettings();
            }
            // Always load active keywords for dropdowns
            this.loadActiveKeywords();
            // Pre-load inference cameras
            this.loadInferenceCameras();
        },

        // Settings Methods
        async loadSettings() {
            console.log("Loading Settings..."); // Debug log
            this.showNotify('Debug: Loading Settings...', 'info');
            try {
                const response = await fetch('/api/settings/');
                const data = await response.json();
                if (data) {
                    this.settings = {
                        enabled_camera: data.enabled_camera || false,
                        enabled_video: data.enabled_video || false,
                        enabled_augmentation: data.enabled_augmentation !== undefined ? data.enabled_augmentation : true,
                        rotation_angle: data.rotation_angle || 15,
                        profiles: data.profiles || this.settings.profiles // Load profiles or keep default
                    };
                }
            } catch (e) {
                console.error("Error loading settings", e);
                this.showNotify('Lỗi tải cấu hình', 'error');
            }
        },

        async saveSettings() {
            this.settingsSaving = true;
            try {
                const response = await fetch('/api/settings/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.settings)
                });
                const data = await response.json();

                // Ensure profiles structure exists (handle migration on frontend if backend missed something)
                if (!data.profiles) {
                    data.profiles = this.settings.profiles; // Use default
                }

                if (data.success) {
                    // Update settings but keep current profile selection
                    this.settings.profiles = data.settings.profiles || this.settings.profiles;
                    this.showNotify('Lưu cấu hình thành công', 'success');
                } else {
                    this.showNotify('Lỗi khi lưu: ' + data.error, 'error');
                }
            } catch (e) {
                this.showNotify('Lỗi kết nối', 'error');
            } finally {
                this.settingsSaving = false;
            }
        },

        handlePreviewImageUpload(event) {
            const file = event.target.files[0];
            if (!file) return;

            this.settingsPreviewFile = file;

            // Show original locally
            const reader = new FileReader();
            reader.onload = (e) => {
                this.originalPreviewImage = e.target.result;
                // Trigger initial preview
                this.previewSettings();
            };
            reader.readAsDataURL(file);
        },

        debouncePreview() {
            if (this.previewDebounceTimer) clearTimeout(this.previewDebounceTimer);
            this.previewDebounceTimer = setTimeout(() => {
                this.previewSettings();
            }, 500); // 500ms delay
        },

        async previewSettings() {
            if (!this.settingsPreviewFile) return;

            this.previewLoading = true;
            try {
                const formData = new FormData();
                formData.append('image', this.settingsPreviewFile);
                formData.append('settings', JSON.stringify(this.settings));
                formData.append('preview_profile', this.activeProfile);

                const response = await fetch('/api/settings/preview', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();

                if (data.success) {
                    this.processedPreviewImage = data.image; // Base64
                    this.previewMetrics = {
                        before: data.metrics_before,
                        after: data.metrics_after
                    };
                    this.previewDetectedProfile = data.detected_profile;
                } else {
                    this.showNotify(data.error || 'Preview failed', 'error');
                }
            } catch (e) {
                console.error(e);
            } finally {
                this.previewLoading = false;
            }
        },
        // Methods


        async loadVideos() {
            try {
                const params = new URLSearchParams({
                    page: this.currentPage,
                    per_page: this.perPage,
                });
                if (this.searchQuery) {
                    params.append('search', this.searchQuery);
                }

                const response = await fetch(`/api/videos?${params}`);
                const data = await response.json();

                if (response.ok) {
                    this.videos = data.videos || [];
                    this.totalPages = data.total_pages || 1;
                    this.renderVideosTable();
                } else {
                    this.showNotify(data.error || 'Lỗi khi tải danh sách video', 'error');
                }
            } catch (error) {
                this.showNotify('Lỗi kết nối: ' + error.message, 'error');
            }
        },

        renderVideosTable() {
            if (this.videos.length === 0) {
                this.videosTableBody = `
                    <tr>
                        <td colspan="8" class="px-6 py-4 text-center text-gray-500">
                            Không có video nào
                        </td>
                    </tr>
                `;
                return;
            }

            this.videosTableBody = this.videos.map(video => {
                // Lấy duration và resolution từ metadata
                const duration = (video.metadata && video.metadata.duration)
                    ? this.formatDuration(video.metadata.duration)
                    : (video.duration ? this.formatDuration(video.duration) : 'N/A');
                const resolution = (video.metadata && video.metadata.resolution)
                    ? video.metadata.resolution
                    : (video.resolution || 'N/A');
                const method = video.download_method === 'url'
                    ? '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-purple-100 text-purple-800">URL</span>'
                    : '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800">Keyword</span>';
                const keyword = video.keyword || '-';
                const downloadedAt = video.downloaded_at
                    ? new Date(video.downloaded_at).toLocaleString('vi-VN')
                    : 'N/A';

                return `
                    <tr class="hover:bg-gray-50">
                        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                            ${video.video_id}
                        </td>
                        <td class="px-6 py-4 text-sm text-gray-900">
                            <a href="${video.url}" target="_blank" class="text-blue-600 hover:text-blue-800">
                                ${this.truncate(video.title, 50)}
                            </a>
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            ${resolution}
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            ${duration}
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                             <span class="font-mono text-xs bg-gray-100 px-2 py-1 rounded border border-gray-200">${(video.media_type || 'mp4').toUpperCase()}</span>
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            <span class="px-2 py-1 text-xs font-semibold rounded-full ${video.platform === 'pexels' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                                ${video.platform || 'youtube'}
                            </span>
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm">
                            ${method}
                        </td>
                        <td class="px-6 py-4 text-sm text-gray-500">
                            ${keyword}
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            ${downloadedAt}
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm">
                            <a href="${video.url}" target="_blank" 
                               class="text-blue-600 hover:text-blue-800">
                                <i class="fas fa-external-link-alt"></i>
                            </a>
                        </td>
                    </tr>
                `;
            }).join('');
        },


        changePage(page) {
            if (page >= 1 && page <= this.totalPages) {
                this.currentPage = page;
                this.loadVideos();
            }
        },

        formatDuration(seconds) {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = seconds % 60;

            if (hours > 0) {
                return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
            }
            return `${minutes}:${secs.toString().padStart(2, '0')}`;
        },

        truncate(str, length) {
            if (str.length <= length) return str;
            return str.substring(0, length) + '...';
        },

        showNotify(message, type = 'success') {
            // Sử dụng Toastify để hiển thị thông báo
            const backgroundColor = type === 'success' ? '#10B981' : type === 'error' ? '#EF4444' : '#3B82F6';
            const icon = type === 'success' ? '✓' : type === 'error' ? '✗' : 'ℹ';

            Toastify({
                text: `${icon} ${message}`,
                duration: 5000,
                gravity: "top",
                position: "right",
                backgroundColor: backgroundColor,
                stopOnFocus: true,
                className: "toastify-custom",
                style: {
                    borderRadius: "8px",
                    padding: "12px 16px",
                    fontSize: "14px",
                    fontWeight: "500",
                    boxShadow: "0 4px 6px rgba(0, 0, 0, 0.1)"
                }
            }).showToast();

            // Giữ lại notification cũ để tương thích
            this.notificationMessage = message;
            this.notificationType = type;
            this.showNotification = true;
            setTimeout(() => {
                this.showNotification = false;
            }, 3000);
        },

        async loadKeywords() {
            try {
                const response = await fetch('/api/keywords');
                const data = await response.json();

                if (response.ok) {
                    this.keywords = data.keywords || [];
                    this.renderKeywordsManagementTable();
                    // Load visualization data để hiển thị Top Keywords (chỉ load data, không render visualization table)
                    try {
                        const vizResponse = await fetch('/api/visualization');
                        const vizData = await vizResponse.json();
                        if (vizResponse.ok) {
                            this.vizData = vizData || {};
                            // Chỉ render Top Keywords, không render visualization table
                            this.renderKeywordsTable();
                        }
                    } catch (vizError) {
                        console.error('Error loading visualization data:', vizError);
                    }
                } else {
                    this.showNotify(data.error || 'Lỗi khi tải danh sách keywords', 'error');
                }
            } catch (error) {
                this.showNotify('Lỗi kết nối: ' + error.message, 'error');
            }
        },

        renderKeywordsTable() {
            // Render Top Keywords từ visualization data
            if (!this.vizData.by_keyword || this.vizData.by_keyword.length === 0) {
                this.keywordsTableBody = `
                    <tr>
                        <td colspan="5" class="px-6 py-4 text-center text-gray-500">
                            Chưa có dữ liệu. Vui lòng tải video trước!
                        </td>
                    </tr>
                `;
                return;
            }

            const total = this.vizData.by_keyword.reduce((sum, kw) => sum + kw.count, 0);
            this.keywordsTableBody = this.vizData.by_keyword.map((kw, index) => {
                const percentage = total > 0 ? ((kw.count / total) * 100).toFixed(2) : 0;

                // --- ADDED: Labeled Count Check ---
                // Avoid displaying 0 if labeled_count is undefined/null
                const labeledCount = (kw.labeled_count !== undefined && kw.labeled_count !== null) ? kw.labeled_count : 0;

                return `
                    <tr class="hover:bg-gray-50">
                        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${index + 1}</td>
                        <td class="px-6 py-4 text-sm text-gray-900">${kw.keyword}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${kw.count}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-yellow-600 font-semibold">${labeledCount}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm">
                            <div class="flex items-center">
                                <div class="w-full bg-gray-200 rounded-full h-2 mr-2">
                                    <div class="bg-blue-600 h-2 rounded-full" style="width: ${percentage}%"></div>
                                </div>
                                <span class="text-gray-600">${percentage}%</span>
                            </div>
                        </td>
                    </tr>
                `;
            }).join('');
        },

        renderKeywordsManagementTable() {
            console.log('Rendering keywords management table, count:', this.keywords.length); // Debug
            if (this.keywords.length === 0) {
                this.vizKeywordsTableBody = `
                    <tr>
                        <td colspan="7" class="px-6 py-4 text-center text-gray-500">
                            Chưa có keyword nào. Hãy thêm keyword mới!
                        </td>
                    </tr>
                `;
                // Setup event listeners sau khi render
                setTimeout(() => this.setupKeywordActions(), 100);
                return;
            }

            this.vizKeywordsTableBody = this.keywords.map((kw, index) => {
                const statusColors = {
                    'pending': 'bg-yellow-100 text-yellow-800',
                    'processing': 'bg-blue-100 text-blue-800',
                    'completed': 'bg-green-100 text-green-800',
                    'failed': 'bg-red-100 text-red-800'
                };
                const statusText = {
                    'pending': 'Chờ xử lý',
                    'processing': 'Đang tải',
                    'completed': 'Hoàn thành',
                    'failed': 'Thất bại'
                };
                const statusClass = statusColors[kw.status] || 'bg-gray-100 text-gray-800';
                const statusLabel = statusText[kw.status] || kw.status;

                return `
                    <tr class="hover:bg-gray-50">
                        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                            ${index + 1}
                        </td>
                        <td class="px-6 py-4 text-sm text-gray-900">
                            <strong>${kw.keyword}</strong>
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            ${kw.num_videos}
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            ${kw.total_downloaded || 0}
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm">
                            <span class="px-2 py-1 text-xs font-semibold rounded-full ${statusClass}">
                                ${statusLabel}
                            </span>
                        </td>
                        <td class="px-6 py-4 text-sm text-gray-500">
                            ${kw.description || '-'}
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm">
                            <div class="flex items-center gap-2">
                                <button 
                                    data-keyword-id="${kw._id || kw.id}"
                                    data-action="edit"
                                    class="keyword-action-btn text-yellow-600 hover:text-yellow-800"
                                    title="Sửa"
                                >
                                    <i class="fas fa-edit"></i>
                                </button>
                               
                                <button 
                                    data-keyword-id="${kw._id || kw.id}"
                                    data-action="delete"
                                    class="keyword-action-btn text-red-600 hover:text-red-800"
                                    title="Xóa"
                                >
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                        </td>
                    </tr>
                `;
            }).join('');

            // Setup event listeners sau khi render
            setTimeout(() => this.setupKeywordActions(), 100);
        },

        async addKeyword() {
            if (!this.newKeyword.keyword.trim()) {
                this.showNotify('Vui lòng nhập từ khóa', 'error');
                return;
            }

            this.addingKeyword = true;
            try {
                const response = await fetch('/api/keywords', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(this.newKeyword),
                });

                const data = await response.json();
                if (response.ok) {
                    this.showNotify(data.message || 'Đã thêm keyword thành công', 'success');
                    this.newKeyword = { keyword: '', num_videos: 1, description: '' };
                    this.loadKeywords();
                } else {
                    this.showNotify(data.error || 'Có lỗi xảy ra', 'error');
                }
            } catch (error) {
                this.showNotify('Lỗi kết nối: ' + error.message, 'error');
            } finally {
                this.addingKeyword = false;
            }
        },

        async downloadKeyword(keywordId) {
            if (!confirm('Bạn có chắc muốn tải video cho keyword này?')) {
                return;
            }

            try {
                const response = await fetch(`/api/keywords/${keywordId}/download`, {
                    method: 'POST',
                });

                const data = await response.json();
                if (response.ok) {
                    this.showNotify(data.message || 'Đã bắt đầu tải video', 'success');
                    // Kiểm tra kết quả download và extract frames
                    this.checkYouTubeDownloadResult();
                    setTimeout(() => {
                        this.loadKeywords();
                    }, 2000);
                } else {
                    this.showNotify(data.error || 'Có lỗi xảy ra', 'error');
                }
            } catch (error) {
                this.showNotify('Lỗi kết nối: ' + error.message, 'error');
            }
        },

        async checkYouTubeDownloadResult() {
            // Kiểm tra kết quả extract frames sau khi download YouTube xong
            let attempts = 0;
            const maxAttempts = 120; // Tối đa 10 phút (120 * 5s)

            const checkInterval = setInterval(async () => {
                attempts++;

                try {
                    const response = await fetch('/api/frames/youtube-result');
                    const data = await response.json();

                    if (data.exists && data.result) {
                        clearInterval(checkInterval);
                        if (data.result.success) {
                            const totalFrames = data.result.total_frames || 0;
                            const videos = data.result.videos || [];
                            this.showNotify(
                                `✅ Tạo frame từ video thành công! Đã tạo ${totalFrames} frame từ ${videos.length} video`,
                                'success'
                            );
                        } else {
                            this.showNotify(
                                `❌ Tạo frame từ video thất bại: ${data.result.error || 'Lỗi không xác định'}`,
                                'error'
                            );
                        }
                    } else if (attempts >= maxAttempts) {
                        clearInterval(checkInterval);
                    }
                } catch (error) {
                    // Lỗi khi check, tiếp tục thử
                    if (attempts >= maxAttempts) {
                        clearInterval(checkInterval);
                    }
                }
            }, 5000); // Check mỗi 5 giây
        },

        async checkPexelsExtractResult() {
            // Kiểm tra kết quả extract frames sau khi download Pexels xong
            let attempts = 0;
            const maxAttempts = 120; // Tối đa 10 phút (120 * 5s)

            const checkInterval = setInterval(async () => {
                attempts++;

                try {
                    const response = await fetch('/api/frames/result');
                    const result = await response.json();

                    if (result.success !== undefined) {
                        clearInterval(checkInterval);
                        if (result.success) {
                            const totalFrames = result.total_frames || 0;
                            const videos = result.videos || [];
                            this.showNotify(
                                `✅ Tạo frame từ video thành công! Đã tạo ${totalFrames} frame từ ${videos.length} video`,
                                'success'
                            );
                        } else {
                            this.showNotify(
                                `❌ Tạo frame từ video thất bại: ${result.error || 'Lỗi không xác định'}`,
                                'error'
                            );
                        }
                    } else if (attempts >= maxAttempts) {
                        clearInterval(checkInterval);
                    }
                } catch (error) {
                    // Lỗi khi check, tiếp tục thử
                    if (attempts >= maxAttempts) {
                        clearInterval(checkInterval);
                    }
                }
            }, 5000); // Check mỗi 5 giây
        },

        setupKeywordActions() {
            // Remove old event listeners first to avoid duplicates
            document.querySelectorAll('.keyword-action-btn').forEach(btn => {
                const newBtn = btn.cloneNode(true);
                btn.parentNode.replaceChild(newBtn, btn);
            });

            // Add new event listeners
            document.querySelectorAll('.keyword-action-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    const keywordId = btn.getAttribute('data-keyword-id'); // MongoDB dùng string ID
                    const action = btn.getAttribute('data-action');

                    console.log('Keyword action clicked:', action, keywordId); // Debug

                    if (action === 'edit') {
                        this.editKeyword(keywordId);
                    } else if (action === 'download') {
                        this.downloadKeyword(keywordId);
                    } else if (action === 'delete') {
                        this.deleteKeyword(keywordId);
                    }
                });
            });
        },

        editKeyword(keywordId) {
            console.log('Edit keyword called with ID:', keywordId); // Debug
            console.log('Available keywords:', this.keywords.map(kw => ({ id: kw._id || kw.id, keyword: kw.keyword }))); // Debug

            const keyword = this.keywords.find(kw => {
                const kwId = kw._id || kw.id;
                return String(kwId) === String(keywordId);
            });

            if (!keyword) {
                this.showNotify('Không tìm thấy keyword với ID: ' + keywordId, 'error');
                return;
            }

            this.editingKeyword = keywordId;
            this.editKeywordForm = {
                keyword: keyword.keyword,
                num_videos: keyword.num_videos || 1,
                description: keyword.description || '',
                is_active: keyword.is_active !== undefined ? keyword.is_active : true,
                status: keyword.status || 'pending'
            };
            this.showEditKeywordModal = true;
        },

        async updateKeyword() {
            if (!this.editKeywordForm.keyword.trim()) {
                this.showNotify('Vui lòng nhập từ khóa', 'error');
                return;
            }

            this.updatingKeyword = true;
            try {
                const response = await fetch(`/api/keywords/${this.editingKeyword}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(this.editKeywordForm),
                });

                const data = await response.json();
                if (response.ok) {
                    this.showNotify(data.message || 'Đã cập nhật keyword thành công', 'success');
                    this.showEditKeywordModal = false;
                    this.editingKeyword = null;
                    this.loadKeywords();
                } else {
                    this.showNotify(data.error || 'Có lỗi xảy ra', 'error');
                }
            } catch (error) {
                this.showNotify('Lỗi kết nối: ' + error.message, 'error');
            } finally {
                this.updatingKeyword = false;
            }
        },

        async deleteKeyword(keywordId) {
            if (!confirm('Bạn có chắc muốn xóa keyword này?')) {
                return;
            }

            try {
                const response = await fetch(`/api/keywords/${keywordId}`, {
                    method: 'DELETE',
                });

                const data = await response.json();
                if (response.ok) {
                    this.showNotify(data.message || 'Đã xóa keyword thành công', 'success');
                    this.loadKeywords();
                } else {
                    this.showNotify(data.error || 'Có lỗi xảy ra', 'error');
                }
            } catch (error) {
                this.showNotify('Lỗi kết nối: ' + error.message, 'error');
            }
        },

        async loadActiveKeywords() {
            try {
                const response = await fetch('/api/keywords?active_only=true');
                const data = await response.json();

                if (response.ok) {
                    this.activeKeywords = data.keywords || [];
                    console.log('Active keywords loaded:', this.activeKeywords); // Debug
                } else {
                    console.error('Error loading active keywords:', data.error);
                    this.activeKeywords = [];
                }
            } catch (error) {
                console.error('Lỗi khi tải keywords:', error);
                this.activeKeywords = [];
            }
        },

        onKeywordSelect() {
            console.log('Keyword selected:', this.selectedKeywordId); // Debug
            console.log('Available keywords:', this.activeKeywords.map(kw => ({ id: kw._id || kw.id, keyword: kw.keyword }))); // Debug

            if (this.selectedKeywordId) {
                const selectedKw = this.activeKeywords.find(kw => {
                    const kwId = String(kw._id || kw.id);
                    const selectedId = String(this.selectedKeywordId);
                    return kwId === selectedId;
                });

                if (selectedKw) {
                    this.selectedKeyword = selectedKw;
                    this.numVideos = selectedKw.num_videos || 1;
                    console.log('Selected keyword:', selectedKw); // Debug
                } else {
                    console.error('Keyword not found:', this.selectedKeywordId); // Debug
                    this.selectedKeyword = null;
                }
            } else {
                this.selectedKeyword = null;
                this.numVideos = 1;
            }
        },

        async loadVisualization() {
            try {
                const response = await fetch('/api/visualization');
                const data = await response.json();

                if (response.ok) {
                    this.vizData = data || {};
                    setTimeout(() => {
                        try {
                            // Chỉ render visualization charts nếu đang ở tab visualization
                            if (this.activeTab === 'visualization') {
                                this.renderCharts();
                                this.renderWordCloud();
                                this.renderVisualizationKeywordsTable();
                            } else if (this.activeTab === 'keywords') {
                                // Nếu đang ở tab keywords, chỉ render Top Keywords
                                this.renderKeywordsTable();
                            }
                        } catch (e) {
                            console.error('Error rendering visualization:', e);
                        }
                    }, 100);
                } else {
                    this.showNotify(data.error || 'Lỗi khi tải dữ liệu visualization', 'error');
                    this.vizData = {};
                }
            } catch (error) {
                this.showNotify('Lỗi kết nối: ' + error.message, 'error');
                this.vizData = {};
            }
        },

        renderCharts() {
            // Helper to safely destroy chart on a canvas
            const destroyChart = (canvasId) => {
                const canvas = document.getElementById(canvasId);
                if (canvas) {
                    try {
                        const existingChart = Chart.getChart(canvas);
                        if (existingChart) {
                            existingChart.destroy();
                        }
                    } catch (e) {
                        console.warn('Error destroying chart ' + canvasId, e);
                    }
                }
            };

            // Note: We no longer maintain this.charts object for destruction, 
            // as we use Chart.getChart() to find and destroy instances attached to the DOM.
            this.charts = {};

            // Platform Chart
            if (this.vizData.by_platform && this.vizData.by_platform.length > 0) {
                destroyChart('platformChart');
                const ctx = document.getElementById('platformChart');
                if (ctx) {
                    try {
                        this.charts.platform = new Chart(ctx, {
                            type: 'doughnut',
                            data: {
                                labels: this.vizData.by_platform.map(p => p.platform),
                                datasets: [{
                                    data: this.vizData.by_platform.map(p => p.count),
                                    backgroundColor: [
                                        'rgba(59, 130, 246, 0.8)',
                                        'rgba(16, 185, 129, 0.8)',
                                        'rgba(251, 146, 60, 0.8)',
                                        'rgba(139, 92, 246, 0.8)',
                                    ]
                                }]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                plugins: {
                                    legend: { position: 'bottom' }
                                }
                            }
                        });
                    } catch (e) { console.error("Error creating platformChart", e); }
                }
            }

            // Method Chart
            if (this.vizData.by_method && this.vizData.by_method.length > 0) {
                destroyChart('methodChart');
                const ctx = document.getElementById('methodChart');
                if (ctx) {
                    const methodLabels = {
                        'keyword': 'Từ Khóa',
                        'url': 'URL',
                        'pexels': 'Pexels Dataset'
                    };

                    this.charts.method = new Chart(ctx, {
                        type: 'pie',
                        data: {
                            labels: this.vizData.by_method.map(m => methodLabels[m.method] || m.method),
                            datasets: [{
                                data: this.vizData.by_method.map(m => m.count),
                                backgroundColor: [
                                    'rgba(34, 197, 94, 0.8)',
                                    'rgba(59, 130, 246, 0.8)',
                                    'rgba(251, 146, 60, 0.8)',
                                    'rgba(139, 92, 246, 0.8)',
                                ]
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: { position: 'bottom' }
                            }
                        }
                    });
                }
            }

            // Weather Chart
            if (this.vizData.by_weather && this.vizData.by_weather.length > 0) {
                destroyChart('weatherChart');
                const ctx = document.getElementById('weatherChart');
                if (ctx) {
                    this.charts.weather = new Chart(ctx, {
                        type: 'doughnut',
                        data: {
                            labels: this.vizData.by_weather.map(w => w.weather || 'Unknown'),
                            datasets: [{
                                data: this.vizData.by_weather.map(w => w.count),
                                backgroundColor: [
                                    '#f59e0b', // Day/Sunny
                                    '#818cf8', // Night/Cloudy
                                    '#3b82f6', // Rain
                                    '#6b7280'  // Other
                                ]
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: { position: 'right' }
                            }
                        }
                    });
                }
            }

            // Resolution Chart
            if (this.vizData.by_resolution && this.vizData.by_resolution.length > 0) {
                destroyChart('resolutionChart');
                const ctx = document.getElementById('resolutionChart');
                if (ctx) {
                    this.charts.resolution = new Chart(ctx, {
                        type: 'bar',
                        data: {
                            labels: this.vizData.by_resolution.map(r => r.resolution),
                            datasets: [{
                                label: 'Số lượng video',
                                data: this.vizData.by_resolution.map(r => r.count),
                                backgroundColor: 'rgba(139, 92, 246, 0.8)'
                            }]
                        },
                        options: {
                            responsive: true,
                            plugins: {
                                legend: { display: false }
                            },
                            scales: {
                                y: { beginAtZero: true }
                            }
                        }
                    });
                }
            }

            // Duration Chart
            if (this.vizData.by_duration && this.vizData.by_duration.length > 0) {
                destroyChart('durationChart');
                const ctx = document.getElementById('durationChart');
                if (ctx) {
                    this.charts.duration = new Chart(ctx, {
                        type: 'bar',
                        data: {
                            labels: this.vizData.by_duration.map(d => d.range),
                            datasets: [{
                                label: 'Số lượng video',
                                data: this.vizData.by_duration.map(d => d.count),
                                backgroundColor: 'rgba(251, 146, 60, 0.8)'
                            }]
                        },
                        options: {
                            responsive: true,
                            plugins: {
                                legend: { display: false }
                            },
                            scales: {
                                y: { beginAtZero: true }
                            }
                        }
                    });
                }
            }

            // Time Chart
            if (this.vizData.by_date && this.vizData.by_date.length > 0) {
                destroyChart('timeChart');
                const ctx = document.getElementById('timeChart');
                if (ctx) {
                    this.charts.time = new Chart(ctx, {
                        type: 'line',
                        data: {
                            labels: this.vizData.by_date.map(d => d.date).reverse(),
                            datasets: [{
                                label: 'Số video tải về',
                                data: this.vizData.by_date.map(d => d.count).reverse(),
                                borderColor: 'rgba(59, 130, 246, 1)',
                                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                                tension: 0.4,
                                fill: true
                            }]
                        },
                        options: {
                            responsive: true,
                            plugins: {
                                legend: { display: false }
                            },
                            scales: {
                                y: { beginAtZero: true }
                            }
                        }
                    });
                }
            }
        },

        renderWordCloud() {
            if (!this.vizData.by_keyword || this.vizData.by_keyword.length === 0) {
                return;
            }

            const canvas = document.getElementById('wordcloud-canvas');
            if (!canvas || typeof WordCloud === 'undefined') return;

            // Clear canvas manually first
            const ctx = canvas.getContext('2d');
            if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);

            // Also check if there was a Chart instance (just in case)
            try {
                const existing = Chart.getChart(canvas);
                if (existing) existing.destroy();
            } catch (e) { }

            // Destroy existing chart reference if any
            if (this.charts.wordcloud && typeof this.charts.wordcloud.destroy === 'function') {
                try { this.charts.wordcloud.destroy(); } catch (e) { }
            }

            // Prepare word list for WordCloud.js
            // Format: [[word, weight], [word, weight], ...]
            const maxCount = Math.max(...this.vizData.by_keyword.map(kw => kw.count), 1);
            const words = this.vizData.by_keyword.map(kw => {
                // Calculate weight based on count
                const weight = Math.max(10, (kw.count / maxCount) * 50 + 10);
                return [kw.keyword, weight];
            });

            console.log('Word Cloud data:', {
                keywords: this.vizData.by_keyword,
                words: words
            }); // Debug

            // Create keyword map for tooltip (include count and platforms)
            const keywordMap = {};
            this.vizData.by_keyword.forEach(kw => {
                keywordMap[kw.keyword] = {
                    count: kw.count,
                    platforms: kw.platforms || [],
                    frame_count: kw.frame_count || 0,
                    labeled_count: kw.labeled_count || 0 // NEW
                };
            });

            // Set canvas size
            canvas.width = canvas.offsetWidth;
            canvas.height = 400;

            // Create tooltip element
            let tooltip = document.getElementById('wordcloud-tooltip');
            if (!tooltip) {
                tooltip = document.createElement('div');
                tooltip.id = 'wordcloud-tooltip';
                tooltip.style.cssText = 'position: absolute; background: rgba(0,0,0,0.9); color: white; padding: 8px 12px; border-radius: 6px; pointer-events: none; z-index: 1000; display: none; font-size: 14px; font-weight: bold; box-shadow: 0 4px 6px rgba(0,0,0,0.3);';
                const parent = canvas.parentElement;
                parent.style.position = 'relative';
                parent.appendChild(tooltip);
            }

            // Generate word cloud with hover callback
            WordCloud(canvas, {
                list: words,
                gridSize: Math.round(16 / Math.sqrt(Math.max(words.length, 1))),
                weightFactor: 1,
                fontFamily: 'Arial, sans-serif',
                color: function () {
                    const colors = ['#3B82F6', '#10B981', '#F59E0B', '#8B5CF6', '#EF4444', '#06B6D4'];
                    return colors[Math.floor(Math.random() * colors.length)];
                },
                rotateRatio: 0.3,
                rotationSteps: 2,
                backgroundColor: '#ffffff',
                minSize: 8,
                drawOutOfBound: false,
                shrinkToFit: true,
                // Hover callback - this is the key feature!
                hover: function (item, dimension, event) {
                    if (item) {
                        const keyword = item[0];
                        const keywordData = keywordMap[keyword] || { count: 0, platforms: [], frame_count: 0, labeled_count: 0 };
                        const count = keywordData.count;
                        const frameCount = keywordData.frame_count || 0;
                        const labeledCount = keywordData.labeled_count || 0; // NEW
                        const platforms = keywordData.platforms || [];

                        // Format platform display
                        let platformText = '';
                        if (platforms.length > 0) {
                            const platformLabels = {
                                'youtube': 'YouTube',
                                'pexels': 'Pexels'
                            };
                            const formattedPlatforms = platforms.map(p => platformLabels[p.toLowerCase()] || p).join(', ');
                            platformText = `<div style="font-size: 11px; color: #60A5FA; margin-top: 4px;">Platform: ${formattedPlatforms}</div>`;
                        }

                        tooltip.style.display = 'block';
                        tooltip.innerHTML = `
                            <div style="font-weight: bold; margin-bottom: 4px;">${keyword}</div>
                            <div style="font-size: 12px; opacity: 0.9;">${count} video(s)</div>
                            <div style="font-size: 12px; opacity: 0.9; color: #FCD34D;">${frameCount} frame(s)</div>
                            <div style="font-size: 12px; opacity: 0.9; color: #10B981;">${labeledCount} labeled</div>
                            ${platformText}
                        `;
                        tooltip.style.left = (event.pageX + 15) + 'px'; // Fix tooltip position relative to page
                        tooltip.style.top = (event.pageY) + 'px';       // Fix tooltip position relative to page
                    } else {
                        tooltip.style.display = 'none';
                        canvas.style.cursor = 'default';
                    }
                }
            });
        },

        renderVisualizationKeywordsTable() {
            if (!this.vizData.by_keyword || this.vizData.by_keyword.length === 0) {
                this.vizKeywordsTableBody = `
                    <tr>
                        <td colspan="5" class="px-6 py-4 text-center text-gray-500">Chưa có dữ liệu</td>
                    </tr>
                `;
                return;
            }

            const total = this.vizData.by_keyword.reduce((sum, kw) => sum + kw.count, 0);
            this.vizKeywordsTableBody = this.vizData.by_keyword.map((kw, index) => {
                const percentage = total > 0 ? ((kw.count / total) * 100).toFixed(2) : 0;
                const labeledCount = (kw.labeled_count !== undefined && kw.labeled_count !== null) ? kw.labeled_count : 0;

                return `
                    <tr class="hover:bg-gray-50">
                        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${index + 1}</td>
                        <td class="px-6 py-4 text-sm text-gray-900">${kw.keyword}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${kw.count}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-yellow-600 font-semibold">${labeledCount}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm">
                            <div class="flex items-center">
                                <div class="w-full bg-gray-200 rounded-full h-2 mr-2">
                                    <div class="bg-blue-600 h-2 rounded-full" style="width: ${percentage}%"></div>
                                </div>
                                <span class="text-gray-600">${percentage}%</span>
                            </div>
                        </td>
                    </tr>
                `;
            }).join('');
        },

        // ==================== CAMERA COLLECTOR FUNCTIONS ====================

        async loadCameraStatus() {
            try {
                const response = await fetch('/api/camera/status');
                const data = await response.json();

                if (response.ok) {
                    this.cameraSchedulerRunning = data.scheduler_running || false;
                    this.cameraLastCollection = data.last_collection ? this.formatDateTime(data.last_collection) : null;
                    this.cameraStats = data.statistics || { total_attempts: 0, successful: 0, failed: 0 };
                    this.activeCameras = data.cameras || [];
                } else {
                    // If camera collector is not initialized, set defaults
                    this.cameraSchedulerRunning = false;
                    this.cameraLastCollection = null;
                    this.cameraStats = { total_attempts: 0, successful: 0, failed: 0 };
                    this.activeCameras = [];
                }
            } catch (error) {
                console.error('Error loading camera status:', error);
                // Set defaults on error
                this.cameraSchedulerRunning = false;
                this.cameraLastCollection = null;
                this.cameraStats = { total_attempts: 0, successful: 0, failed: 0 };
                this.activeCameras = [];
            }
        },

        async loadCameraList() {
            try {
                const response = await fetch('/api/camera/list');
                const data = await response.json();

                if (response.ok) {
                    this.allCameras = data.cameras || [];
                    this.filteredCameraList = data.cameras || [];
                    if (data.cameras && data.cameras.length === 0 && data.message) {
                        console.warn('Camera list warning:', data.message);
                    }
                } else {
                    this.allCameras = [];
                    this.filteredCameraList = [];
                }
            } catch (error) {
                console.error('Error loading camera list:', error);
                this.allCameras = [];
                this.filteredCameraList = [];
                // Don't show error notification as it's not critical
            }
        },

        filterCameraList() {
            if (!this.cameraSearchQuery.trim()) {
                this.filteredCameraList = this.allCameras;
                return;
            }

            const query = this.cameraSearchQuery.toLowerCase();
            this.filteredCameraList = this.allCameras.filter(cam => {
                const title = (cam.title || '').toLowerCase();
                const code = (cam.code || '').toLowerCase();
                const displayName = (cam.display_name || '').toLowerCase();
                const cameraId = (cam.camera_id || '').toLowerCase();

                return title.includes(query) ||
                    code.includes(query) ||
                    displayName.includes(query) ||
                    cameraId.includes(query);
            });
        },

        onCameraSelect() {
            if (this.selectedCameraId) {
                const selected = this.allCameras.find(cam => cam.camera_id === this.selectedCameraId);
                if (selected) {
                    this.selectedCameraName = selected.title || selected.code || selected.camera_id;
                }
            } else {
                this.selectedCameraName = '';
            }
        },

        async addCamera() {
            if (!this.selectedCameraId) {
                this.showNotify('Vui lòng chọn camera', 'error');
                return;
            }

            this.addingCamera = true;
            try {
                const response = await fetch('/api/camera/add', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ camera_id: this.selectedCameraId }),
                });

                const data = await response.json();
                if (response.ok) {
                    this.showNotify(data.message || 'Đã thêm camera thành công', 'success');
                    this.selectedCameraId = '';
                    this.selectedCameraName = '';
                    this.loadCameraStatus();
                } else {
                    this.showNotify(data.message || 'Có lỗi xảy ra', 'error');
                }
            } catch (error) {
                this.showNotify('Lỗi kết nối: ' + error.message, 'error');
            } finally {
                this.addingCamera = false;
            }
        },

        async removeCamera(cameraId) {
            if (!confirm('Bạn có chắc muốn xóa camera này khỏi danh sách thu thập?')) {
                return;
            }

            try {
                const response = await fetch('/api/camera/remove', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ camera_id: cameraId }),
                });

                const data = await response.json();
                if (response.ok) {
                    this.showNotify(data.message || 'Đã xóa camera thành công', 'success');
                    this.loadCameraStatus();
                } else {
                    this.showNotify(data.message || 'Có lỗi xảy ra', 'error');
                }
            } catch (error) {
                this.showNotify('Lỗi kết nối: ' + error.message, 'error');
            }
        },

        async toggleCameraCollector() {
            this.cameraLoading = true;
            try {
                const endpoint = this.cameraSchedulerRunning ? '/api/camera/stop' : '/api/camera/start';
                const response = await fetch(endpoint, { method: 'POST' });
                const data = await response.json();

                if (response.ok) {
                    this.showNotify(data.message || 'Thành công', 'success');
                    this.loadCameraStatus();
                } else {
                    this.showNotify(data.message || 'Có lỗi xảy ra', 'error');
                }
            } catch (error) {
                this.showNotify('Lỗi kết nối: ' + error.message, 'error');
            } finally {
                this.cameraLoading = false;
            }
        },

        async loadCameraRecentImages() {
            try {
                const response = await fetch('/api/camera/recent-images?limit=12');
                const data = await response.json();

                if (response.ok) {
                    const images = data.images || [];
                    this.cameraRecentImages = images;

                    // Hiển thị ảnh mới nhất trên map nếu có
                    if (images.length > 0) {
                        const latest = images[0];
                        // Chỉ cập nhật nếu là ảnh mới hơn
                        if (!this.latestCameraImage ||
                            new Date(latest.timestamp) > new Date(this.latestCameraImage.timestamp)) {
                            this.latestCameraImage = latest;
                        }
                    }
                }
            } catch (error) {
                console.error('Error loading recent images:', error);
            }
        },

        startCameraAutoRefresh() {
            // Dừng interval cũ nếu có
            if (this.cameraAutoRefreshInterval) {
                clearInterval(this.cameraAutoRefreshInterval);
            }

            // Tự động refresh mỗi 5 giây
            this.cameraAutoRefreshInterval = setInterval(() => {
                if (this.activeTab === 'camera') {
                    this.loadCameraRecentImages();
                    this.loadCameraStatus();
                }
            }, 5000);
        },

        stopCameraAutoRefresh() {
            try {
                if (this.cameraAutoRefreshInterval) {
                    clearInterval(this.cameraAutoRefreshInterval);
                    this.cameraAutoRefreshInterval = null;
                }
            } catch (e) {
                // Ignore errors if interval doesn't exist
            }
        },



        showCameraImage(img) {
            this.selectedCameraImage = img;
            this.showCameraImageModal = true;
        },

        formatDateTime(dateString) {
            if (!dateString) return '-';
            const date = new Date(dateString);
            return date.toLocaleString('vi-VN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
        },

        // --- Gallery Functions ---

        async checkPexelsDownloadResult(progressInterval) {
            // Poll mỗi 2 giây để check kết quả
            const maxAttempts = 150; // Tối đa 5 phút (150 * 2s)
            let attempts = 0;

            const checkInterval = setInterval(async () => {
                attempts++;
                try {
                    const response = await fetch('/api/pexels/result');
                    const result = await response.json();

                    if (result.success !== undefined) {
                        clearInterval(checkInterval);
                        if (progressInterval) clearInterval(progressInterval);

                        // Complete progress
                        this.pexelsDownloadProgress = 100;

                        setTimeout(() => {
                            this.pexelsDownloading = false;
                            this.pexelsDownloadProgress = 0;
                        }, 1000);

                        if (result.success) {
                            const dbMsg = result.saved_to_db > 0 ? ` (${result.saved_to_db} video đã lưu vào database)` : '';
                            this.showNotify(`✅ Tải video thành công! Đã tải ${result.count} video vào thư mục pexels_traffic_dataset${dbMsg}`, 'success');

                            // Kiểm tra kết quả extract frames tự động
                            this.checkPexelsExtractResult();
                        } else {
                            this.showNotify(`❌ Lỗi khi tải video: ${result.error || 'Unknown error'}`, 'error');
                        }
                    } else if (attempts >= maxAttempts) {
                        clearInterval(checkInterval);
                        if (progressInterval) clearInterval(progressInterval);
                        this.pexelsDownloadProgress = 0;
                        this.pexelsDownloading = false;
                        this.showNotify('⚠️ Không nhận được kết quả sau thời gian chờ. Vui lòng kiểm tra thư mục pexels_traffic_dataset', 'error');
                    }
                } catch (error) {
                    if (attempts >= maxAttempts) {
                        clearInterval(checkInterval);
                        if (progressInterval) clearInterval(progressInterval);
                        this.pexelsDownloadProgress = 0;
                        this.pexelsDownloading = false;
                    }
                }
            }, 2000);
        },

        async extractFrames() {
            this.pexelsExtracting = true;
            this.pexelsExtractProgress = 0;

            // Poll progress từ server
            const progressInterval = setInterval(async () => {
                try {
                    const response = await fetch('/api/frames/progress');
                    const progressData = await response.json();
                    if (progressData.progress !== undefined) {
                        this.pexelsExtractProgress = Math.min(progressData.progress, 95);
                    }
                } catch (e) {
                    // Ignore errors
                }
            }, 1000);

            try {
                const response = await fetch('/api/frames/extract', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                });

                const data = await response.json();
                if (response.ok) {
                    this.showNotify(data.message || 'Đã bắt đầu tạo frame từ video', 'success');

                    // Poll để check kết quả sau khi tạo xong
                    this.checkExtractFramesResult(progressInterval);
                } else {
                    clearInterval(progressInterval);
                    this.pexelsExtractProgress = 0;
                    this.showNotify(data.message || 'Có lỗi xảy ra', 'error');
                    this.pexelsExtracting = false;
                }
            } catch (error) {
                clearInterval(progressInterval);
                this.pexelsExtractProgress = 0;
                this.showNotify('Lỗi kết nối: ' + error.message, 'error');
                this.pexelsExtracting = false;
            }
        },

        async checkExtractFramesResult(progressInterval) {
            // Poll mỗi 3 giây để check kết quả (tạo frame có thể lâu hơn)
            const maxAttempts = 200; // Tối đa 10 phút (200 * 3s)
            let attempts = 0;

            const checkInterval = setInterval(async () => {
                attempts++;
                try {
                    const response = await fetch('/api/frames/result');
                    const result = await response.json();

                    if (result.success !== undefined) {
                        clearInterval(checkInterval);
                        if (progressInterval) clearInterval(progressInterval);

                        // Complete progress
                        this.pexelsExtractProgress = 100;

                        setTimeout(() => {
                            this.pexelsExtracting = false;
                            this.pexelsExtractProgress = 0;
                        }, 1000);

                        if (result.success) {
                            const videoCount = result.videos ? result.videos.length : 0;
                            this.showNotify(`✅ Tạo frame thành công! Đã tạo ${result.total_frames} frame từ ${videoCount} video trong thư mục dataset_extracted`, 'success');
                        } else {
                            this.showNotify(`❌ Lỗi khi tạo frame: ${result.error || 'Unknown error'}`, 'error');
                        }
                    } else if (attempts >= maxAttempts) {
                        clearInterval(checkInterval);
                        if (progressInterval) clearInterval(progressInterval);
                        this.pexelsExtractProgress = 0;
                        this.pexelsExtracting = false;
                        this.showNotify('⚠️ Không nhận được kết quả sau thời gian chờ. Vui lòng kiểm tra thư mục dataset_extracted', 'error');
                    }
                } catch (error) {
                    if (attempts >= maxAttempts) {
                        clearInterval(checkInterval);
                        if (progressInterval) clearInterval(progressInterval);
                        this.pexelsExtractProgress = 0;
                        this.pexelsExtracting = false;
                    }
                }
            }, 3000);
        }
    };
}

function boxplotTab() {
    return {
        loading: false,
        success: false,
        generatedOnce: false,
        message: '',
        resultType: 'frame',
        buckets: [],
        subPrefixes: [],
        selectedBucket: '',
        currentPrefix: '',
        currentPath: [],
        boxplotData: [],
        charts: [],

        outlierFrameLoading: false,
        outlierImageUrl: null,

        async init() {
            await this.loadBuckets();
            if (this.buckets.length > 0) {
                this.selectedBucket = this.buckets[0];
                await this.loadSubPrefixes();
            }
        },

        resetPath() {
            this.currentPrefix = '';
            this.currentPath = [];
        },

        async loadBuckets() {
            try {
                const res = await fetch("/api/minio/buckets");
                const json = await res.json();
                this.buckets = json.success && json.buckets?.length ? json.buckets : ["frames"];
                console.log("Buckets loaded:", this.buckets);
            } catch (err) {
                console.error("Lỗi load buckets:", err);
                this.buckets = ["frames"];
            }
        },

        async loadSubPrefixes() {
            if (!this.selectedBucket) return;
            this.loading = true;
            try {
                let url = `/api/minio/subprefixes?bucket=${encodeURIComponent(this.selectedBucket)}`;
                if (this.currentPrefix) url += `&prefix=${encodeURIComponent(this.currentPrefix)}`;
                const res = await fetch(url);
                const json = await res.json();
                this.subPrefixes = json.success ? json.subprefixes : [];
                console.log("Subprefixes:", this.subPrefixes);
            } catch (err) {
                console.error("Lỗi load subprefixes:", err);
                this.subPrefixes = [];
            } finally {
                this.loading = false;
            }
        },

        enterFolder(folder) {
            const clean = folder.replace(/\/$/, '');
            this.currentPath.push(clean);
            this.currentPrefix = this.currentPath.join('/') + '/';
            this.loadSubPrefixes();
        },

        goUpOneLevel() {
            if (!this.currentPath.length) return;
            this.currentPath.pop();
            this.currentPrefix = this.currentPath.length ? this.currentPath.join('/') + '/' : '';
            this.loadSubPrefixes();
        },

        goToLevel(idx) {
            this.currentPath = this.currentPath.slice(0, idx + 1);
            this.currentPrefix = this.currentPath.length ? this.currentPath.join('/') + '/' : '';
            this.loadSubPrefixes();
        },

        goToRoot() {
            this.resetPath();
            this.loadSubPrefixes();
        },

        async generateBoxplot() {
            if (this.loading || !this.selectedBucket) return;
            this.loading = true;
            this.generatedOnce = true;
            this.success = false;
            this.boxplotData = [];
            this.message = '';
            this.destroyAllCharts();

            try {
                const res = await fetch("/api/boxplots/generate", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        bucket: this.selectedBucket,
                        prefix: this.currentPrefix || ""
                    })
                });
                const json = await res.json();
                console.log("Backend response:", json); // ← Debug quan trọng

                if (json.success) {
                    this.success = true;
                    this.message = json.message;
                    this.resultType = json.type || 'frame';
                    this.boxplotData = json.boxplot_data || [];
                    console.log("Boxplot data received:", this.boxplotData);
                    this.$nextTick(() => this.renderAllCharts());
                } else {
                    this.message = json.message || "Lỗi từ server";
                    console.warn("Backend error:", json.message);
                }
            } catch (err) {
                console.error("Lỗi gọi API:", err);
                this.message = "Lỗi kết nối server";
            } finally {
                this.loading = false;
            }
        },

        renderAllCharts() {
            if (!this.boxplotData.length) {
                console.warn("Không có dữ liệu boxplot để vẽ");
                return;
            }

            const self = this;

            this.destroyAllCharts();

            this.boxplotData.forEach((info, idx) => {
                const canvas = document.getElementById(`boxChart${idx}`);
                if (!canvas) return;

                const outlierPoints = (info.outliers_with_meta || []).map((o, i) => ({
                    x: 0,
                    y: o.value,
                    outlierIndex: i,
                    metadata: o.metadata
                }));

                const chart = new Chart(canvas, {
                    type: 'bar',
                    data: {
                        labels: [info.label],
                        datasets: [
                            {
                                label: info.label,
                                type: 'boxplot',
                                data: [info.values],
                                backgroundColor: 'rgba(54, 162, 235, 0.3)',
                                borderColor: 'rgba(54, 162, 235, 1)',
                                borderWidth: 2,
                                outlierColor: '#ff6384',
                                outlierRadius: 0,
                                padding: 10,
                                stats: info.stats  // ← ĐÃ THÊM → tooltip sẽ lấy được stats
                            },
                            {
                                type: 'scatter',
                                label: 'Outliers',
                                data: outlierPoints,
                                backgroundColor: '#ff6384',
                                pointRadius: 6,
                                pointHoverRadius: 10,
                                pointBorderColor: '#fff',
                                pointBorderWidth: 1.5,
                                parsing: false
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            x: { display: false },
                            y: { title: { display: true, text: "Giá trị" } }
                        },
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                enabled: true,
                                backgroundColor: 'rgba(15, 23, 42, 0.96)',
                                titleColor: '#f8fafc',
                                bodyColor: '#cbd5e1',
                                borderColor: '#475569',
                                borderWidth: 1,
                                cornerRadius: 10,
                                padding: 14,
                                titleFont: { size: 15, weight: '600' },
                                bodyFont: { size: 13 },
                                displayColors: false,
                                callbacks: {
                                    title: function (tooltipItems) {
                                        const outlier = tooltipItems[0].raw;
                                        const meta = outlier.metadata || {};
                                        return meta.filename || 'Chi tiết Outlier';
                                    },

                                    label: function (context) {
                                        const p = context.raw;
                                        const meta = p.metadata || {};

                                        // SỬA Ở ĐÂY: Lấy stats từ dataset boxplot (luôn là datasets[0])
                                        const boxDataset = context.chart.data.datasets[0];
                                        const stats = boxDataset?.stats || {};

                                        const lines = [];

                                        // THỐNG KÊ BOXPLOT (an toàn)
                                        lines.push(`Đặc trưng: ${context.chart.data.labels[0] || '?'}`);
                                        lines.push(`Tổng số mẫu: ${stats.count ?? '?'}`);
                                        lines.push(`Mean: ${stats.mean?.toFixed(2) ?? '?'}`);
                                        lines.push(`Median: ${stats.median?.toFixed(2) ?? '?'}`);
                                        lines.push(`Q1: ${stats.q1?.toFixed(2) ?? '?'}`);
                                        lines.push(`Q3: ${stats.q3?.toFixed(2) ?? '?'}`);
                                        lines.push(`Min / Max: ${stats.min?.toFixed(2) ?? '?'} – ${stats.max?.toFixed(2) ?? '?'}`);
                                        lines.push(`Số outlier: ${stats.outlier_count ?? stats.outliers?.length ?? '?'}`);

                                        // THÔNG TIN OUTLIER/FRAME
                                        lines.push('────────────────────────');
                                        lines.push(`Giá trị outlier: ${p.y?.toFixed(2) ?? '?'}`);
                                        lines.push(`File: ${meta.filename || 'unknown'}`);

                                        if (meta.bucket && meta.key) {
                                            const shortPath = meta.key.split('/').slice(-2).join('/');
                                        }

                                        if (meta.platform) lines.push(`Nguồn: ${meta.platform}`);
                                        if (meta.scene_type) lines.push(`Cảnh: ${meta.scene_type}`);

                                        return lines;
                                    }
                                }
                            }
                        },
                        onClick: function (event, elements) {
                            console.log("Chart click event fired", { elements: elements.length });

                            if (!elements.length) return;

                            const element = elements[0];
                            const datasetIndex = element.datasetIndex;
                            const index = element.index;

                            if (datasetIndex === 1) {
                                const outlier = outlierPoints[index];

                                if (outlier && outlier.metadata) {
                                    console.log("Clicked outlier:", outlier);

                                    self.openOutlierModal({
                                        feature: info.feature,
                                        label: info.label,
                                        value: outlier.y,
                                        filename: outlier.metadata.filename || 'unknown',
                                        path: outlier.metadata.local_path || outlier.metadata.path || 'unknown',
                                        bucket: outlier.metadata.bucket || self.selectedBucket,
                                        key: outlier.metadata.key || 'unknown'
                                    });
                                }
                            }
                        }
                    }
                });

                this.charts[idx] = chart;
            });
        },

        openOutlierModal(outlier) {
            console.log("openOutlierModal được gọi:", outlier);

            this.selectedOutlier = outlier;

            // Lấy filename hoặc key để kiểm tra extension
            const filename = outlier.filename || outlier.metadata?.filename || '';
            const key = outlier.key || outlier.metadata?.key || '';
            const fileExt = (filename || key).toLowerCase();

            // Kiểm tra nếu là ảnh (frame)
            const isImage = fileExt.endsWith('.png') ||
                fileExt.endsWith('.jpg') ||
                fileExt.endsWith('.jpeg');

            if (isImage) {
                const bucket = outlier.bucket || outlier.metadata?.bucket || this.selectedBucket;
                const keyToUse = outlier.key || outlier.metadata?.key;

                if (bucket && keyToUse) {
                    this.outlierImageUrl = `/api/image-proxy?bucket=${encodeURIComponent(bucket)}&key=${encodeURIComponent(keyToUse)}`;
                    this.outlierFrameLoading = true;

                    // Preload để biết load xong
                    const img = new Image();
                    img.onload = () => {
                        console.log("Ảnh preview load thành công:", this.outlierImageUrl);
                        this.outlierFrameLoading = false;
                    };
                    img.onerror = () => {
                        console.error("Load preview thất bại:", this.outlierImageUrl);
                        this.outlierFrameLoading = false;
                        this.outlierImageUrl = null; // fallback nếu lỗi
                    };
                    img.src = this.outlierImageUrl;
                } else {
                    console.warn("Thiếu bucket hoặc key để tạo preview");
                    this.outlierImageUrl = null;
                    this.outlierFrameLoading = false;
                }
            } else {
                // Không phải ảnh → coi như video hoặc unknown
                console.log("Không phải file ảnh:", fileExt);
                this.outlierImageUrl = null;
                this.outlierFrameLoading = false;
            }

            this.showOutlierModal = true;
        },

        closeOutlierModal() {
            console.log("closeOutlierModal được gọi");
            this.showOutlierModal = false;
            this.selectedOutlier = null;
            this.outlierImageUrl = null;
            this.outlierFrameLoading = false;
        },

        resetChartZoom(index) {
            if (this.charts[index]) this.charts[index].resetZoom();
        },

        destroyAllCharts() {
            this.charts.forEach(chart => chart?.destroy());
            this.charts = [];
        }
    }
}

function scatterTab() {
    return {
        showScatterFrameModal: false,
        selectedScatterFrameUrl: null,
        selectedScatterFrame: null,
        frameLoading: false,

        loading: false,
        success: false,
        generatedOnce: false,
        message: '',
        resultType: 'frame',
        buckets: [],
        subPrefixes: [],
        selectedBucket: '',
        currentPrefix: '',
        currentPath: [],
        scatterData: [],
        charts: [],

        async init() {
            console.log("Scatter module khởi động");
            await this.loadBuckets();
            if (this.buckets.length > 0) {
                this.selectedBucket = this.buckets[0];
                await this.loadSubPrefixes();
            }
        },

        resetPath() {
            this.currentPrefix = '';
            this.currentPath = [];
            this.subPrefixes = [];
        },

        async loadBuckets() {
            try {
                const res = await fetch("/api/minio/buckets");
                const json = await res.json();
                this.buckets = json.success && json.buckets?.length ? json.buckets : ["dataset"];
            } catch (err) {
                console.error("Lỗi load buckets:", err);
                this.buckets = ["dataset"];
            }
        },

        async loadSubPrefixes() {
            if (!this.selectedBucket) return;
            this.loading = true;
            try {
                let url = `/api/minio/subprefixes?bucket=${encodeURIComponent(this.selectedBucket)}`;
                if (this.currentPrefix) url += `&prefix=${encodeURIComponent(this.currentPrefix)}`;
                const res = await fetch(url);
                const json = await res.json();
                if (json.success) {
                    this.subPrefixes = json.subprefixes || [];
                } else {
                    this.subPrefixes = [];
                    this.message = json.message || "Không tải được thư mục";
                }
            } catch (err) {
                console.error(err);
                this.subPrefixes = [];
            } finally {
                this.loading = false;
            }
        },

        enterFolder(folder) {
            const clean = folder.replace(/\/$/, '');
            this.currentPath.push(clean);
            this.currentPrefix = this.currentPath.join('/') + '/';
            this.loadSubPrefixes();
        },

        goUpOneLevel() {
            if (this.currentPath.length === 0) return;
            this.currentPath.pop();
            this.currentPrefix = this.currentPath.length ? this.currentPath.join('/') + '/' : '';
            this.loadSubPrefixes();
        },

        goToLevel(index) {
            this.currentPath = this.currentPath.slice(0, index + 1);
            this.currentPrefix = this.currentPath.length ? this.currentPath.join('/') + '/' : '';
            this.loadSubPrefixes();
        },

        goToRoot() {
            this.resetPath();
            this.loadSubPrefixes();
        },

        async generateScatter() {
            if (this.loading || !this.selectedBucket) return;
            this.loading = true;
            this.generatedOnce = true;
            this.success = false;
            this.scatterData = [];
            this.message = '';
            this.$nextTick(() => this.destroyAllCharts());

            try {
                const res = await fetch("/api/scatters/generate", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        bucket: this.selectedBucket,
                        prefix: this.currentPrefix || ""
                    })
                });

                const json = await res.json();

                if (!res.ok || !json.success) {
                    this.message = json.message || "Lỗi từ server khi tạo scatter";
                    console.error("API scatter error:", json);
                    return;
                }

                this.success = true;
                this.message = json.message;
                this.resultType = json.type || 'frame';
                this.scatterData = json.scatter_data || [];

                // Debug: In ra dữ liệu mẫu từ backend
                if (this.scatterData.length > 0 && this.scatterData[0].data?.object_name?.length > 0) {
                    console.log("Sample object_name từ backend:", this.scatterData[0].data.object_name[0]);
                    console.log("Sample bucket từ backend:", this.scatterData[0].data.bucket?.[0] || "Không có bucket");
                    console.log("Current prefix frontend:", this.currentPrefix);
                }

                this.$nextTick(() => this.renderAllCharts());
            } catch (err) {
                console.error("Lỗi gọi API scatter:", err);
                this.message = "Lỗi kết nối hoặc xử lý dữ liệu";
            } finally {
                this.loading = false;
            }
        },

        renderAllCharts() {
            this.scatterData.forEach((info, idx) => {
                const canvasId = `scatterChart${idx}`;
                let canvas = document.getElementById(canvasId);
                if (!canvas) return;

                // Buộc reset tooltip cũ bằng cách clone và replace canvas
                const parent = canvas.parentNode;
                const newCanvas = canvas.cloneNode(true);
                parent.replaceChild(newCanvas, canvas);
                newCanvas.id = canvasId;  // giữ nguyên ID

                const ctx = newCanvas.getContext('2d');

                const pointData = info.data.x.map((x, i) => ({
                    x: x,
                    y: info.data.y[i],
                    frameIdx: info.data.frame_index?.[i] ?? i,
                    objectName: info.data.object_name?.[i] ?? null,
                    platform: info.data.platform?.[i] ?? 'unknown',
                    scene_type: info.data.scene_type?.[i] ?? 'day',
                    file_size: info.data.file_size?.[i] ?? 0,
                    created_at: info.data.created_at?.[i] ?? null,
                    video_id: info.data.video_id?.[i] ?? 'unknown',
                    bucket: info.data.bucket?.[i] ?? null
                }));

                const chart = new Chart(ctx, {
                    type: 'scatter',
                    data: {
                        datasets: [{
                            label: `${info.title} (${pointData.length} frames)`,
                            data: pointData,
                            backgroundColor: 'rgba(45, 212, 191, 0.7)',
                            borderColor: 'white',
                            pointBorderWidth: 1,
                            pointRadius: 5,
                            pointHoverRadius: 9,
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                display: true,
                                position: 'top',
                            },
                            tooltip: {
                                enabled: true,
                                backgroundColor: 'rgba(15, 23, 42, 0.95)',
                                titleFont: { size: 14, weight: 'bold' },
                                bodyFont: { size: 13 },
                                padding: 10,
                                cornerRadius: 6,
                                callbacks: {
                                    title: function (tooltipItems) {
                                        return tooltipItems[0].dataset.label || 'Chi tiết frame';
                                    },
                                    label: function (context) {
                                        const p = context.raw;
                                        const lines = [];

                                        // Thông tin chính
                                        lines.push(`Frame: ${p.frameIdx + 1}`);
                                        lines.push(`Giá trị Y: ${p.y.toFixed(2)}`);

                                        if (p.x !== undefined && !isNaN(p.x)) {
                                            lines.push(`Giá trị X: ${p.x.toFixed(2)}`);
                                        }

                                        // File & vị trí
                                        let fileName = 'unknown';
                                        if (p.objectName) {
                                            fileName = p.objectName.split('/').pop();
                                            lines.push(`File: ${fileName}`);
                                        }

                                        if (p.bucket && p.objectName) {
                                            const shortPath = p.objectName.split('/').slice(-2).join('/');
                                            lines.push(`Vị trí: ${p.bucket}/${shortPath}`);
                                        } else if (p.bucket) {
                                            lines.push(`Bucket: ${p.bucket}`);
                                        }

                                        // Metadata bổ sung
                                        if (p.platform && p.platform !== 'unknown') {
                                            lines.push(`Nguồn: ${p.platform}`);
                                        }
                                        if (p.scene_type && p.scene_type !== 'day') {
                                            lines.push(`Cảnh: ${p.scene_type}`);
                                        }
                                        if (p.video_id && p.video_id !== 'unknown') {
                                            lines.push(`Video ID: ${p.video_id}`);
                                        }
                                        if (p.file_size > 0) {
                                            lines.push(`Kích thước: ${(p.file_size / 1024 / 1024).toFixed(2)} MB`);
                                        }
                                        if (p.created_at) {
                                            const date = new Date(p.created_at);
                                            lines.push(`Ngày tạo: ${date.toLocaleString('vi-VN', {
                                                day: '2-digit', month: '2-digit', year: 'numeric',
                                                hour: '2-digit', minute: '2-digit'
                                            })}`);
                                        }

                                        return lines;
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                title: { display: true, text: info.x_label || 'Trục X' },
                                grid: { color: 'rgba(255,255,255,0.1)' }
                            },
                            y: {
                                title: { display: true, text: info.y_label || 'Trục Y' },
                                grid: { color: 'rgba(255,255,255,0.1)' }
                            }
                        },
                        onClick: (event, elements) => {
                            if (elements.length === 0) return;
                            const p = pointData[elements[0].index];

                            let key = p.objectName;
                            if (!key) {
                                key = `frame_${String(p.frameIdx).padStart(6, '0')}.png`;
                            }

                            const frameBucket = p.bucket || this.selectedBucket;

                            console.log("Click frame:", {
                                bucket: frameBucket,
                                key: key,
                                objectName: p.objectName,
                                frameIdx: p.frameIdx
                            });

                            let finalKey = key.replace(/\/{2,}/g, '/');

                            const imageUrl = `/api/image-proxy?bucket=${encodeURIComponent(frameBucket)}&key=${encodeURIComponent(finalKey)}`;

                            this.selectedScatterFrame = {
                                image_url: imageUrl,
                                video_name: finalKey.split('/').pop() || `Frame ${p.frameIdx + 1}`,
                                platform: p.platform,
                                scene_type: p.scene_type,
                                video_id: p.video_id || 'unknown',
                                frame_index: p.frameIdx + 1,
                                storage_bucket: frameBucket,
                                storage_key: finalKey,
                            };

                            this.selectedScatterFrameUrl = imageUrl;
                            this.frameLoading = true;
                            this.showScatterFrameModal = true;

                            const img = new Image();
                            img.onload = () => this.frameLoading = false;
                            img.onerror = () => {
                                this.frameLoading = false;
                                console.error("Load frame thất bại:", { bucket: frameBucket, key: finalKey });
                                alert(`Không tải được frame.\nBucket: ${frameBucket}\nKey: ${finalKey}`);
                            };
                            img.src = imageUrl;
                        },
                    }
                });

                this.charts[idx] = chart;
            });
        },

        resetChartZoom(index) {
            if (this.charts[index]) this.charts[index].resetZoom();
        },

        destroyAllCharts() {
            this.charts.forEach((chart, idx) => {
                if (chart) {
                    chart.destroy();
                }
                const canvas = document.getElementById(`scatterChart${idx}`);
                if (canvas) {
                    const ctx = canvas.getContext('2d');
                    if (ctx) {
                        ctx.clearRect(0, 0, canvas.width, canvas.height);
                    }
                }
            });
            this.charts = [];
        },

        closeScatterModal() {
            this.showScatterFrameModal = false;
            this.selectedScatterFrameUrl = null;
            this.selectedScatterFrame = null;
            this.frameLoading = false;
        }
    };
}