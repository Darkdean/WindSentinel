import base64
import json
import os
import sqlite3
import time
import uuid

from passlib.hash import bcrypt

DB_PATH = os.path.join(os.path.dirname(__file__), "windsentinel.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        create table if not exists users (
            username text primary key,
            password_hash text not null,
            role text not null,
            mfa_secret text,
            must_change_password integer not null default 1
        )
        """
    )
    cur.execute(
        """
        create table if not exists health_reports (
            id integer primary key autoincrement,
            agent_id text not null,
            payload text not null,
            ts integer not null
        )
        """
    )
    cur.execute(
        """
        create table if not exists client_logs (
            id integer primary key autoincrement,
            agent_id text not null,
            record text not null,
            ts integer not null
        )
        """
    )
    cur.execute(
        """
        create table if not exists policies (
            agent_id text primary key,
            payload text not null,
            ts integer not null
        )
        """
    )
    cur.execute(
        """
        create table if not exists audit_logs (
            id integer primary key autoincrement,
            username text not null,
            action text not null,
            ts integer not null,
            ip text,
            target text,
            result text,
            via_api integer not null default 0,
            user_agent text,
            method text,
            path text,
            referer text,
            query text,
            role text,
            auth_type text,
            api_endpoint_id integer
        )
        """
    )
    cur.execute(
        """
        create table if not exists agent_groups (
            id integer primary key autoincrement,
            name text unique not null,
            description text,
            created_at integer not null
        )
        """
    )
    cur.execute(
        """
        create table if not exists agent_profiles (
            agent_id text primary key,
            display_name text,
            notes text,
            group_id integer,
            updated_at integer not null
        )
        """
    )
    cur.execute(
        """
        create table if not exists agent_tags (
            id integer primary key autoincrement,
            name text unique not null,
            created_at integer not null
        )
        """
    )
    cur.execute(
        """
        create table if not exists agent_tag_map (
            agent_id text not null,
            tag_id integer not null,
            unique(agent_id, tag_id)
        )
        """
    )
    cur.execute(
        """
        create table if not exists agent_config_templates (
            name text primary key,
            config text not null,
            updated_at integer not null
        )
        """
    )
    cur.execute(
        """
        create table if not exists agent_config_template_versions (
            id integer primary key autoincrement,
            name text not null,
            config text not null,
            created_at integer not null
        )
        """
    )
    cur.execute(
        """
        create table if not exists api_endpoints (
            id integer primary key autoincrement,
            name text not null,
            alias text,
            role text not null,
            functions text not null,
            key_hash text not null,
            created_at integer not null,
            created_by text not null,
            last_used_at integer
        )
        """
    )
    cur.execute(
        """
        create table if not exists log_exports (
            id integer primary key autoincrement,
            target_type text not null,
            config text not null,
            enabled integer not null,
            created_at integer not null
        )
        """
    )
    cur.execute(
        """
        create table if not exists log_retention (
            id integer primary key check (id = 1),
            max_days integer,
            max_bytes integer,
            updated_at integer not null
        )
        """
    )
    cur.execute(
        """
        create table if not exists login_blacklist (
            id integer primary key check (id = 1),
            ip_list text,
            device_types text,
            ua_keywords text,
            browser_list text,
            os_list text,
            updated_at integer not null
        )
        """
    )
    cur.execute(
        """
        create table if not exists login_whitelist (
            id integer primary key check (id = 1),
            ip_list text,
            updated_at integer not null
        )
        """
    )
    cur.execute(
        """
        create table if not exists agent_offline_codes (
            agent_id text primary key,
            code_hash text not null,
            code_salt text not null,
            code_version integer not null,
            status text not null,
            created_at integer not null,
            rotated_at integer,
            rotated_by text
        )
        """
    )
    cur.execute(
        """
        create table if not exists agent_control_tasks (
            id integer primary key autoincrement,
            agent_id text not null,
            task_type text not null,
            status text not null,
            payload text not null,
            created_at integer not null,
            created_by text not null,
            created_role text not null,
            mfa_verified_at integer,
            expires_at integer,
            delivered_at integer,
            started_at integer,
            finished_at integer,
            result_code text,
            result_message text,
            audit_correlation_id text
        )
        """
    )
    conn.commit()
    ensure_audit_columns(conn)
    ensure_log_export_columns(conn)
    ensure_login_blacklist_columns(conn)
    ensure_login_whitelist_columns(conn)
    ensure_default_admin(conn)
    conn.close()


def ensure_audit_columns(conn):
    cur = conn.cursor()
    cur.execute("pragma table_info(audit_logs)")
    cols = {row[1] for row in cur.fetchall()}
    if "ip" not in cols:
        cur.execute("alter table audit_logs add column ip text")
    if "target" not in cols:
        cur.execute("alter table audit_logs add column target text")
    if "result" not in cols:
        cur.execute("alter table audit_logs add column result text")
    if "via_api" not in cols:
        cur.execute("alter table audit_logs add column via_api integer not null default 0")
    if "user_agent" not in cols:
        cur.execute("alter table audit_logs add column user_agent text")
    if "method" not in cols:
        cur.execute("alter table audit_logs add column method text")
    if "path" not in cols:
        cur.execute("alter table audit_logs add column path text")
    if "referer" not in cols:
        cur.execute("alter table audit_logs add column referer text")
    if "query" not in cols:
        cur.execute("alter table audit_logs add column query text")
    if "role" not in cols:
        cur.execute("alter table audit_logs add column role text")
    if "auth_type" not in cols:
        cur.execute("alter table audit_logs add column auth_type text")
    if "api_endpoint_id" not in cols:
        cur.execute("alter table audit_logs add column api_endpoint_id integer")
    if "correlation_id" not in cols:
        cur.execute("alter table audit_logs add column correlation_id text")
    conn.commit()


def ensure_log_export_columns(conn):
    cur = conn.cursor()
    cur.execute("pragma table_info(log_exports)")
    cols = {row[1] for row in cur.fetchall()}
    if "log_types" not in cols:
        cur.execute("alter table log_exports add column log_types text")
    conn.commit()


def ensure_login_blacklist_columns(conn):
    cur = conn.cursor()
    cur.execute("pragma table_info(login_blacklist)")
    cols = {row[1] for row in cur.fetchall()}
    if "ip_list" not in cols:
        cur.execute("alter table login_blacklist add column ip_list text")
    if "device_types" not in cols:
        cur.execute("alter table login_blacklist add column device_types text")
    if "ua_keywords" not in cols:
        cur.execute("alter table login_blacklist add column ua_keywords text")
    if "browser_list" not in cols:
        cur.execute("alter table login_blacklist add column browser_list text")
    if "os_list" not in cols:
        cur.execute("alter table login_blacklist add column os_list text")
    if "updated_at" not in cols:
        cur.execute("alter table login_blacklist add column updated_at integer not null default 0")
    conn.commit()


def ensure_login_whitelist_columns(conn):
    cur = conn.cursor()
    cur.execute("pragma table_info(login_whitelist)")
    cols = {row[1] for row in cur.fetchall()}
    if "ip_list" not in cols:
        cur.execute("alter table login_whitelist add column ip_list text")
    if "updated_at" not in cols:
        cur.execute("alter table login_whitelist add column updated_at integer not null default 0")
    conn.commit()


def ensure_default_admin(conn):
    cur = conn.cursor()
    cur.execute("select username from users where username = ?", ("windmap",))
    if cur.fetchone() is None:
        cur.execute(
            "insert into users (username, password_hash, role, must_change_password) values (?, ?, ?, ?)",
            ("windmap", bcrypt.hash("admin"), "admin", 1),
        )
        conn.commit()


def verify_user(username, password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("select * from users where username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    if not bcrypt.verify(password, row["password_hash"]):
        return None
    return row


def set_user_password(username, new_password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "update users set password_hash = ?, must_change_password = 0 where username = ?",
        (bcrypt.hash(new_password), username),
    )
    conn.commit()
    conn.close()


def set_user_mfa(username, secret):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("update users set mfa_secret = ? where username = ?", (secret, username))
    conn.commit()
    conn.close()


def add_user(username, password, role):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "insert into users (username, password_hash, role, must_change_password) values (?, ?, ?, ?)",
        (username, bcrypt.hash(password), role, 0),
    )
    conn.commit()
    conn.close()


def list_users():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("select username, role, mfa_secret, must_change_password from users")
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_user(username):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("delete from users where username = ?", (username,))
    conn.commit()
    conn.close()


def upsert_config_template(name, config):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "insert into agent_config_template_versions (name, config, created_at) values (?, ?, ?)",
        (name, json.dumps(config), int(time.time())),
    )
    cur.execute(
        "insert into agent_config_templates (name, config, updated_at) values (?, ?, ?) "
        "on conflict(name) do update set config = excluded.config, updated_at = excluded.updated_at",
        (name, json.dumps(config), int(time.time())),
    )
    conn.commit()
    conn.close()


def list_config_templates():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("select name, updated_at from agent_config_templates order by updated_at desc")
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_config_template(name):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("select name, config, updated_at from agent_config_templates where name = ?", (name,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    data = dict(row)
    data["config"] = json.loads(data["config"])
    return data


def delete_config_template(name):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("delete from agent_config_templates where name = ?", (name,))
    cur.execute("delete from agent_config_template_versions where name = ?", (name,))
    conn.commit()
    conn.close()


def list_config_template_versions(name, limit=50):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "select id, name, created_at from agent_config_template_versions where name = ? order by id desc limit ?",
        (name, int(limit)),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_config_template_version(name, version_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "select id, name, config, created_at from agent_config_template_versions where name = ? and id = ?",
        (name, int(version_id)),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    data = dict(row)
    data["config"] = json.loads(data["config"])
    return data


def store_health(agent_id, payload):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "insert into health_reports (agent_id, payload, ts) values (?, ?, ?)",
        (agent_id, json.dumps(payload), int(time.time())),
    )
    conn.commit()
    conn.close()


def store_log(agent_id, record):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "insert into client_logs (agent_id, record, ts) values (?, ?, ?)",
        (agent_id, json.dumps(record), int(time.time())),
    )
    conn.commit()
    conn.close()


def get_logs_sql(query):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query)
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def set_policy(agent_id, payload):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "insert into policies (agent_id, payload, ts) values (?, ?, ?) on conflict(agent_id) do update set payload=excluded.payload, ts=excluded.ts",
        (agent_id, json.dumps(payload), int(time.time())),
    )
    conn.commit()
    conn.close()


def get_policy(agent_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("select payload from policies where agent_id = ?", (agent_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return json.loads(row["payload"])


def list_agents(group_id=None, tag_id=None, q=None, offset=0, limit=200):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        select a.agent_id,
               a.last_seen,
               ap.display_name,
               ap.notes,
               ap.group_id,
               ag.name as group_name,
               tags.tags as tags,
               tags.tag_ids as tag_ids
        from (
            select agent_id, max(ts) as last_seen from (
                select agent_id, ts from health_reports
                union all
                select agent_id, ts from client_logs
                union all
                select agent_id, ts from policies
                union all
                select agent_id, updated_at as ts from agent_profiles
            ) group by agent_id
        ) a
        left join agent_profiles ap on ap.agent_id = a.agent_id
        left join agent_groups ag on ag.id = ap.group_id
        left join (
            select m.agent_id, group_concat(t.name, ",") as tags, group_concat(t.id, ",") as tag_ids
            from agent_tag_map m join agent_tags t on t.id = m.tag_id
            group by m.agent_id
        ) tags on tags.agent_id = a.agent_id
        order by a.last_seen desc
        """
    )
    rows = cur.fetchall()
    conn.close()
    result = []
    term = q.strip().lower() if q else None
    for row in rows:
        data = dict(row)
        tags = data.get("tags")
        tag_ids = data.get("tag_ids")
        data["tags"] = tags.split(",") if tags else []
        parsed_tag_ids = [int(item) for item in tag_ids.split(",")] if tag_ids else []
        if group_id is not None and data.get("group_id") != group_id:
            continue
        if tag_id is not None and tag_id not in parsed_tag_ids:
            continue
        if term:
            haystack = " ".join(
                [
                    str(data.get("agent_id") or ""),
                    str(data.get("display_name") or ""),
                    str(data.get("notes") or ""),
                    str(data.get("group_name") or ""),
                    ",".join(data.get("tags") or []),
                ]
            ).lower()
            if term not in haystack:
                continue
        data.pop("tag_ids", None)
        result.append(data)
    total = len(result)
    paged = result[offset : offset + limit]
    return {"items": paged, "total": total, "offset": offset, "limit": limit}


