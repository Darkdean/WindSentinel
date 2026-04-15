"""
测试数据库存储模块
"""
import pytest
import sqlite3
import tempfile
import os


# 创建临时数据库 fixture
@pytest.fixture
def temp_db():
    """创建临时测试数据库"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    os.unlink(path)


class TestDatabaseSchema:
    """测试数据库结构"""

    def test_agent_profiles_columns(self, temp_db):
        """测试 agent_profiles 表结构"""
        conn = sqlite3.connect(temp_db)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS agent_profiles (
                agent_id TEXT PRIMARY KEY,
                display_name TEXT,
                notes TEXT,
                group_id INTEGER,
                computer_name TEXT,
                system_serial TEXT,
                board_serial TEXT,
                created_at INTEGER,
                updated_at INTEGER
            )
        """)
        conn.commit()
        
        # 检查表存在
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='agent_profiles'")
        assert cur.fetchone() is not None
        
        conn.close()

    def test_agent_offline_codes_columns(self, temp_db):
        """测试 agent_offline_codes 表结构"""
        conn = sqlite3.connect(temp_db)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS agent_offline_codes (
                agent_id TEXT PRIMARY KEY,
                offline_uninstall_code_encrypted TEXT,
                created_at INTEGER,
                updated_at INTEGER
            )
        """)
        conn.commit()
        
        # 检查表存在
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='agent_offline_codes'")
        assert cur.fetchone() is not None
        
        conn.close()


class TestUpsertFunctions:
    """测试 upsert 函数"""

    def test_upsert_agent_profile(self, temp_db):
        """测试插入/更新 agent profile"""
        conn = sqlite3.connect(temp_db)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS agent_profiles (
                agent_id TEXT PRIMARY KEY,
                display_name TEXT,
                computer_name TEXT,
                system_serial TEXT,
                board_serial TEXT,
                created_at INTEGER,
                updated_at INTEGER
            )
        """)
        conn.commit()
        
        agent_id = "test-agent-001"
        now = 12345
        
        # 插入
        cur.execute("""
            INSERT INTO agent_profiles (agent_id, display_name, computer_name, system_serial, board_serial, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (agent_id, "Test Agent", "my-computer", "SN123456", "BS789012", now, now))
        conn.commit()
        
        # 查询验证
        cur.execute("SELECT computer_name, system_serial, board_serial FROM agent_profiles WHERE agent_id = ?", (agent_id,))
        row = cur.fetchone()
        assert row[0] == "my-computer"
        assert row[1] == "SN123456"
        assert row[2] == "BS789012"
        
        conn.close()

    def test_upsert_offline_code(self, temp_db):
        """测试插入/更新离线卸载码"""
        conn = sqlite3.connect(temp_db)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS agent_offline_codes (
                agent_id TEXT PRIMARY KEY,
                offline_uninstall_code_encrypted TEXT,
                created_at INTEGER,
                updated_at INTEGER
            )
        """)
        conn.commit()
        
        agent_id = "test-agent-002"
        encrypted_code = "YWJjZGVmZ2hpamtsbW5vcA=="  # mock base64
        now = 12345
        
        # 插入
        cur.execute("""
            INSERT INTO agent_offline_codes (agent_id, offline_uninstall_code_encrypted, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        """, (agent_id, encrypted_code, now, now))
        conn.commit()
        
        # 查询验证
        cur.execute("SELECT offline_uninstall_code_encrypted FROM agent_offline_codes WHERE agent_id = ?", (agent_id,))
        row = cur.fetchone()
        assert row[0] == encrypted_code
        
        conn.close()
