// Alpine.js data và functions
function app() {
    return {
        // State
        sidebarOpen: true,
        activeTab: 'visualization',
        urlInput: '',
        urlDownloadPlatform: 'youtube', // New
        keywordDownloadPlatform: 'youtube', // New
        selectedKeywordId: '',
        activeKeywords: [],
        selectedKeyword: null,
        numVideos: 1,
        downloading: false,
        videos: [],
        // ... (omitting lines for brevity, target replace will handle)

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
                        platform: this.urlDownloadPlatform
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
        galleryPage: 1,
        galleryPerPage: 10, // Groups per page
        galleryTotalPages: 0,
        galleryTotalFrames: 0,
        galleryLoading: false,
        showGalleryModal: false,
        selectedGalleryFrame: null,

        // Gallery Dashboard State
        galleryStats: {},
        galleryFilterPlatform: 'all',
        gallerySearchQuery: '',
        galleryCharts: {},

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
                    // Delay to ensure DOM is visible/layout computed
                    setTimeout(() => {
                        this.renderCharts();
                    }, 100);
                }
            } catch (error) {
                console.error("Failed to load stats", error);
            }
        },

        renderCharts() {
            console.log("Rendering Gallery Charts...");
            try {
                // 1. Trend Chart
                const trendEl = document.getElementById('galleryTrendChart');
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
            } catch (e) {
                console.error("Error rendering charts:", e);
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
                    per_page: this.galleryPerPage
                });

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
                    await this.loadGroupFrames(group.video_id);
                }
            }
        },

        async loadGroupFrames(videoId) {
            try {
                // Fetch up to 100 frames for preview in the group
                const response = await fetch(`/api/frames?video_id=${videoId}&per_page=100`);
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
        },

        // Missing state variables fixed
        editKeywordForm: {
            keyword: '',
            num_videos: 1,
            description: ''
        },
        updatingKeyword: false,



        init() {
            console.log('App initialized');
            // Load initial data based on active tab
            if (this.activeTab === 'visualization') {
                this.loadVisualization();
            }
            // Always load active keywords for dropdowns
            this.loadActiveKeywords();
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
                        <td colspan="4" class="px-6 py-4 text-center text-gray-500">
                            Chưa có dữ liệu. Vui lòng tải video trước!
                        </td>
                    </tr>
                `;
                return;
            }

            const total = this.vizData.by_keyword.reduce((sum, kw) => sum + kw.count, 0);
            this.keywordsTableBody = this.vizData.by_keyword.map((kw, index) => {
                const percentage = total > 0 ? ((kw.count / total) * 100).toFixed(2) : 0;
                return `
                    <tr class="hover:bg-gray-50">
                        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${index + 1}</td>
                        <td class="px-6 py-4 text-sm text-gray-900">${kw.keyword}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${kw.count}</td>
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
                    platforms: kw.platforms || []
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
                        const keywordData = keywordMap[keyword] || { count: 0, platforms: [] };
                        const count = keywordData.count;
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
                            ${platformText}
                        `;
                        tooltip.style.left = (event.pageX + 15) + 'px';
                        tooltip.style.top = (event.pageY - 50) + 'px';
                        canvas.style.cursor = 'pointer';
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
                        <td colspan="4" class="px-6 py-4 text-center text-gray-500">Chưa có dữ liệu</td>
                    </tr>
                `;
                return;
            }

            const total = this.vizData.by_keyword.reduce((sum, kw) => sum + kw.count, 0);
            this.vizKeywordsTableBody = this.vizData.by_keyword.map((kw, index) => {
                const percentage = total > 0 ? ((kw.count / total) * 100).toFixed(2) : 0;
                return `
                    <tr class="hover:bg-gray-50">
                        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${index + 1}</td>
                        <td class="px-6 py-4 text-sm text-gray-900">${kw.keyword}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${kw.count}</td>
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


