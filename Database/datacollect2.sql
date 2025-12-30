-- --------------------------------------------------------
-- Host:                         127.0.0.1
-- Server version:               8.0.30 - MySQL Community Server - GPL
-- Server OS:                    Win64
-- HeidiSQL Version:             12.1.0.6537
-- --------------------------------------------------------

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET NAMES utf8 */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;


-- Dumping database structure for data_collection
CREATE DATABASE IF NOT EXISTS `data_collection` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;
USE `data_collection`;

-- Dumping structure for table data_collection.downloaded_videos
CREATE TABLE IF NOT EXISTS `downloaded_videos` (
  `id` int NOT NULL AUTO_INCREMENT,
  `video_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'ID video từ YouTube',
  `title` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Tiêu đề video',
  `url` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'URL video',
  `file_path` varchar(1000) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Đường dẫn file đã tải về',
  `duration` int DEFAULT NULL COMMENT 'Độ dài video (giây)',
  `fps` int DEFAULT NULL COMMENT 'Frames per second',
  `width` int DEFAULT NULL COMMENT 'Chiều rộng video (pixel)',
  `height` int DEFAULT NULL COMMENT 'Chiều cao video (pixel)',
  `resolution` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Độ phân giải (vd: 1920x1080)',
  `platform` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT 'youtube' COMMENT 'Nền tảng (youtube, vimeo, etc)',
  `keyword` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Từ khóa tìm kiếm (NULL nếu tải bằng URL)',
  `download_method` enum('keyword','url','pexels') COLLATE utf8mb4_unicode_ci NOT NULL,
  `downloaded_at` datetime NOT NULL COMMENT 'Thời gian tải về',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Thời gian tạo record',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Thời gian cập nhật',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_video_id` (`video_id`),
  KEY `idx_video_id` (`video_id`),
  KEY `idx_keyword` (`keyword`),
  KEY `idx_downloaded_at` (`downloaded_at`),
  KEY `idx_download_method` (`download_method`)
) ENGINE=InnoDB AUTO_INCREMENT=43 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Bảng lưu thông tin video đã tải về';

