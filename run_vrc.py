from aiavatar import AIAvatar
from aiavatar.processors.chatgpt import ChatGPTProcessor
from config import GOOGLE_API_KEY, DEEPSEEK_API_KEY

# --- 关键：配置 DeepSeek 处理器 ---
# 我们利用 ChatGPTProcessor，但把地址指向 DeepSeek
chat_processor_deepseek = ChatGPTProcessor(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1",  # 强制指向 DeepSeek 服务器
    model="deepseek-chat"                   # 使用 DeepSeek 模型
)

# --- 初始化 AIAvatar ---
app = AIAvatar(
    google_api_key=GOOGLE_API_KEY,
    chat_processor=chat_processor_deepseek, # 替换掉你代码里的 chat_processor_dify
    voicevox_speaker_id=23,                  # 冥鳴ひまり (你之前选的 54)
    input_device=16,  # 对应 CABLE Output (听 VRChat 里的声音)
    output_device=20, # 对应 CABLE Input (说话给 VRChat 听)
)

# 启动 (默认唤醒词是 "こんにちは")
print("--- 启动成功：DeepSeek 模式已就绪 ---")
app.start_listening_wakeword()


# input_device=16,  # 对应 CABLE Output (听 VRChat 里的声音)
# output_device=20, # 对应 CABLE Input (说话给 VRChat 听)