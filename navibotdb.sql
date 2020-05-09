CREATE DATABASE IF NOT EXISTS navibotdb;
USE navibotdb;

-- CORE: Settings per guild based on a key, value approach 
-- Example: 
-- gui_id       gst_key             gst_value         gst_value_type
-- 999999999    allow_nsfw          no                1
CREATE TABLE guild_settings (
    gui_id BIGINT UNSIGNED NOT NULL,
    gst_key VARCHAR(64) NOT NULL,
    gst_value VARCHAR(1024) NOT NULL,
    gst_value_type TINYINT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (gui_id, gst_key)
);
