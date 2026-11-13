CREATE DATABASE IF NOT EXISTS campus_lost_found;
USE campus_lost_found;

'CREATE TABLE `items` (
  `id` int NOT NULL AUTO_INCREMENT,
  `item_name` varchar(100) NOT NULL,
  `description` varchar(255) DEFAULT NULL,
  `category` varchar(50) DEFAULT NULL,
  `location` varchar(100) DEFAULT NULL,
  `date_found` date DEFAULT NULL,
  `status` varchar(20) DEFAULT 'Lost',
  `owner_name` varchar(100) DEFAULT NULL,
  `contact` varchar(20) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=131 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci';

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS verifications (
    item_id INT PRIMARY KEY,
    question VARCHAR(150) NOT NULL,
    answer VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
    id INT AUTO_INCREMENT PRIMARY KEY,
    item_id INT NOT NULL,
    username VARCHAR(50) NOT NULL,
    claimant_name VARCHAR(100) NOT NULL,
    contact VARCHAR(100) NOT NULL,
    answer VARCHAR(200) NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'Pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);