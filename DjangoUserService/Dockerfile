FROM python:3.12-slim-bookworm

WORKDIR /app

# 使用国内 Debian 镜像加速 (Bookworm)
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources

# 系统依赖 (mysqlclient)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_SYSTEM_PYTHON=1
ENV UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# 拷贝全部源码（setuptools 项目需要完整代码才能构建）
COPY . .

# 安装依赖（删除旧 lock，从镜像重新解析）
RUN rm -f uv.lock && uv sync --no-dev

# 启动脚本
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8001

ENTRYPOINT ["/entrypoint.sh"]