-- Dumping data for table data_collection.downloaded_videos: ~30 rows (approximately)
INSERT INTO `downloaded_videos` (`id`, `video_id`, `title`, `url`, `file_path`, `duration`, `fps`, `width`, `height`, `resolution`, `platform`, `keyword`, `download_method`, `downloaded_at`, `created_at`, `updated_at`) VALUES
	(13, 'V8paX22Sgzg', 'Crazy rush hour traffic in Saigon - Ho Chi Minh City, Vietnam', 'https://www.youtube.com/watch?v=V8paX22Sgzg', 'C:\\laragon\\www\\DMAI\\downloads\\Crazy rush hour traffic in Saigon - Ho Chi Minh City, Vietnam.webm', 36, 30, 1920, 1080, '1920x1080', 'youtube', 'saigon traffic', 'keyword', '2025-12-25 16:19:30', '2025-12-25 09:19:29', '2025-12-25 09:19:29'),
	(14, '1ZupwFOhjl4', 'Rush Hour Traffic with motorcycle in Ho Chi Minh city - Vietnam', 'https://www.youtube.com/watch?v=1ZupwFOhjl4', 'C:\\laragon\\www\\DMAI\\downloads\\Rush Hour Traffic with motorcycle in Ho Chi Minh city - Vietnam.mp4', 152, 30, 1920, 1080, '1920x1080', 'youtube', 'saigon traffic', 'keyword', '2025-12-25 16:19:35', '2025-12-25 09:19:35', '2025-12-25 09:19:35'),
	(15, 'fm0cX7P6PSw', 'Crazy yet Organized Traffic in Vietnam Ho Chi Minh', 'https://www.youtube.com/watch?v=fm0cX7P6PSw', 'C:\\laragon\\www\\DMAI\\downloads\\Crazy yet Organized Traffic in Vietnam Ho Chi Minh.webm', 137, 30, 1920, 1080, '1920x1080', 'youtube', 'saigon traffic', 'keyword', '2025-12-25 16:19:40', '2025-12-25 09:19:40', '2025-12-25 09:19:40'),
	(16, 'gKLWZjBu2iQ', 'Crazy Saigon Traffic', 'https://www.youtube.com/watch?v=gKLWZjBu2iQ', 'C:\\laragon\\www\\DMAI\\downloads\\Crazy Saigon Traffic.mp4', 467, 30, 640, 480, '640x480', 'youtube', 'saigon traffic', 'keyword', '2025-12-25 16:19:45', '2025-12-25 09:19:45', '2025-12-25 09:19:45'),
	(17, 'v-T4KeJkrYc', 'Saigon Traffic', 'https://www.youtube.com/watch?v=v-T4KeJkrYc', 'C:\\laragon\\www\\DMAI\\downloads\\Saigon Traffic.mp4', 231, 60, 1280, 720, '1280x720', 'youtube', 'saigon traffic', 'keyword', '2025-12-25 16:20:00', '2025-12-25 09:20:00', '2025-12-25 09:20:00'),
	(18, 'AbQEdblUIF0', 'Driving in HCMC Vietnam 4K. First person view', 'https://www.youtube.com/watch?v=AbQEdblUIF0', 'C:\\laragon\\www\\DMAI\\downloads\\Driving in HCMC Vietnam 4K. First person view.webm', 1864, 60, 1920, 1080, '1920x1080', 'youtube', 'saigon traffic', 'keyword', '2025-12-25 16:20:58', '2025-12-25 09:20:58', '2025-12-25 09:20:58'),
	(19, 'wqPSsu7XQ74', 'How to cross a street in Ho Chi Minh City (Saigon), Vietnam', 'https://www.youtube.com/watch?v=wqPSsu7XQ74', 'C:\\laragon\\www\\DMAI\\downloads\\How to cross a street in Ho Chi Minh City (Saigon), Vietnam.webm', 40, 30, 1280, 720, '1280x720', 'youtube', 'saigon traffic', 'keyword', '2025-12-25 16:21:01', '2025-12-25 09:21:00', '2025-12-25 09:21:00'),
	(20, 'LSQXJROfkdc', 'How to cross the road in Saigon Vietnam Traffic', 'https://www.youtube.com/watch?v=LSQXJROfkdc', 'C:\\laragon\\www\\DMAI\\downloads\\How to cross the road in Saigon Vietnam Traffic.webm', 115, 30, 1920, 1080, '1920x1080', 'youtube', 'saigon traffic', 'keyword', '2025-12-25 16:21:22', '2025-12-25 09:21:21', '2025-12-25 09:21:21'),
	(21, 'gEi6dK-wY8Y', 'UNEXPECTED TRAFFIC IN SAIGON | SAIGON CRAZY TRAFFIC 2025', 'https://www.youtube.com/watch?v=gEi6dK-wY8Y', 'C:\\laragon\\www\\DMAI\\downloads\\UNEXPECTED TRAFFIC IN SAIGON ｜ SAIGON CRAZY TRAFFIC 2025.mp4', 2490, 60, 1920, 1080, '1920x1080', 'youtube', 'saigon traffic', 'keyword', '2025-12-25 16:23:55', '2025-12-25 09:23:55', '2025-12-25 09:23:55'),
	(22, 'Xf2FAT9D4BE', 'Insane rush hour traffic in Saigon/Ho Chi Minh City, Vietnam 🇻🇳🇻🇳🇻🇳', 'https://www.youtube.com/watch?v=Xf2FAT9D4BE', 'C:\\laragon\\www\\DMAI\\downloads\\Insane rush hour traffic in Saigon⧸Ho Chi Minh City, Vietnam 🇻🇳🇻🇳🇻🇳.webm', 2050, 60, 1920, 1080, '1920x1080', 'youtube', 'saigon traffic', 'keyword', '2025-12-25 16:28:35', '2025-12-25 09:28:35', '2025-12-25 09:28:35'),
	(23, 'mtAXQqN2NAY', 'Hanoi morning traffic - October 10 2015', 'https://www.youtube.com/watch?v=mtAXQqN2NAY', 'C:\\laragon\\www\\DMAI\\downloads\\Hanoi morning traffic - October 10 2015.webm', 20, 30, 1920, 1080, '1920x1080', 'youtube', 'hanoi traffict', 'keyword', '2025-12-25 16:38:23', '2025-12-25 09:38:22', '2025-12-25 09:38:22'),
	(24, 'oetF3UTIwbc', 'Traffic in Hanoi during \'rush hour\'', 'https://www.youtube.com/watch?v=oetF3UTIwbc', 'C:\\laragon\\www\\DMAI\\downloads\\Traffic in Hanoi during \'rush hour\'.mp4', 33, 30, 640, 480, '640x480', 'youtube', 'hanoi traffict', 'keyword', '2025-12-25 16:38:25', '2025-12-25 09:38:24', '2025-12-25 09:38:24'),
	(25, 'UzKw4O9qOZo', 'Vietnam raw street traffic capture – Morning Rush Hour Traffic in Hanoi, Vietnam', 'https://www.youtube.com/watch?v=UzKw4O9qOZo', 'C:\\laragon\\www\\DMAI\\downloads\\Vietnam raw street traffic capture – Morning Rush Hour Traffic in Hanoi, Vietnam.mp4', 205, 60, 1920, 1080, '1920x1080', 'youtube', 'hanoi traffict', 'keyword', '2025-12-25 16:38:36', '2025-12-25 09:38:35', '2025-12-25 09:38:35'),
	(26, 'Gf8_lzCWvq4', 'Crazy Hanoi Traffic', 'https://www.youtube.com/watch?v=Gf8_lzCWvq4', 'C:\\laragon\\www\\DMAI\\downloads\\Crazy Hanoi Traffic.mp4', 145, 25, 1280, 720, '1280x720', 'youtube', 'hanoi traffict', 'keyword', '2025-12-25 16:38:40', '2025-12-25 09:38:39', '2025-12-25 09:38:39'),
	(27, 'IiCeMrY5lKA', 'Vietnam Hanoi crazy traffic driving (part 2)', 'https://www.youtube.com/watch?v=IiCeMrY5lKA', 'C:\\laragon\\www\\DMAI\\downloads\\Vietnam Hanoi crazy traffic driving (part 2).webm', 185, 30, 1920, 1080, '1920x1080', 'youtube', 'hanoi traffict', 'keyword', '2025-12-25 16:38:49', '2025-12-25 09:38:48', '2025-12-25 09:38:48'),
	(28, 'MNn9qKG2UFI', '4K Road traffic video for object detection and tracking - free download now!', 'https://www.youtube.com/watch?v=MNn9qKG2UFI', 'C:\\laragon\\www\\DMAI\\downloads\\4K Road traffic video for object detection and tracking - free download now!.webm', 306, 30, 1920, 1080, '1920x1080', 'youtube', 'Road traffict video', 'keyword', '2025-12-25 16:51:21', '2025-12-25 09:51:21', '2025-12-25 09:51:21'),
	(29, 'e_WBuBqS9h8', '30 Minutes of Cars Driving By in 2009', 'https://www.youtube.com/watch?v=e_WBuBqS9h8', 'C:\\laragon\\www\\DMAI\\downloads\\30 Minutes of Cars Driving By in 2009.mp4', 1793, 30, 1280, 720, '1280x720', 'youtube', 'Road traffict video', 'keyword', '2025-12-25 16:51:37', '2025-12-25 09:51:37', '2025-12-25 09:51:37'),
	(30, 'wqctLW0Hb_0', 'Road traffic video for object recognition', 'https://www.youtube.com/watch?v=wqctLW0Hb_0', 'C:\\laragon\\www\\DMAI\\downloads\\Road traffic video for object recognition.webm', 2048, 25, 1280, 720, '1280x720', 'youtube', 'Road traffict video', 'keyword', '2025-12-25 16:51:49', '2025-12-25 09:51:49', '2025-12-25 09:51:49'),
	(31, '6o5VNoVwW7I', 'SiMTraM - Simulation of Mixed Traffic Mobility official Video', 'https://www.youtube.com/watch?v=6o5VNoVwW7I', 'C:\\laragon\\www\\DMAI\\downloads\\SiMTraM - Simulation of Mixed Traffic Mobility official Video.mp4', 135, 29, 1920, 1080, '1920x1080', 'youtube', 'Mixed traffic flow video dataset', 'keyword', '2025-12-25 17:00:33', '2025-12-25 10:00:32', '2025-12-25 10:00:32'),
	(32, 'JqhdBCCUVyQ', 'Vehicle Dataset Sample 2', 'https://www.youtube.com/watch?v=JqhdBCCUVyQ', 'C:\\laragon\\www\\DMAI\\downloads\\Vehicle Dataset Sample 2.mp4', 10, 30, 1920, 1080, '1920x1080', 'youtube', NULL, 'url', '2025-12-25 17:03:22', '2025-12-25 10:03:22', '2025-12-25 10:03:22'),
	(33, '2103099', 'Mike Bird - 2103099', 'https://www.pexels.com/video/traffic-flow-in-the-highway-2103099/', 'C:\\laragon\\www\\DMAI\\pexels_traffic_dataset\\pexels_traffic_2103099.mp4', 60, 60, 1280, 720, '1280x720', 'pexels', 'traffic', 'pexels', '2025-12-30 15:10:58', '2025-12-30 08:10:58', '2025-12-30 08:10:58'),
	(34, '1472014', 'Tom Fisk - 1472014', 'https://www.pexels.com/video/aerial-view-of-a-busy-freeway-1472014/', 'C:\\laragon\\www\\DMAI\\pexels_traffic_dataset\\pexels_traffic_1472014.mp4', 32, 30, 1280, 720, '1280x720', 'pexels', 'traffic', 'pexels', '2025-12-30 15:11:01', '2025-12-30 08:11:00', '2025-12-30 08:11:00'),
	(35, '853828', 'Coverr - 853828', 'https://www.pexels.com/video/blurred-video-of-cars-stuck-in-traffic-853828/', 'C:\\laragon\\www\\DMAI\\pexels_traffic_dataset\\pexels_traffic_853828.mp4', 16, 25, 1280, 720, '1280x720', 'pexels', 'traffic', 'pexels', '2025-12-30 15:11:03', '2025-12-30 08:11:02', '2025-12-30 08:11:02'),
	(36, '3121459', 'Taryn Elliott - 3121459', 'https://www.pexels.com/video/traffic-on-an-intersection-road-in-a-city-3121459/', 'C:\\laragon\\www\\DMAI\\pexels_traffic_dataset\\pexels_traffic_3121459.mp4', 37, 24, 1280, 720, '1280x720', 'pexels', 'traffic', 'pexels', '2025-12-30 15:11:05', '2025-12-30 08:11:04', '2025-12-30 08:11:04'),
	(37, '1860079', 'Alexander Lutkov - 1860079', 'https://www.pexels.com/video/time-lapse-video-of-traffic-1860079/', 'C:\\laragon\\www\\DMAI\\pexels_traffic_dataset\\pexels_traffic_1860079.mp4', 6, 25, 1280, 720, '1280x720', 'pexels', 'traffic', 'pexels', '2025-12-30 15:11:07', '2025-12-30 08:11:06', '2025-12-30 08:11:06'),
	(38, '2109463', 'Mike Bird - 2109463', 'https://www.pexels.com/video/time-lapse-of-cars-2109463/', 'C:\\laragon\\www\\DMAI\\pexels_traffic_dataset\\pexels_traffic_2109463.mp4', 20, 60, 1280, 720, '1280x720', 'pexels', 'traffic', 'pexels', '2025-12-30 15:11:09', '2025-12-30 08:11:08', '2025-12-30 08:11:08'),
	(39, '2099536', 'Nino Souza - 2099536', 'https://www.pexels.com/video/nightlife-in-the-city-2099536/', 'C:\\laragon\\www\\DMAI\\pexels_traffic_dataset\\pexels_traffic_2099536.mp4', 20, 60, 1280, 720, '1280x720', 'pexels', 'traffic', 'pexels', '2025-12-30 15:11:11', '2025-12-30 08:11:10', '2025-12-30 08:11:10'),
	(40, '857267', 'Kelly Lacy - 857267', 'https://www.pexels.com/video/time-lapse-of-busy-street-857267/', 'C:\\laragon\\www\\DMAI\\pexels_traffic_dataset\\pexels_traffic_857267.mp4', 8, 24, 1280, 720, '1280x720', 'pexels', 'traffic', 'pexels', '2025-12-30 15:11:12', '2025-12-30 08:11:12', '2025-12-30 08:11:12'),
	(41, '2053855', 'Tom Fisk - 2053855', 'https://www.pexels.com/video/aerial-view-of-vehicles-travelling-at-night-2053855/', 'C:\\laragon\\www\\DMAI\\pexels_traffic_dataset\\pexels_traffic_2053855.mp4', 41, 30, 1280, 720, '1280x720', 'pexels', 'traffic', 'pexels', '2025-12-30 15:11:15', '2025-12-30 08:11:14', '2025-12-30 08:11:14'),
	(42, '2697636', '葉崧民 - 2697636', 'https://www.pexels.com/video/time-lapse-footage-of-vehicular-and-people-traffic-in-a-city-street-at-daytime-2697636/', 'C:\\laragon\\www\\DMAI\\pexels_traffic_dataset\\pexels_traffic_2697636.mp4', 7, 30, 1440, 1080, '1440x1080', 'pexels', 'traffic', 'pexels', '2025-12-30 15:11:16', '2025-12-30 08:11:16', '2025-12-30 08:11:16');

