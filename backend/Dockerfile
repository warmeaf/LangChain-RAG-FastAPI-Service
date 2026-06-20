FROM python:3.12-slim-bookworm

WORKDIR /app

# 使用国内 Debian 镜像加速
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources

# 系统依赖 (pymupdf, paddleocr, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 使用系统 Python（无需 venv）
# PyPI 国内镜像加速
ENV UV_SYSTEM_PYTHON=1
ENV UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# 先拷贝依赖文件，利用 Docker 缓存层
COPY pyproject.toml uv.lock ./

# 删除旧 lock，强制从镜像重新解析
RUN rm -f uv.lock && uv sync --no-dev

# 拷贝源码
COPY . .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
