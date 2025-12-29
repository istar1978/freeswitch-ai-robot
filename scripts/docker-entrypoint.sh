#!/bin/bash

set -e

echo "FreeSWITCH AI Robot 容器启动脚本"

# 等待MySQL就绪
echo "等待MySQL数据库就绪..."
#while ! mysqladmin ping -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" --silent; do
#    echo "等待MySQL..."
    sleep 12
#done

echo "MySQL连接成功"

# 运行数据库初始化（如果需要）
echo "检查数据库初始化..."
python -c "
import asyncio
from storage.mysql_client import mysql_client

async def init_db():
    try:
        await mysql_client.connect()
        # 检查表是否存在，如果不存在则创建
        from sqlalchemy import text
        async with mysql_client.engine.begin() as conn:
            # 检查users表是否存在
            result = await conn.execute(text('SHOW TABLES LIKE \"users\"'))
            if not result.fetchone():
                print('初始化数据库表...')
                # 读取并执行初始化SQL
                with open('storage/init_database.sql', 'r', encoding='utf-8') as f:
                    sql = f.read()
                # 分割SQL语句并执行
                statements = [stmt.strip() for stmt in sql.split(';') if stmt.strip()]
                for stmt in statements:
                    if stmt:
                        await conn.execute(text(stmt))
                print('数据库初始化完成')
            else:
                print('数据库已初始化')
        await mysql_client.disconnect()
    except Exception as e:
        print(f'数据库初始化失败: {e}')
        raise

asyncio.run(init_db())
"

echo "数据库初始化完成"

# 启动主应用
echo "启动AI机器人应用..."
exec python main.py
