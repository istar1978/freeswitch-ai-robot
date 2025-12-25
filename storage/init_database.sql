-- FreeSWITCH AI Robot Database Schema
-- Generated on 2025-12-24

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- System configurations table
CREATE TABLE IF NOT EXISTS system_configs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    key VARCHAR(100) UNIQUE NOT NULL,
    value JSON NOT NULL,
    description VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Call records table
CREATE TABLE IF NOT EXISTS call_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    caller_number VARCHAR(50),
    start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    end_time DATETIME,
    duration INT,
    conversation_log TEXT,
    status VARCHAR(20) DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Scenarios table
CREATE TABLE IF NOT EXISTS scenarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    scenario_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    entry_points JSON,
    system_prompt TEXT NOT NULL,
    welcome_message TEXT NOT NULL,
    fallback_responses JSON,
    max_turns INT DEFAULT 10,
    timeout_seconds INT DEFAULT 300,
    custom_settings JSON,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Gateways table
CREATE TABLE IF NOT EXISTS gateways (
    id INT AUTO_INCREMENT PRIMARY KEY,
    gateway_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    gateway_type VARCHAR(20) NOT NULL,
    profile VARCHAR(50) DEFAULT 'external',
    username VARCHAR(100),
    password VARCHAR(100),
    realm VARCHAR(100),
    proxy VARCHAR(100),
    register BOOLEAN DEFAULT FALSE,
    retry_seconds INT DEFAULT 30,
    caller_id_in_from BOOLEAN DEFAULT FALSE,
    contact_params VARCHAR(255),
    max_channels INT DEFAULT 100,
    codecs JSON DEFAULT ('["PCMU", "PCMA", "G729"]'),
    freeswitch_instances JSON,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Entry points table
CREATE TABLE IF NOT EXISTS entry_points (
    id INT AUTO_INCREMENT PRIMARY KEY,
    entry_point_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    dialplan_pattern VARCHAR(255) NOT NULL,
    scenario_id VARCHAR(100) NOT NULL,
    gateway_id VARCHAR(100),
    freeswitch_instances JSON,
    priority INT DEFAULT 100,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- FreeSWITCH configurations table
CREATE TABLE IF NOT EXISTS freeswitch_configs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    instance_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    host VARCHAR(100) NOT NULL,
    port INT DEFAULT 8021,
    password VARCHAR(100) NOT NULL,
    scenario_mapping JSON,
    gateway_ids JSON,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Outbound campaigns table
CREATE TABLE IF NOT EXISTS outbound_campaigns (
    id INT AUTO_INCREMENT PRIMARY KEY,
    campaign_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    gateway_id VARCHAR(100) NOT NULL,
    scenario_id VARCHAR(100) NOT NULL,
    data_fields JSON,
    status VARCHAR(20) DEFAULT 'draft',
    total_contacts INT DEFAULT 0,
    completed_contacts INT DEFAULT 0,
    successful_calls INT DEFAULT 0,
    failed_calls INT DEFAULT 0,
    max_concurrent_calls INT DEFAULT 10,
    call_timeout INT DEFAULT 30,
    retry_attempts INT DEFAULT 3,
    retry_interval INT DEFAULT 300,
    schedule_start DATETIME,
    schedule_end DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Outbound contacts table
CREATE TABLE IF NOT EXISTS outbound_contacts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    campaign_id VARCHAR(100) NOT NULL,
    contact_data JSON,
    phone_number VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    attempts INT DEFAULT 0,
    last_attempt DATETIME,
    next_attempt DATETIME,
    call_result VARCHAR(50),
    call_duration INT,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX idx_call_records_session_id ON call_records(session_id);
CREATE INDEX idx_call_records_status ON call_records(status);
CREATE INDEX idx_scenarios_scenario_id ON scenarios(scenario_id);
CREATE INDEX idx_scenarios_is_active ON scenarios(is_active);
CREATE INDEX idx_gateways_gateway_id ON gateways(gateway_id);
CREATE INDEX idx_gateways_is_active ON gateways(is_active);
CREATE INDEX idx_entry_points_entry_point_id ON entry_points(entry_point_id);
CREATE INDEX idx_entry_points_scenario_id ON entry_points(scenario_id);
CREATE INDEX idx_entry_points_is_active ON entry_points(is_active);
CREATE INDEX idx_freeswitch_configs_instance_id ON freeswitch_configs(instance_id);
CREATE INDEX idx_freeswitch_configs_is_active ON freeswitch_configs(is_active);
CREATE INDEX idx_outbound_campaigns_campaign_id ON outbound_campaigns(campaign_id);
CREATE INDEX idx_outbound_campaigns_status ON outbound_campaigns(status);
CREATE INDEX idx_outbound_contacts_campaign_id ON outbound_contacts(campaign_id);
CREATE INDEX idx_outbound_contacts_status ON outbound_contacts(status);
CREATE INDEX idx_outbound_contacts_phone_number ON outbound_contacts(phone_number);

-- Insert default admin user (password: admin123)
INSERT IGNORE INTO users (username, password_hash, is_admin) VALUES
('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LeCt1uB0YgLpO/lTe', TRUE);

-- Insert default scenario
INSERT IGNORE INTO scenarios (scenario_id, name, description, entry_points, system_prompt, welcome_message, fallback_responses) VALUES
('default', '默认场景', '默认AI助手场景', '["default"]', '你是专业的AI助手，请友好地回答用户的问题。', '您好，我是AI助手，请问有什么可以帮您？', '["抱歉，我暂时无法处理这个问题，请稍后再试。"]');

-- Insert default FreeSWITCH config
INSERT IGNORE INTO freeswitch_configs (instance_id, name, host, port, password, scenario_mapping, gateway_ids) VALUES
('default', '默认FreeSWITCH实例', 'localhost', 8021, 'ClueCon', '{"default": "default"}', '[]');

-- Insert sample gateway
INSERT IGNORE INTO gateways (gateway_id, name, description, gateway_type, profile, username, password, realm, proxy, register, freeswitch_instances) VALUES
('sample_gateway', '示例网关', '用于测试的示例SIP网关', 'sip', 'external', 'user', 'pass', 'sip.example.com', 'sip.example.com', FALSE, '["default"]');

-- Insert sample entry point
INSERT IGNORE INTO entry_points (entry_point_id, name, description, dialplan_pattern, scenario_id, gateway_id, freeswitch_instances, priority) VALUES
('sample_entry', '示例入口点', '用于测试的示例入口点', '^1000$', 'default', 'sample_gateway', '["default"]', 100);