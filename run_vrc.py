from aiavatar import AIAvatar
from aiavatar.processors.chatgpt import ChatGPTProcessor
from aiavatar.speech.azurespeech import AzureSpeechController
from aiavatar.speech.fishaudio import FishAudioSpeechController
from config import GOOGLE_API_KEY, AZURE_SPEECH_KEY, AZURE_REGION, FISH_AUDIO_API_KEY, FISH_AUDIO_MODEL
from datetime import datetime
import os

# --- 创建日志目录和文件 ---
log_dir = os.path.join(os.path.dirname(__file__), 'chat_logs')
os.makedirs(log_dir, exist_ok=True)

start_time = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file_path = os.path.join(log_dir, f"chat_log_{start_time}.txt")

def log_conversation(user_input: str, ai_response: str):
    """记录对话到日志文件"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file_path, 'a', encoding='utf-8') as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"[{timestamp}]\n")
        f.write(f"User: {user_input}\n")
        f.write(f"AI: {ai_response}\n")

# --- 配置本地 Ollama 处理器 ---
# 使用已经包含系统提示词的 aoba-cat 模型
chat_processor_deepseek = ChatGPTProcessor(
    api_key="ollama",  # Ollama 不需要真实 API Key，随意填写即可
    base_url="http://localhost:11434/v1",  # 本地 Ollama 服务地址
    model="aoba-cat:latest",  # 使用已包含角色设定的模型
    temperature=0.9,  # 设置温度参数，增加回复的随机性和创造性
    max_tokens=512,  # 设置最大生成 token 数
)

# --- 配置 TTS 语音合成 ---
# 选择 TTS 服务: "azure" 或 "fishaudio"
TTS_SERVICE = "azure"  # 修改这里来切换 TTS 服务

if TTS_SERVICE == "azure":
    # Azure TTS
    speech_controller = AzureSpeechController(
        api_key=AZURE_SPEECH_KEY,
        region=AZURE_REGION,
        speaker_name="zh-CN-XiaoxiaoNeural",  # 使用晓晓的声音
        speaker_gender="Female",
        lang="zh-CN",
        device_index=21  # 对应 CABLE Input (说话给 VRChat 听)
    )
elif TTS_SERVICE == "fishaudio":
    # Fish Audio TTS
    speech_controller = FishAudioSpeechController(
        api_key=FISH_AUDIO_API_KEY,
        model=FISH_AUDIO_MODEL,
        device_index=21  # 对应 CABLE Input (说话给 VRChat 听)
    )
else:
    raise ValueError(f"Unknown TTS service: {TTS_SERVICE}")

# --- 初始化 AIAvatar ---
app = AIAvatar(
    google_api_key=GOOGLE_API_KEY,
    chat_processor=chat_processor_deepseek, # 替换掉你代码里的 chat_processor_dify
    speech_controller=speech_controller,  # 使用配置的 TTS 服务
    input_device=1,  # 对应 CABLE Output (听 VRChat 里的声音)
    language="zh-CN",  # 设置为中文
    start_voice="AI青叶已上线~主人",  # 启动时的回应
)

# --- 设置对话结束回调，记录日志 ---
async def on_turn_end_with_logging(request_text: str, response_text: str) -> bool:
    if request_text and response_text:
        log_conversation(request_text, response_text)
    return False  # 继续监听

app.on_turn_end = on_turn_end_with_logging

# 启动 (无需唤醒词，直接开始监听)
print(f"--- 启动成功：本地 Ollama (aoba-cat) 中文模式已就绪 (始终监听模式) ---")
print(f"--- TTS 服务: {TTS_SERVICE.upper()} ---")
print(f"--- 对话日志保存至: {log_file_path} ---")
import asyncio
asyncio.run(app.start_chat())


# input_device=16,  # 对应 CABLE Output (听 VRChat 里的声音)
# output_device=20, # 对应 CABLE Input (说话给 VRChat 听)