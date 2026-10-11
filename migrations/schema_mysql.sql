-- NativeFrames Production MySQL 8.0+ Schema

CREATE TABLE admins (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	username VARCHAR(120) NOT NULL, 
	password_hash VARCHAR(256) NOT NULL, 
	display_name VARCHAR(150), 
	created_at DATETIME NOT NULL, 
	last_login_at DATETIME, 
	PRIMARY KEY (id)
);

CREATE TABLE app_settings (
	`key` VARCHAR(80) NOT NULL, 
	value TEXT, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (`key`)
);

CREATE TABLE folders (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(200) NOT NULL, 
	description TEXT, 
	parent_id INTEGER, 
	visibility_status VARCHAR(20) NOT NULL, 
	sort_order INTEGER NOT NULL, 
	cover_image VARCHAR(500), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(parent_id) REFERENCES folders (id) ON DELETE SET NULL
);

CREATE TABLE viewer_sessions (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	display_name VARCHAR(150) NOT NULL, 
	normalized_name VARCHAR(150) NOT NULL, 
	session_token VARCHAR(128) NOT NULL, 
	created_at DATETIME NOT NULL, 
	last_activity_at DATETIME, 
	ended_at DATETIME, 
	session_status VARCHAR(20) NOT NULL, 
	ip_address VARCHAR(80), 
	user_agent VARCHAR(300), 
	PRIMARY KEY (id)
);

CREATE TABLE admin_audit_logs (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	admin_id INTEGER, 
	action VARCHAR(80) NOT NULL, 
	entity_type VARCHAR(50), 
	entity_id INTEGER, 
	details TEXT, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(admin_id) REFERENCES admins (id) ON DELETE SET NULL
);

CREATE TABLE media (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	title VARCHAR(300) NOT NULL, 
	description TEXT, 
	caption TEXT, 
	tags VARCHAR(500), 
	media_type VARCHAR(20) NOT NULL, 
	stored_filename VARCHAR(400), 
	storage_path VARCHAR(500), 
	thumbnail_path VARCHAR(500), 
	folder_id INTEGER, 
	status VARCHAR(20) NOT NULL, 
	is_featured BOOL NOT NULL, 
	mime_type VARCHAR(100), 
	file_size BIGINT, 
	duration_seconds FLOAT, 
	artist VARCHAR(200), 
	view_count INTEGER NOT NULL, 
	like_count INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	published_at DATETIME, 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(folder_id) REFERENCES folders (id) ON DELETE SET NULL
);

CREATE TABLE media_events (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	viewer_session_id INTEGER, 
	media_id INTEGER, 
	folder_id INTEGER, 
	event_type VARCHAR(50) NOT NULL, 
	event_timestamp DATETIME NOT NULL, 
	event_metadata TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(viewer_session_id) REFERENCES viewer_sessions (id) ON DELETE CASCADE, 
	FOREIGN KEY(media_id) REFERENCES media (id) ON DELETE SET NULL, 
	FOREIGN KEY(folder_id) REFERENCES folders (id) ON DELETE SET NULL
);

CREATE TABLE media_favourites (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	viewer_session_id INTEGER NOT NULL, 
	media_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_fav_session_media UNIQUE (viewer_session_id, media_id), 
	FOREIGN KEY(viewer_session_id) REFERENCES viewer_sessions (id) ON DELETE CASCADE, 
	FOREIGN KEY(media_id) REFERENCES media (id) ON DELETE CASCADE
);

CREATE TABLE media_likes (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	viewer_session_id INTEGER NOT NULL, 
	media_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_like_session_media UNIQUE (viewer_session_id, media_id), 
	FOREIGN KEY(viewer_session_id) REFERENCES viewer_sessions (id) ON DELETE CASCADE, 
	FOREIGN KEY(media_id) REFERENCES media (id) ON DELETE CASCADE
);