def get_agent_detail(agent_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        select a.agent_id,
               a.last_seen,
               ap.display_name,
               ap.notes,
               ap.group_id,
               ag.name as group_name,
               tags.tags as tags
        from (
            select agent_id, max(ts) as last_seen from (
                select agent_id, ts from health_reports
                union all
                select agent_id, ts from client_logs
                union all
                select agent_id, ts from policies
                union all
                select agent_id, updated_at as ts from agent_profiles
            ) where agent_id = ? group by agent_id
        ) a
        left join agent_profiles ap on ap.agent_id = a.agent_id
        left join agent_groups ag on ag.id = ap.group_id
        left join (
            select m.agent_id, group_concat(t.name, ",") as tags
            from agent_tag_map m join agent_tags t on t.id = m.tag_id
            group by m.agent_id
        ) tags on tags.agent_id = a.agent_id
        """,
        (agent_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    data = dict(row)
    if data.get("tags"):
        data["tags"] = data["tags"].split(",")
    else:
        data["tags"] = []
    return data


def upsert_agent_profile(agent_id, display_name=None, notes=None, group_id=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        insert into agent_profiles (agent_id, display_name, notes, group_id, updated_at)
        values (?, ?, ?, ?, ?)
        on conflict(agent_id) do update set
            display_name=excluded.display_name,
            notes=excluded.notes,
            group_id=excluded.group_id,
            updated_at=excluded.updated_at
        """,
        (agent_id, display_name, notes, group_id, int(time.time())),
    )
    conn.commit()
    conn.close()


