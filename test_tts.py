import azure.cognitiveservices.speech as speechsdk
from config import AZURE_SPEECH_KEY, AZURE_REGION

def generate_vrcai_voice():
    # ================= 配置区域 =================
    speech_key = AZURE_SPEECH_KEY
    service_region = AZURE_REGION 
    
    # 输出文件名
    output_filename = "vrcai_waifu_voice.wav"
    # ===========================================

    # 1. 初始化配置
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
    audio_config = speechsdk.audio.AudioOutputConfig(filename=output_filename)

    # 2. 定义 SSML 内容 (二次元调教版)
    # 这里选择了 zh-CN-XiaoxiaoNeural (晓晓)，她最温柔且支持多种情感
    # pitch="+10%" 让声音更清脆，更偏向二次元少女感
    # style="warm" 让语气听起来非常治愈、温柔
    ssml_content = f"""
    <speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' 
           xmlns:mstts='https://www.w3.org/2001/mstts' xml:lang='zh-CN'>
        <voice name='zh-CN-XiaoxiaoNeural'>
            <mstts:express-as style='warm' styledegree='1.5'>
                <prosody pitch='+12%' rate='+5%' volume='100'>
                    你好呀，主人！欢迎回到虚拟世界。
                    我是你的 AI 助手，今天也会一直陪在你身边的哦。
                </prosody>
            </mstts:express-as>
        </voice>
    </speak>
    """

    # 3. 创建合成器
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

    print(f"🚀 正在为你的二次元形象合成语音...")
    
    # 4. 执行合成 (注意这里用的是 speak_ssml_async)
    result = synthesizer.speak_ssml_async(ssml_content).get()

    # 5. 结果检查
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        print(f"✅ 合成成功！")
        print(f"📁 音频已保存至: {output_filename}")
        print(f"🎵 声音设定: 温柔治愈系 / 晓晓 / Pitch+12%")
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        print(f"❌ 合成失败: {cancellation_details.reason}")
        if cancellation_details.error_details:
            print(f"🔍 错误详情: {cancellation_details.error_details}")
            print("💡 请检查你的 API Key 是否填写正确，以及网络是否通畅。")

if __name__ == "__main__":
    generate_vrcai_voice()
