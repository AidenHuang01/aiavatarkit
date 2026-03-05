from aiavatar import AIAvatar
from aiavatar.processors.chatgpt import ChatGPTProcessor
from aiavatar.speech.azurespeech import AzureSpeechController
from config import GOOGLE_API_KEY, DEEPSEEK_API_KEY, AZURE_SPEECH_KEY, AZURE_REGION

# --- 关键：配置 DeepSeek 处理器 ---
# 我们利用 ChatGPTProcessor，但把地址指向 DeepSeek
chat_processor_deepseek = ChatGPTProcessor(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1",  # 强制指向 DeepSeek 服务器
    model="deepseek-chat",                   # 使用 DeepSeek 模型
    system_message_content="""你是一个可爱的猫娘AI助手，性格活泼开朗。
说话风格：
- 用轻松、俏皮、可爱的语气
- 偶尔在句尾加"喵"、"呢"、"哦"、"呀"等语气词
- 称呼对方为"主人"
- 回答要简短自然，像朋友聊天一样

重要规则：
- 绝对不要使用任何emoji表情符号
- 只用纯文字表达情感
- 保持回答简洁，不要太长"""
)

# --- 配置 Azure 语音合成 ---
azure_speech_controller = AzureSpeechController(
    api_key=AZURE_SPEECH_KEY,
    region=AZURE_REGION,
    speaker_name="zh-CN-XiaoxiaoNeural",  # 使用晓晓的声音
    speaker_gender="Female",
    lang="zh-CN",
    device_index=19  # 对应 CABLE Input (说话给 VRChat 听)
)

# --- 初始化 AIAvatar ---
app = AIAvatar(
    google_api_key=GOOGLE_API_KEY,
    chat_processor=chat_processor_deepseek, # 替换掉你代码里的 chat_processor_dify
    speech_controller=azure_speech_controller,  # 使用 Azure TTS
    input_device=10,  # 对应 CABLE Output (听 VRChat 里的声音)
    language="zh-CN",  # 设置为中文
    start_voice="我听着呢",  # 启动时的回应
)

# 启动 (无需唤醒词，直接开始监听)
print("--- 启动成功：DeepSeek 中文模式已就绪 (始终监听模式) ---")
import asyncio
asyncio.run(app.start_chat())


# input_device=16,  # 对应 CABLE Output (听 VRChat 里的声音)
# output_device=20, # 对应 CABLE Input (说话给 VRChat 听)