def list_groups():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("select id, name, description from agent_groups order by id desc")
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def create_group(name, description=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "insert or ignore into agent_groups (name, description, created_at) values (?, ?, ?)",
        (name, description, int(time.time())),
    )
    cur.execute("select id from agent_groups where name = ?", (name,))
    row = cur.fetchone()
    conn.commit()
    conn.close()
    return row["id"] if row else None


def delete_group(group_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("update agent_profiles set group_id = null where group_id = ?", (group_id,))
    cur.execute("delete from agent_groups where id = ?", (group_id,))
    conn.commit()
    conn.close()


def list_tags():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("select id, name from agent_tags order by id desc")
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def create_tag(name):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "insert or ignore into agent_tags (name, created_at) values (?, ?)",
        (name, int(time.time())),
    )
    cur.execute("select id from agent_tags where name = ?", (name,))
    row = cur.fetchone()
    conn.commit()
    conn.close()
    return row["id"] if row else None


def delete_tag(tag_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("delete from agent_tag_map where tag_id = ?", (tag_id,))
    cur.execute("delete from agent_tags where id = ?", (tag_id,))
    conn.commit()
    conn.close()


def set_agent_tags(agent_id, tags):
    cleaned = [t.strip() for t in tags if t.strip()]
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("delete from agent_tag_map where agent_id = ?", (agent_id,))
    for tag in cleaned:
        cur.execute(
            "insert or ignore into agent_tags (name, created_at) values (?, ?)",
            (tag, int(time.time())),
        )
        cur.execute("select id from agent_tags where name = ?", (tag,))
        row = cur.fetchone()
        if row:
            cur.execute(
                "insert or ignore into agent_tag_map (agent_id, tag_id) values (?, ?)",
                (agent_id, row["id"]),
            )
    conn.commit()
    conn.close()


def list_agent_ids_by_group(group_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("select agent_id from agent_profiles where group_id = ?", (group_id,))
    rows = cur.fetchall()
    conn.close()
    return [row["agent_id"] for row in rows]


def list_agent_ids_by_tag(tag_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("select agent_id from agent_tag_map where tag_id = ?", (tag_id,))
    rows = cur.fetchall()
    conn.close()
    return [row["agent_id"] for row in rows]


def get_latest_health(agent_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "select payload, ts from health_reports where agent_id = ? order by ts desc limit 1",
        (agent_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {"payload": json.loads(row["payload"]), "ts": row["ts"]}


def add_audit(
    username,
    action,
    ip=None,
    target=None,
    result=None,
    via_api=False,
    user_agent=None,
    method=None,
    path=None,
    referer=None,
    query=None,
    role=None,
    auth_type=None,
    api_endpoint_id=None,
    correlation_id=None,
):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "insert into audit_logs (username, action, ts, ip, target, result, via_api, user_agent, method, path, referer, query, role, auth_type, api_endpoint_id, correlation_id) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (username, action, int(time.time()), ip, target, result, 1 if via_api else 0, user_agent, method, path, referer, query, role, auth_type, api_endpoint_id, correlation_id),
    )
    conn.commit()
    conn.close()


def list_audits(limit=200, username=None, action=None, since=None, until=None):
    conn = get_conn()
    cur = conn.cursor()
    clauses = []
    params = []
    if username:
        clauses.append("username = ?")
        params.append(username)
    if action:
        clauses.append("action like ?")
        params.append(f"%{action}%")
    if since is not None:
        clauses.append("ts >= ?")
        params.append(int(since))
    if until is not None:
        clauses.append("ts <= ?")
        params.append(int(until))
    where = f"where {' and '.join(clauses)}" if clauses else ""
    params.append(limit)
    cur.execute(
        f"select username, action, ts, ip, target, result, via_api, user_agent, method, path, referer, query, role, auth_type, api_endpoint_id, correlation_id from audit_logs {where} order by ts desc limit ?",
        params,
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def list_rules():
    rules_path = os.path.join(os.path.dirname(__file__), "rules")
    if not os.path.exists(rules_path):
        return []
    result = []
    for name in os.listdir(rules_path):
        if not name.endswith(".yar"):
            continue
        path = os.path.join(rules_path, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                result.append({"name": name, "content": f.read()})
        except Exception:
            result.append({"name": name, "content": ""})
    return result


def save_rule(name, content):
    rules_path = os.path.join(os.path.dirname(__file__), "rules")
    versions_path = os.path.join(rules_path, "versions")
    os.makedirs(rules_path, exist_ok=True)
    safe_name = name.replace("/", "_").replace("\\", "_")
    if not safe_name.endswith(".yar"):
        safe_name = safe_name + ".yar"
    path = os.path.join(rules_path, safe_name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    version_dir = os.path.join(versions_path, safe_name)
    os.makedirs(version_dir, exist_ok=True)
    version_name = f"{int(time.time())}.yar"
    version_path = os.path.join(version_dir, version_name)
    with open(version_path, "w", encoding="utf-8") as f:
        f.write(content)
    return safe_name


def list_rule_versions(name):
    rules_path = os.path.join(os.path.dirname(__file__), "rules")
    safe_name = name.replace("/", "_").replace("\\", "_")
    if not safe_name.endswith(".yar"):
        safe_name = safe_name + ".yar"
    version_dir = os.path.join(rules_path, "versions", safe_name)
    if not os.path.exists(version_dir):
        return []
    items = []
    for file_name in os.listdir(version_dir):
        if not file_name.endswith(".yar"):
            continue
        ts = file_name.replace(".yar", "")
        items.append({"version": ts, "name": file_name})
    items.sort(key=lambda x: x["version"], reverse=True)
    return items


def get_rule_version(name, version):
    rules_path = os.path.join(os.path.dirname(__file__), "rules")
    safe_name = name.replace("/", "_").replace("\\", "_")
    if not safe_name.endswith(".yar"):
        safe_name = safe_name + ".yar"
    version_file = f"{version}.yar"
    path = os.path.join(rules_path, "versions", safe_name, version_file)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def get_rule_content(name):
    rules_path = os.path.join(os.path.dirname(__file__), "rules")
    safe_name = name.replace("/", "_").replace("\\", "_")
    if not safe_name.endswith(".yar"):
        safe_name = safe_name + ".yar"
    path = os.path.join(rules_path, safe_name)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def restore_rule_version(name, version):
    content = get_rule_version(name, version)
    if content is None:
        return None
    return save_rule(name, content)


def list_audit_stats(bucket="day", username=None, action=None, since=None, until=None):
    conn = get_conn()
    cur = conn.cursor()
    clauses = []
    params = []
    if username:
        clauses.append("username = ?")
        params.append(username)
    if action:
        clauses.append("action like ?")
        params.append(f"%{action}%")
    if since is not None:
        clauses.append("ts >= ?")
        params.append(int(since))
    if until is not None:
        clauses.append("ts <= ?")
        params.append(int(until))
    where = f"where {' and '.join(clauses)}" if clauses else ""
    if bucket == "hour":
        group_expr = "strftime('%Y-%m-%d %H:00', ts, 'unixepoch')"
    else:
        group_expr = "strftime('%Y-%m-%d', ts, 'unixepoch')"
    cur.execute(
        f"select {group_expr} as bucket, count(*) as count from audit_logs {where} group by bucket order by bucket",
        params,
    )
    rows = cur.fetchall()
    cur.execute(
        f"select action, count(*) as count from audit_logs {where} group by action order by count desc",
        params,
    )
    actions = cur.fetchall()
    conn.close()
    return {
        "series": [dict(row) for row in rows],
        "actions": [dict(row) for row in actions],
    }


def upsert_agent_offline_code(agent_id, code_hash, code_salt, code_version, status, rotated_by):
    now = int(time.time())
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        insert into agent_offline_codes (agent_id, code_hash, code_salt, code_version, status, created_at, rotated_at, rotated_by)
        values (?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(agent_id) do update set
            code_hash=excluded.code_hash,
            code_salt=excluded.code_salt,
            code_version=excluded.code_version,
            status=excluded.status,
            rotated_at=excluded.rotated_at,
            rotated_by=excluded.rotated_by
        """,
        (agent_id, code_hash, code_salt, int(code_version), status, now, now, rotated_by),
    )
    conn.commit()
    conn.close()


def get_agent_offline_code(agent_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "select agent_id, code_hash, code_salt, code_version, status, created_at, rotated_at, rotated_by from agent_offline_codes where agent_id = ?",
        (agent_id,),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def create_agent_control_task(
    agent_id,
    task_type,
    payload,
    created_by,
    created_role,
    mfa_verified_at=None,
    expires_at=None,
    audit_correlation_id=None,
):
    now = int(time.time())
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        insert into agent_control_tasks (
            agent_id, task_type, status, payload, created_at, created_by, created_role,
            mfa_verified_at, expires_at, audit_correlation_id
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            agent_id,
            task_type,
            "queued",
            json.dumps(payload),
            now,
            created_by,
            created_role,
            mfa_verified_at,
            expires_at,
            audit_correlation_id,
        ),
    )
    task_id = cur.lastrowid
    conn.commit()
    conn.close()
    return task_id


def list_agent_control_tasks(agent_id, limit=50):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        select id, agent_id, task_type, status, payload, created_at, created_by, created_role,
               mfa_verified_at, expires_at, delivered_at, started_at, finished_at,
               result_code, result_message, audit_correlation_id
        from agent_control_tasks
        where agent_id = ?
        order by id desc
        limit ?
        """,
        (agent_id, int(limit)),
    )
    rows = cur.fetchall()
    conn.close()
    items = []
    for row in rows:
        data = dict(row)
        data["payload"] = json.loads(data["payload"])
        items.append(data)
    return items


def get_next_agent_control_task(agent_id):
    now = int(time.time())
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        select id, agent_id, task_type, status, payload, created_at, created_by, created_role,
               mfa_verified_at, expires_at, delivered_at, started_at, finished_at,
               result_code, result_message, audit_correlation_id
        from agent_control_tasks
        where agent_id = ?
          and status = 'queued'
          and (expires_at is null or expires_at >= ?)
        order by id asc
        limit 1
        """,
        (agent_id, now),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    task_id = row["id"]
    cur.execute(
        "update agent_control_tasks set status = 'delivered', delivered_at = ? where id = ? and status = 'queued'",
        (now, task_id),
    )
    conn.commit()
    cur.execute(
        """
        select id, agent_id, task_type, status, payload, created_at, created_by, created_role,
               mfa_verified_at, expires_at, delivered_at, started_at, finished_at,
               result_code, result_message, audit_correlation_id
        from agent_control_tasks
        where id = ?
        """,
        (task_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    data = dict(row)
    data["payload"] = json.loads(data["payload"])
    return data


def update_agent_control_task_status(task_id, status, result_code=None, result_message=None):
    now = int(time.time())
    updates = ["status = ?", "result_code = ?", "result_message = ?"]
    params = [status, result_code, result_message]
    if status == "acknowledged":
        updates.append("started_at = coalesce(started_at, ?)")
        params.append(now)
    if status in {"completed", "failed", "expired", "cancelled"}:
        updates.append("finished_at = ?")
        params.append(now)
    params.append(int(task_id))
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"update agent_control_tasks set {', '.join(updates)} where id = ?", params)
    conn.commit()
    cur.execute(
        """
        select id, agent_id, task_type, status, payload, created_at, created_by, created_role,
               mfa_verified_at, expires_at, delivered_at, started_at, finished_at,
               result_code, result_message, audit_correlation_id
        from agent_control_tasks
        where id = ?
        """,
        (int(task_id),),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    data = dict(row)
    data["payload"] = json.loads(data["payload"])
    return data


def create_api_endpoint(name, alias, role, functions, key_hash, created_by):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "insert into api_endpoints (name, alias, role, functions, key_hash, created_at, created_by) values (?, ?, ?, ?, ?, ?, ?)",
        (name, alias, role, json.dumps(functions), key_hash, int(time.time()), created_by),
    )
    endpoint_id = cur.lastrowid
    conn.commit()
    conn.close()
    return endpoint_id


def list_api_endpoints(role=None, created_by=None):
    conn = get_conn()
    cur = conn.cursor()
    clauses = []
    params = []
    if role:
        clauses.append("role = ?")
        params.append(role)
    if created_by:
        clauses.append("created_by = ?")
        params.append(created_by)
    where = f"where {' and '.join(clauses)}" if clauses else ""
    cur.execute(
        f"select id, name, alias, role, functions, created_at, created_by, last_used_at from api_endpoints {where} order by id desc",
        params,
    )
    rows = cur.fetchall()
    conn.close()
    items = []
    for row in rows:
        data = dict(row)
        data["functions"] = json.loads(data["functions"])
        items.append(data)
    return items


def delete_api_endpoint(endpoint_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("delete from api_endpoints where id = ?", (endpoint_id,))
    conn.commit()
    conn.close()


def get_api_endpoint_by_key_hash(key_hash):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "select id, name, alias, role, functions, created_by from api_endpoints where key_hash = ?",
        (key_hash,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    data = dict(row)
    data["functions"] = json.loads(data["functions"])
    return data


def get_api_endpoint(endpoint_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "select id, name, alias, role, functions, created_by from api_endpoints where id = ?",
        (endpoint_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    data = dict(row)
    data["functions"] = json.loads(data["functions"])
    return data


def update_api_endpoint_last_used(endpoint_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("update api_endpoints set last_used_at = ? where id = ?", (int(time.time()), endpoint_id))
    conn.commit()
    conn.close()


def create_log_export(target_type, config, enabled=True, log_types=None):
    conn = get_conn()
    cur = conn.cursor()
    stored_types = json.dumps(log_types or [])
    cur.execute(
        "insert into log_exports (target_type, config, enabled, created_at, log_types) values (?, ?, ?, ?, ?)",
        (target_type, json.dumps(config), 1 if enabled else 0, int(time.time()), stored_types),
    )
    export_id = cur.lastrowid
    conn.commit()
    conn.close()
    return export_id


def list_log_exports():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("select id, target_type, config, enabled, created_at, log_types from log_exports order by id desc")
    rows = cur.fetchall()
    conn.close()
    items = []
    for row in rows:
        data = dict(row)
        data["config"] = json.loads(data["config"])
        log_types = data.get("log_types")
        if log_types:
            data["log_types"] = json.loads(log_types)
        else:
            data["log_types"] = ["health", "client_logs", "audit"]
        items.append(data)
    return items


def delete_log_export(export_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("delete from log_exports where id = ?", (export_id,))
    conn.commit()
    conn.close()


def set_log_export_enabled(export_id, enabled):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("update log_exports set enabled = ? where id = ?", (1 if enabled else 0, export_id))
    conn.commit()
    conn.close()


def set_log_retention(max_days=None, max_bytes=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "insert into log_retention (id, max_days, max_bytes, updated_at) values (1, ?, ?, ?) "
        "on conflict(id) do update set max_days = excluded.max_days, max_bytes = excluded.max_bytes, updated_at = excluded.updated_at",
        (max_days, max_bytes, int(time.time())),
    )
    conn.commit()
    conn.close()


def get_log_retention():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("select max_days, max_bytes, updated_at from log_retention where id = 1")
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else {"max_days": None, "max_bytes": None, "updated_at": None}


def set_login_blacklist(ip_list=None, device_types=None, ua_keywords=None, browser_list=None, os_list=None):
    conn = get_conn()
    cur = conn.cursor()
    ip_value = json.dumps(ip_list or [])
    device_value = json.dumps(device_types or [])
    ua_value = json.dumps(ua_keywords or [])
    browser_value = json.dumps(browser_list or [])
    os_value = json.dumps(os_list or [])
    cur.execute(
        "insert into login_blacklist (id, ip_list, device_types, ua_keywords, browser_list, os_list, updated_at) values (1, ?, ?, ?, ?, ?, ?) "
        "on conflict(id) do update set ip_list = excluded.ip_list, device_types = excluded.device_types, ua_keywords = excluded.ua_keywords, browser_list = excluded.browser_list, os_list = excluded.os_list, updated_at = excluded.updated_at",
        (ip_value, device_value, ua_value, browser_value, os_value, int(time.time())),
    )
    conn.commit()
    conn.close()


def get_login_blacklist():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("select ip_list, device_types, ua_keywords, browser_list, os_list, updated_at from login_blacklist where id = 1")
    row = cur.fetchone()
    conn.close()
    if not row:
        return {"ip_list": [], "device_types": [], "ua_keywords": [], "browser_list": [], "os_list": [], "updated_at": None}
    data = dict(row)
    data["ip_list"] = json.loads(data.get("ip_list") or "[]")
    data["device_types"] = json.loads(data.get("device_types") or "[]")
    data["ua_keywords"] = json.loads(data.get("ua_keywords") or "[]")
    data["browser_list"] = json.loads(data.get("browser_list") or "[]")
    data["os_list"] = json.loads(data.get("os_list") or "[]")
    return data


def set_login_whitelist(ip_list=None):
    conn = get_conn()
    cur = conn.cursor()
    ip_value = json.dumps(ip_list or [])
    cur.execute(
        "insert into login_whitelist (id, ip_list, updated_at) values (1, ?, ?) "
        "on conflict(id) do update set ip_list = excluded.ip_list, updated_at = excluded.updated_at",
        (ip_value, int(time.time())),
    )
    conn.commit()
    conn.close()


def get_login_whitelist():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("select ip_list, updated_at from login_whitelist where id = 1")
    row = cur.fetchone()
    conn.close()
    if not row:
        return {"ip_list": [], "updated_at": None}
    data = dict(row)
    data["ip_list"] = json.loads(data.get("ip_list") or "[]")
    return data


def purge_logs_older_than(cutoff_ts):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("delete from client_logs where ts < ?", (int(cutoff_ts),))
    cur.execute("delete from health_reports where ts < ?", (int(cutoff_ts),))
    conn.commit()
    conn.close()


def purge_logs_by_size(max_bytes):
    if max_bytes is None:
        return
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("select sum(length(record)) as total from client_logs")
    row = cur.fetchone()
    total_logs = row["total"] or 0
    cur.execute("select sum(length(payload)) as total from health_reports")
    row = cur.fetchone()
    total_health = row["total"] or 0
    total = total_logs + total_health
    if total <= max_bytes:
        conn.close()
        return
    cur.execute("select id, ts, length(record) as size from client_logs order by ts asc")
    rows = cur.fetchall()
    for row in rows:
        if total <= max_bytes:
            break
        cur.execute("delete from client_logs where id = ?", (row["id"],))
        total -= row["size"] or 0
    cur.execute("select id, ts, length(payload) as size from health_reports order by ts asc")
    rows = cur.fetchall()
    for row in rows:
        if total <= max_bytes:
            break
        cur.execute("delete from health_reports where id = ?", (row["id"],))
        total -= row["size"] or 0
    conn.commit()
    conn.close()


def generate_token():
    return base64.urlsafe_b64encode(uuid.uuid4().bytes).decode().rstrip("=")
