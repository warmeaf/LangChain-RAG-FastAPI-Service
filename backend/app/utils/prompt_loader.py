from typing import Dict
import yaml
import os

from app.utils.config import prompt_config
from app.core.logger_handler import logger
from app.utils.path_tool import get_abstract_path, get_project_root


def load_prompt(prompt_type: str = 'main_prompt'):
    """
    加载指定类型的提示词模板

    Args:
        prompt_type: 提示词类型，对应prompt_config中的键名
            - main_prompt: 主要提示词
            - rag_summary_prompt: RAG摘要提示词
            - report_prompt: 报告提示词
            - reorder_prompt: 文档重排序提示词

    Returns:
        提示词模板内容
    """
    try:
        # 检查prompt_type是否存在于配置中
        if prompt_type not in prompt_config:
            logger.error(f"【加载提示词模板】配置中不存在 {prompt_type} 类型的提示词")
            raise KeyError(f"配置中不存在 {prompt_type} 类型的提示词")

        prompt_path = get_abstract_path(prompt_config[prompt_type])
    except Exception as e:
        logger.error(f"【加载提示词模板】加载 {prompt_config.get(prompt_type, prompt_type)} 时出错: {e}")
        raise e

    try:
        return open(prompt_path, encoding="utf-8").read()
    except Exception as e:
        logger.error(f"【加载提示词模板】读取 {prompt_path} 时出错: {e}")
        raise e


def load_system_prompts() -> Dict[str, str]:
    """加载分层系统提示词（YAML 格式）

    从 app/prompt/system_prompt.yaml 加载 base / execute / summarization 三层提示词。
    每层中的 {tools} 占位符由调用方动态注入工具描述。

    Returns:
        {"base": str, "execute": str, "summarization": str}
    """
    yaml_path = os.path.join(get_project_root(), "app", "prompt", "system_prompt.yaml")
    try:
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"【加载系统提示词】文件不存在: {yaml_path}")
        raise
    except yaml.YAMLError as e:
        logger.error(f"【加载系统提示词】YAML 解析错误: {e}")
        raise

    if not isinstance(data, dict):
        raise ValueError(f"system_prompt.yaml 格式错误：期望 dict，实际 {type(data)}")

    return {
        "base": data.get("base", "").strip(),
        "execute": data.get("execute", "").strip(),
        "summarization": data.get("summarization", "").strip(),
    }


def build_stage_prompt(stage: str, tools_xml: str) -> str:
    """构建特定阶段的完整系统提示词

    Args:
        stage: 阶段名称 (execute / summarization)
        tools_xml: 工具 XML 描述字符串

    Returns:
        完整的系统提示词（工具注入后的）
    """
    prompts = load_system_prompts()
    base = prompts.get("base", "")
    stage_prompt = prompts.get(stage, "")

    # 组合：base + 阶段特定
    combined = base + "\n\n" + stage_prompt

    # 注入工具描述
    return combined.replace("{tools}", tools_xml)


if __name__ == '__main__':
    print(load_prompt('report_prompt'))