-- Dumping structure for table data_collection.keywords
CREATE TABLE IF NOT EXISTS `keywords` (
  `id` int NOT NULL AUTO_INCREMENT,
  `keyword` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Từ khóa tìm kiếm',
  `num_videos` int DEFAULT '1' COMMENT 'Số lượng video muốn tải cho từ khóa này',
  `status` enum('pending','processing','completed','failed') COLLATE utf8mb4_unicode_ci DEFAULT 'pending' COMMENT 'Trạng thái xử lý',
  `total_downloaded` int DEFAULT '0' COMMENT 'Tổng số video đã tải thành công',
  `last_downloaded_at` datetime DEFAULT NULL COMMENT 'Thời gian tải lần cuối',
  `description` text COLLATE utf8mb4_unicode_ci COMMENT 'Mô tả về từ khóa này',
  `is_active` tinyint(1) DEFAULT '1' COMMENT 'Từ khóa có đang active không',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Thời gian tạo',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Thời gian cập nhật',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_keyword` (`keyword`),
  KEY `idx_keyword` (`keyword`),
  KEY `idx_status` (`status`),
  KEY `idx_is_active` (`is_active`),
  KEY `idx_last_downloaded_at` (`last_downloaded_at`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Bảng quản lý từ khóa tìm kiếm';

-- Dumping data for table data_collection.keywords: ~4 rows (approximately)
INSERT INTO `keywords` (`id`, `keyword`, `num_videos`, `status`, `total_downloaded`, `last_downloaded_at`, `description`, `is_active`, `created_at`, `updated_at`) VALUES
	(1, 'Road traffict video', 1, 'pending', 0, NULL, '', 1, '2025-12-25 07:07:21', '2025-12-25 07:42:01'),
	(2, 'saigon traffic', 1, 'pending', 0, NULL, '', 1, '2025-12-25 07:07:53', '2025-12-25 07:42:02'),
	(3, 'hanoi traffict', 1, 'pending', 0, NULL, '', 1, '2025-12-25 08:04:22', '2025-12-25 08:04:22'),
	(4, 'Mixed traffic flow video dataset', 1, 'pending', 0, NULL, '', 1, '2025-12-25 10:00:03', '2025-12-25 10:00:03');

/*!40103 SET TIME_ZONE=IFNULL(@OLD_TIME_ZONE, 'system') */;
/*!40101 SET SQL_MODE=IFNULL(@OLD_SQL_MODE, '') */;
/*!40014 SET FOREIGN_KEY_CHECKS=IFNULL(@OLD_FOREIGN_KEY_CHECKS, 1) */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40111 SET SQL_NOTES=IFNULL(@OLD_SQL_NOTES, 1) */;
