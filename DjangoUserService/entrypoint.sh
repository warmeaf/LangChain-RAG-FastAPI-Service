#!/bin/bash
set -e

echo "📦 运行数据库迁移..."
python manage.py makemigrations --noinput
python manage.py migrate --noinput

echo "🚀 启动 Django 服务..."
exec python manage.py runserver 0.0.0.0:8001
