from aiavatar import AIAvatar
from aiavatar.processors.chatgpt import ChatGPTProcessor
from aiavatar.speech.azurespeech import AzureSpeechController
from config import GOOGLE_API_KEY, AZURE_SPEECH_KEY, AZURE_REGION

# --- 配置本地 Ollama 处理器 ---
# 使用已经包含系统提示词的 aoba-cat 模型
chat_processor_deepseek = ChatGPTProcessor(
    api_key="ollama",  # Ollama 不需要真实 API Key，随意填写即可
    base_url="http://localhost:11434/v1",  # 本地 Ollama 服务地址
    model="aoba-cat:latest",  # 使用已包含角色设定的模型
    temperature=0.9,  # 设置温度参数，增加回复的随机性和创造性
    max_tokens=512,  # 设置最大生成 token 数
)

# --- 配置 Azure 语音合成 ---
azure_speech_controller = AzureSpeechController(
    api_key=AZURE_SPEECH_KEY,
    region=AZURE_REGION,
    speaker_name="zh-CN-XiaoxiaoNeural",  # 使用晓晓的声音
    speaker_gender="Female",
    lang="zh-CN",
    device_index=20  # 对应 CABLE Input (说话给 VRChat 听)
)

# --- 初始化 AIAvatar ---
app = AIAvatar(
    google_api_key=GOOGLE_API_KEY,
    chat_processor=chat_processor_deepseek, # 替换掉你代码里的 chat_processor_dify
    speech_controller=azure_speech_controller,  # 使用 Azure TTS
    input_device=10,  # 对应 CABLE Output (听 VRChat 里的声音)
    language="zh-CN",  # 设置为中文
    start_voice="AI青叶已上线~主人",  # 启动时的回应
)

# 启动 (无需唤醒词，直接开始监听)
print("--- 启动成功：本地 Ollama (magnum-34b) 中文模式已就绪 (始终监听模式) ---")
import asyncio
asyncio.run(app.start_chat())


# input_device=16,  # 对应 CABLE Output (听 VRChat 里的声音)
# output_device=20, # 对应 CABLE Input (说话给 VRChat 听)