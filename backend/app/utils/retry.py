"""统一重试装饰器，基于 tenacity。

重试可恢复的瞬态异常（网络/超时/限流），不重试 4xx 业务错误。
"""
import asyncio

import httpx
import openai
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

# 安全导入 grpc.RpcError（pymilvus 的底层依赖，gRPC 超时/不可用异常）
try:
    from grpc import RpcError as _GrpcError
except ImportError:
    _GrpcError = type(None)  # grpc 不可用时不会匹配任何真实异常

# 可重试异常：连接失败、超时、限流(429)、服务端错误(5xx)
# 注意：不包含 httpx.HTTPStatusError，避免重试 4xx 业务错误
RETRYABLE_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    openai.APITimeoutError,
    openai.APIConnectionError,
    openai.RateLimitError,
    openai.InternalServerError,
    asyncio.TimeoutError,
    _GrpcError,
)


def rag_retry(max_attempts: int = 3, max_wait: int = 8):
    """RAG 服务的统一重试装饰器。

    Args:
        max_attempts: 最大尝试次数（含首次）
        max_wait: 指数退避最大等待秒数
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, max=max_wait),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        reraise=True,
    )
