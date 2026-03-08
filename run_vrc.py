from aiavatar import AIAvatar
from aiavatar.processors.chatgpt import ChatGPTProcessor
from aiavatar.speech.gptsovits import GPTSoVITSSpeechController
from aiavatar.listeners.soniox import SonioxVoiceRequestListener
from config import GOOGLE_API_KEY, SONIOX_API_KEY
from datetime import datetime
import os

# --- 音频设备配置 ---
INPUT_DEVICE = 1   # 对应 CABLE Output (听 VRChat 里的声音)
OUTPUT_DEVICE = 21  # 对应 CABLE Input (说话给 VRChat 听)

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
    model="aoba-lite:latest",  # 使用已包含角色设定的模型
    temperature=0.9,  # 设置温度参数，增加回复的随机性和创造性
    max_tokens=512,  # 设置最大生成 token 数
)

# --- 配置语音识别 ---
# 选择语音识别服务: "soniox" 或 "google"
STT_SERVICE = "soniox"  # 修改这里来切换语音识别服务

if STT_SERVICE == "soniox":
    # Soniox 语音识别
    request_listener = SonioxVoiceRequestListener(
        api_key=SONIOX_API_KEY,
        volume_threshold=-50,
        timeout=0.8,
        detection_timeout=10.0,
        lang="zh",
        rate=16000,
        device_index=INPUT_DEVICE,
        enable_speaker_diarization=True,  # 启用说话者识别
        primary_speaker_strategy="longest"  # 选择说话最多的人作为主要说话者
    )
else:
    # 使用 Google 语音识别（默认）
    request_listener = None  # AIAvatar 会自动使用 Google API

# --- 配置 TTS 语音合成 ---
# 使用 GPT-SoVITS TTS
speech_controller = GPTSoVITSSpeechController(
    base_url="http://localhost:9880",
    refer_wav_path=r"C:\Users\hyc97\models\GPT-SoVITS-v2pro-20250604-nvidia50\reference_audio\Feibi.wav",
    prompt_text="在此之前,请您务必继续享受旅居拉古那的时光。",
    prompt_language="中文",
    text_language="中文",
    device_index=OUTPUT_DEVICE
)

# --- 初始化 AIAvatar ---
app = AIAvatar(
    google_api_key=GOOGLE_API_KEY,
    chat_processor=chat_processor_deepseek,
    speech_controller=speech_controller,
    request_listener=request_listener,  # 使用配置的语音识别服务
    input_device=INPUT_DEVICE,
    language="zh-CN",  # 设置为中文
    start_voice="猫娘系统初始化完毕,青叶已上线~和我对话吧主人",  # 启动时的回应
)

# --- 设置对话结束回调，记录日志 ---
async def on_turn_end_with_logging(request_text: str, response_text: str) -> bool:
    if request_text and response_text:
        log_conversation(request_text, response_text)
    return False  # 继续监听

app.on_turn_end = on_turn_end_with_logging

# 启动 (无需唤醒词，直接开始监听)
print(f"--- 启动成功：本地 Ollama (aoba-lite) 中文模式已就绪 (始终监听模式) ---")
print(f"--- 语音识别服务: {STT_SERVICE.upper()} ---")
print(f"--- TTS 服务: GPT-SoVITS ---")
print(f"--- 对话日志保存至: {log_file_path} ---")
import asyncio
asyncio.run(app.start_chat())


# input_device=16,  # 对应 CABLE Output (听 VRChat 里的声音)
# output_device=20, # 对应 CABLE Input (说话给 VRChat 听)