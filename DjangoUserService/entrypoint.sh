#!/bin/bash
set -e

echo "📦 运行数据库迁移..."
uv run python manage.py makemigrations --noinput
uv run python manage.py migrate --noinput

echo "🚀 启动 Django 服务..."
exec uv run python manage.py runserver 0.0.0.0:8001
