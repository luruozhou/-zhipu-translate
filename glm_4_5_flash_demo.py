import json
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple

from zai import ZhipuAiClient


def get_client() -> ZhipuAiClient:
    """从配置文件中读取 API Key，并创建 ZhipuAiClient。"""
    config_path = Path(__file__).resolve().parent / "config.json"
    with config_path.open("r", encoding="utf-8") as f:
        config = json.load(f)

    api_key = config.get("ZHIPU_API_KEY")
    if not api_key:
        raise ValueError("config.json 中缺少 ZHIPU_API_KEY，请检查配置。")

    return ZhipuAiClient(api_key=api_key)


def translate_text(text: str, target_lang: str) -> None:
    """
    调用 GLM-4.5-Flash 模型，将用户输入翻译成指定语言。

    参数：
      - text: 原文内容
      - target_lang: 目标语言，由用户自由指定，例如：
          - 简体中文、繁体中文、英语、日语、法语等自然语言描述
          - zh / en / ja / fr 等语言代码

    要求：
      - 只输出翻译结果本身，不要额外解释。
    """
    client = get_client()

    response = client.chat.completions.create(
        model="GLM-4-Flash-250414",  # 如需更强推理可改为 "glm-4.5"
        messages=[
            {
                "role": "user",
                "content": (
                    "你是一个专业的翻译助手。"
                    f"请将我给你的文本翻译成目标语言：{target_lang}。"
                    "目标语言的描述可能是自然语言（例如“简体中文”“英语”），"
                    "也可能是语言代码（例如 zh、en、ja、fr 等），"
                    "请根据这个描述自行理解目标语言并进行翻译。"
                    "只输出翻译后的文本本身，不要任何解释或前后缀。"
                )
            },
            {
                "role": "user",
                "content": text,
            },
        ],
        thinking={"type": "disabled"},
        stream=True,
        max_tokens=2048,
        temperature=0.3,
    )

    # 流式输出翻译结果
    for chunk in response:
        delta = chunk.choices[0].delta
        if delta.content:
            print(delta.content, end="", flush=True)

    print()  # 换行


def translate_text_sync(text: str, target_lang: str) -> Tuple[bool, str, float]:
    """
    同步版本的翻译函数，用于并发测试。
    返回: (是否成功, 错误信息或结果, 耗时)
    """
    start_time = time.time()
    try:
        client = get_client()
        response = client.chat.completions.create(
            model="GLM-4-Flash-250414",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "你是一个专业的翻译助手。"
                        f"请将我给你的文本翻译成目标语言：{target_lang}。"
                        "目标语言的描述可能是自然语言（例如'简体中文''英语'），"
                        "也可能是语言代码（例如 zh、en、ja、fr 等），"
                        "请根据这个描述自行理解目标语言并进行翻译。"
                        "只输出翻译后的文本本身，不要任何解释或前后缀。"
                    )
                },
                {
                    "role": "user",
                    "content": text,
                },
            ],
            thinking={"type": "disabled"},
            stream=False,  # 并发测试时使用非流式，便于统计
            max_tokens=2048,
            temperature=0.3,
        )
        
        result = response.choices[0].message.content
        elapsed = time.time() - start_time
        return (True, result, elapsed)
    except Exception as e:
        elapsed = time.time() - start_time
        return (False, str(e), elapsed)


def test_concurrent_requests(
    text: str,
    target_lang: str,
    max_concurrent: int = 50,
    step: int = 5,
    start_concurrent: int = 1
) -> None:
    """
    测试不同并发级别的请求，找出触发接口报错的并发数。
    接口报错视为限流导致。
    
    参数:
        text: 要翻译的文本
        target_lang: 目标语言
        max_concurrent: 最大并发数
        step: 每次增加的并发数
        start_concurrent: 起始并发数
    """
    print(f"\n{'='*60}")
    print(f"开始并发测试：从 {start_concurrent} 到 {max_concurrent}，步长 {step}")
    print(f"测试文本: {text}")
    print(f"目标语言: {target_lang}")
    print(f"{'='*60}\n")
    
    current_concurrent = start_concurrent
    
    while current_concurrent <= max_concurrent:
        print(f"\n[测试并发数: {current_concurrent}]")
        print("-" * 60)
        
        success_count = 0
        fail_count = 0
        total_time = 0
        errors = []
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=current_concurrent) as executor:
            futures = [
                executor.submit(translate_text_sync, text, target_lang)
                for _ in range(current_concurrent)
            ]
            
            for future in as_completed(futures):
                success, result, elapsed = future.result()
                total_time += elapsed
                
                if success:
                    success_count += 1
                else:
                    fail_count += 1
                    errors.append(result[:150])
        
        elapsed_total = time.time() - start_time
        avg_time = total_time / current_concurrent if current_concurrent > 0 else 0
        
        print(f"成功: {success_count}/{current_concurrent}")
        print(f"失败: {fail_count}/{current_concurrent}")
        print(f"总耗时: {elapsed_total:.2f}秒")
        print(f"平均单次耗时: {avg_time:.2f}秒")
        
        if fail_count > 0:
            print(f"\n⚠️  检测到接口报错！并发数 {current_concurrent} 时出现 {fail_count} 个错误")
            if errors:
                print("\n错误示例（前3个）:")
                for err in errors[:3]:
                    print(f"  - {err}")
        
        # 如果出现错误，停止测试（视为限流）
        if fail_count > 0:
            print(f"\n{'='*60}")
            print(f"结论: 并发数 {current_concurrent} 时开始触发接口报错（限流）")
            print(f"{'='*60}\n")
            break
        
        # 等待一下再测试下一个并发级别，避免影响测试结果
        if current_concurrent < max_concurrent:
            print("\n等待 2 秒后继续下一个测试...")
            time.sleep(2)
        
        current_concurrent += step
    
    if current_concurrent > max_concurrent:
        print(f"\n{'='*60}")
        print(f"测试完成: 在并发数 {max_concurrent} 以内未触发接口报错")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    # 并发测试模式 - 参数写死
    test_concurrent_requests(
        text="今天天气不错",
        target_lang="英文",
        max_concurrent=50,
        step=5,
        start_concurrent=1
    )
