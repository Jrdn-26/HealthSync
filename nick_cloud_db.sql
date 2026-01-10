-- Database: nick_cloud_db
-- Pour XAMPP MySQL

CREATE DATABASE IF NOT EXISTS `nick_cloud_db` 
DEFAULT CHARACTER SET utf8mb4 
COLLATE utf8mb4_general_ci;

USE `nick_cloud_db`;

-- Table: confirmation_codes
CREATE TABLE IF NOT EXISTS `confirmation_codes` (
  `email` varchar(100) NOT NULL,
  `code` varchar(6) NOT NULL,
  `data_json` text NOT NULL,
  `expires_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`email`),
  KEY `expires_at` (`expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table: virtual_machines
CREATE TABLE IF NOT EXISTS `virtual_machines` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `vm_name` varchar(100) NOT NULL,
  `email` varchar(100) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `storage_mb` int(11) NOT NULL DEFAULT 500,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `last_login` timestamp NULL DEFAULT NULL,
  `status` enum('active','suspended') DEFAULT 'active',
  PRIMARY KEY (`id`),
  UNIQUE KEY `vm_name` (`vm_name`),
  UNIQUE KEY `email` (`email`),
  KEY `status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table: vm_files (optionnel)
CREATE TABLE IF NOT EXISTS `vm_files` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `vm_name` varchar(100) NOT NULL,
  `filename` varchar(255) NOT NULL,
  `file_path` varchar(500) NOT NULL,
  `size_bytes` bigint(20) NOT NULL,
  `uploaded_at` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_vm_name` (`vm_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;