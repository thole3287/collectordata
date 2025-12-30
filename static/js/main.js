// Alpine.js data và functions
function app() {
    return {
        // State
        sidebarOpen: true,
        activeTab: 'download',
        urlInput: '',
        selectedKeywordId: '',
        activeKeywords: [],
        selectedKeyword: null,
        numVideos: 1,
        downloading: false,
        videos: [],
        videosTableBody: '',
        currentPage: 1,
        totalPages: 1,
        perPage: 20,
        searchQuery: '',
        stats: {},
        vizData: {},
        charts: {},
        keywords: [],
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
        // Pexels Dataset state
        pexelsQuery: 'traffic',
        pexelsNumVideos: 10,
        pexelsDownloading: false,
        pexelsExtracting: false,
        pexelsDownloadProgress: 0,
        pexelsExtractProgress: 0,
        newKeyword: {
            keyword: '',
            num_videos: 1,
            description: ''
        },
        addingKeyword: false,
        showNotification: false,
        notificationMessage: '',
        notificationType: 'success',

        // Methods
        async downloadByUrl() {
            if (!this.urlInput.trim()) {
                this.showNotify('Vui lòng nhập ít nhất một URL', 'error');
                return;
            }

            const urls = this.urlInput.trim().split('\n').filter(url => url.trim());
            if (urls.length === 0) {
                this.showNotify('Vui lòng nhập ít nhất một URL hợp lệ', 'error');
                return;
            }

            this.downloading = true;
            try {
                const response = await fetch('/api/download/url', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ urls: urls }),
                });

                const data = await response.json();
                if (response.ok) {
                    this.showNotify(data.message || 'Đã bắt đầu tải video', 'success');
                    this.urlInput = '';
                    // Tự động refresh danh sách sau 5 giây
                    setTimeout(() => {
                        if (this.activeTab === 'videos') {
                            this.loadVideos();
                        }
                    }, 5000);
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
            if (!this.selectedKeywordId) {
                this.showNotify('Vui lòng chọn keyword từ danh sách', 'error');
                return;
            }

            const selectedKw = this.activeKeywords.find(kw => kw.id == this.selectedKeywordId);
            if (!selectedKw) {
                this.showNotify('Keyword không tồn tại', 'error');
                return;
            }

            const keyword = selectedKw.keyword;
            const numVideos = parseInt(this.numVideos) || selectedKw.num_videos || 1;

            this.downloading = true;
            try {
                const response = await fetch('/api/download/keyword', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        keyword: keyword,
                        num_videos: numVideos,
                    }),
                });

                const data = await response.json();
                if (response.ok) {
                    this.showNotify(data.message || 'Đã bắt đầu tải video', 'success');
                    this.selectedKeywordId = '';
                    this.selectedKeyword = null;
                    this.numVideos = 1;
                    // Tự động refresh danh sách sau 5 giây
                    setTimeout(() => {
                        if (this.activeTab === 'videos') {
                            this.loadVideos();
                        }
                        if (this.activeTab === 'keywords') {
                            this.loadKeywords();
                        }
                        this.loadActiveKeywords();
                    }, 5000);
                } else {
                    this.showNotify(data.error || 'Có lỗi xảy ra', 'error');
                }
            } catch (error) {
                this.showNotify('Lỗi kết nối: ' + error.message, 'error');
            } finally {
                this.downloading = false;
            }
        },

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
                const duration = video.duration ? this.formatDuration(video.duration) : 'N/A';
                const resolution = video.resolution || 'N/A';
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

        async loadStats() {
            try {
                const response = await fetch('/api/stats');
                const data = await response.json();

                if (response.ok) {
                    this.stats = data;
                } else {
                    this.showNotify(data.error || 'Lỗi khi tải thống kê', 'error');
                }
            } catch (error) {
                this.showNotify('Lỗi kết nối: ' + error.message, 'error');
            }
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
                    this.renderKeywordsTable();
                } else {
                    this.showNotify(data.error || 'Lỗi khi tải danh sách keywords', 'error');
                }
            } catch (error) {
                this.showNotify('Lỗi kết nối: ' + error.message, 'error');
            }
        },

        renderKeywordsTable() {
            console.log('Rendering keywords table, count:', this.keywords.length); // Debug
            if (this.keywords.length === 0) {
                this.keywordsTableBody = `
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

            this.keywordsTableBody = this.keywords.map(kw => {
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
                            ${kw.id}
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
                                    data-keyword-id="${kw.id}"
                                    data-action="download"
                                    class="keyword-action-btn text-blue-600 hover:text-blue-800 disabled:text-gray-400 disabled:cursor-not-allowed"
                                    ${kw.status === 'processing' ? 'disabled' : ''}
                                    title="Tải video"
                                >
                                    <i class="fas fa-download"></i>
                                </button>
                                <button 
                                    data-keyword-id="${kw.id}"
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
                } else {
                    this.activeKeywords = [];
                }
            } catch (error) {
                console.error('Lỗi khi tải keywords:', error);
                this.activeKeywords = [];
            }
        },

        onKeywordSelect() {
            if (this.selectedKeywordId) {
                const selectedKw = this.activeKeywords.find(kw => kw.id == this.selectedKeywordId);
                if (selectedKw) {
                    this.selectedKeyword = selectedKw;
                    this.numVideos = selectedKw.num_videos || 1;
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
                            this.renderCharts();
                            this.renderWordCloud();
                            this.renderVisualizationKeywordsTable();
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
            // Destroy existing charts
            if (this.charts) {
                Object.values(this.charts).forEach(chart => {
                    if (chart && typeof chart.destroy === 'function') chart.destroy();
                });
            }
            this.charts = {};

            // Platform Chart
            if (this.vizData.by_platform && this.vizData.by_platform.length > 0) {
                const ctx = document.getElementById('platformChart');
                if (ctx) {
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
                }
            }

            // Method Chart
            if (this.vizData.by_method && this.vizData.by_method.length > 0) {
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

            // Resolution Chart
            if (this.vizData.by_resolution && this.vizData.by_resolution.length > 0) {
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
            if (!canvas || typeof Chart === 'undefined') return;

            // Destroy existing chart if any
            if (this.charts.wordcloud) {
                this.charts.wordcloud.destroy();
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
                color: function() {
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
                hover: function(item, dimension, event) {
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

        async downloadPexelsVideos() {
            if (!this.pexelsQuery.trim()) {
                this.showNotify('Vui lòng nhập từ khóa tìm kiếm', 'error');
                return;
            }

            if (this.pexelsNumVideos < 1 || this.pexelsNumVideos > 80) {
                this.showNotify('Số lượng video phải từ 1 đến 80', 'error');
                return;
            }

            this.pexelsDownloading = true;
            this.pexelsDownloadProgress = 0;
            
            // Poll progress từ server
            const progressInterval = setInterval(async () => {
                try {
                    const response = await fetch('/api/pexels/progress');
                    const progressData = await response.json();
                    if (progressData.progress !== undefined) {
                        this.pexelsDownloadProgress = Math.min(progressData.progress, 95);
                    }
                } catch (e) {
                    // Ignore errors
                }
            }, 1000);
            
            try {
                const response = await fetch('/api/pexels/download', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        query: this.pexelsQuery.trim(),
                        num_videos: this.pexelsNumVideos
                    }),
                });

                const data = await response.json();
                if (response.ok) {
                    this.showNotify(data.message || 'Đã bắt đầu tải video từ Pexels', 'success');
                    
                    // Poll để check kết quả sau khi tải xong
                    this.checkPexelsDownloadResult(progressInterval);
                } else {
                    clearInterval(progressInterval);
                    this.pexelsDownloadProgress = 0;
                    this.showNotify(data.message || 'Có lỗi xảy ra', 'error');
                    this.pexelsDownloading = false;
                }
            } catch (error) {
                clearInterval(progressInterval);
                this.pexelsDownloadProgress = 0;
                this.showNotify('Lỗi kết nối: ' + error.message, 'error');
                this.pexelsDownloading = false;
            }
        },

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


