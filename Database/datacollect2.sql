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
