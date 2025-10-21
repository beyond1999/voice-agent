import asyncio
import time

from langchain_core.messages import AIMessage,ToolMessage
# from app.codeagent.tools.file_tools import file_tools
# from app.codeagent.tools.file_saver import FileSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
# from app.codeagent.model.qwen import llm_qwen
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
# from app.codeagent.tools.shell_terminal_tools import get_stdio_shell_terminal_tools

from langchain_openai import ChatOpenAI
from pydantic import SecretStr
import base64
import json
import os
import pickle
from pathlib import Path
from typing import Sequence, Any
import shlex 
import subprocess
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple, ChannelVersions, CheckpointMetadata, \
    Checkpoint

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from langchain_community.agent_toolkits.file_management import FileManagementToolkit
import platform

file_tools = FileManagementToolkit(root_dir=r"D:\agent_learn\.temp")

@tool("execute_command", return_direct=False)
def execute_command(command: str) -> str:
    """
    执行命令行命令并返回结果。适用于需要获取系统信息、文件操作、进程查询等场景。
    
    Args:
        command: 要执行的命令字符串
    """
    try:
        os_type = platform.system()
        # 跨平台命令处理
        if os_type == "Windows":
            if command.startswith("ls"):
                command = command.replace("ls", "dir", 1)
            elif command.startswith("pwd"):
                command = "echo %cd%"
        
        # 解析命令参数
        args = shlex.split(command, posix=(os_type != "Windows"))
        print(args)
        # 执行命令
        result = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=(os_type == "Windows")
        )
        print(result)
        # 处理结果
        if result.returncode == 0:
            return f"命令执行成功:\n{result.stdout}"
        else:
            return f"命令执行失败 (返回码: {result.returncode})\n错误信息: {result.stderr}"
            
    except Exception as e:
        return f"执行命令时发生错误: {str(e)}"

llm_qwen = ChatOpenAI(
    model="qwen-max",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key=SecretStr("sk-eaae534c121f4c6da4c4c36c987ab275"),
    streaming=True,
)

async def create_mcp_stdio_client(name,params):
    config = {
        name:{
            "transport":"stdio",
            **params,
        }
    }
    print(config)
    client = MultiServerMCPClient(config)

    tools = await client.get_tools()

    return client,tools

# async  def get_stdio_shell_terminal_tools():
#     params = {
#         "command":"python",
#         'args':[
#             r"C:\Users\DELL\ai-agent-test\app\codeagent\mcp\shell_tools.py"
#         ]
#     }

#     client ,tools =await  create_mcp_stdio_client("shell_tools",params)

#     return tools

class FileSaver(BaseCheckpointSaver[str],):
    def __init__(self,base_path:str = r"D:\agent_learn\agent\checkpoint"):
        super().__init__()
        self.base_path=base_path
        os.makedirs(base_path,exist_ok=True)

    def _get_checkpoint_path(self,thread_id,checkpoint_id):
        dir_path = os.path.join(self.base_path, thread_id)
        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, checkpoint_id+".json")

        return file_path

    def _serialize_checkpoint(self,data)->str:
        pickled = pickle.dumps(data)
        return  base64.b64encode(pickled).decode()

    def _deserialize(self,data):
        decoded=base64.b64decode(data.encode())
        return pickle.loads(decoded)

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """Fetch a checkpoint tuple using the given configuration.

        Args:
            config: Configuration specifying which checkpoint to retrieve.

        Returns:
            Optional[CheckpointTuple]: The requested checkpoint tuple, or None if not found.

        Raises:
            NotImplementedError: Implement this method in your custom checkpoint saver.
        """
        # 找到正确的checkpoint文件路径
        thread_id = config["configurable"]["thread_id"]
        # checkpoint_id = config["configurable"].get("checkpoint_id")

        # 读取文件内容
        dir_path = os.path.join(self.base_path,thread_id)
        checkpoint_files = list(Path(dir_path).glob("*.json"))
        checkpoint_files.sort(key=lambda x:x.stem,reverse=True)
        if len(checkpoint_files)==0:
            return None
        latest_checkpoint = checkpoint_files[0]
        checkpoint_id=latest_checkpoint.stem
        checkpoint_file_path = self._get_checkpoint_path(thread_id,checkpoint_id)

        # 反序列化
        with open(checkpoint_file_path,"r",encoding="utf-8") as checkpoint_file:
            data = json.load(checkpoint_file)

        checkpoint = self._deserialize(data["checkpoint"])
        metadata = self._deserialize(data["metadata"])

        # 返回checkpoint对象

        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_id":checkpoint_id,
             }
            },
            checkpoint=checkpoint,
            metadata=metadata
        )

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Store a checkpoint with its configuration and metadata.

        Args:
            config: Configuration for the checkpoint.
            checkpoint: The checkpoint to store.
            metadata: Additional metadata for the checkpoint.
            new_versions: New channel versions as of this write.

        Returns:
            RunnableConfig: Updated configuration after storing the checkpoint.

        Raises:
            NotImplementedError: Implement this method in your custom checkpoint saver.
        """
        # print("put")
        #生成文件路径
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = checkpoint["id"]
        checkpoint_path = self._get_checkpoint_path(thread_id,checkpoint_id)

        #将checkpoint序列化
        checkpoint_data={
            "checkpoint":self._serialize_checkpoint(checkpoint),
            "metadata":self._serialize_checkpoint(metadata),
        }


        #将checkpoint 存储到到文件系统中
        with open(checkpoint_path,"w",encoding="utf-8") as f:
            f.write(json.dumps(checkpoint_data,indent=2,ensure_ascii=False))

        #生成返回值
        return {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_id":checkpoint_id,
        }
    }


    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Store intermediate writes linked to a checkpoint.

        Args:
            config: Configuration of the related checkpoint.
            writes: List of writes to store.
            task_id: Identifier for the task creating the writes.
            task_path: Path of the task creating the writes.

        Raises:
            NotImplementedError: Implement this method in your custom checkpoint saver.
        """
        # print("put_writes")

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """Asynchronously fetch a checkpoint tuple using the given configuration.

        Args:
            config: Configuration specifying which checkpoint to retrieve.

        Returns:
            Optional[CheckpointTuple]: The requested checkpoint tuple, or None if not found.

        Raises:
            NotImplementedError: Implement this method in your custom checkpoint saver.
        """
        return self.get_tuple(config)

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Asynchronously store a checkpoint with its configuration and metadata.

        Args:
            config: Configuration for the checkpoint.
            checkpoint: The checkpoint to store.
            metadata: Additional metadata for the checkpoint.
            new_versions: New channel versions as of this write.

        Returns:
            RunnableConfig: Updated configuration after storing the checkpoint.

        Raises:
            NotImplementedError: Implement this method in your custom checkpoint saver.
        """
        return self.put(config,checkpoint,metadata,new_versions)

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Asynchronously store intermediate writes linked to a checkpoint.

        Args:
            config: Configuration of the related checkpoint.
            writes: List of writes to store.
            task_id: Identifier for the task creating the writes.
            task_path: Path of the task creating the writes.

        Raises:
            NotImplementedError: Implement this method in your custom checkpoint saver.
        """
        return self.put_writes(config,writes,task_id,task_path)
    
from langgraph.prebuilt import create_react_agent
# from app.codeagent.model.qwen import llm_qwen
# from app.codeagent.tools.file_tools import file_tools

# if __name__=="__main__":
#     memory = FileSaver()
#     agent = create_react_agent(
#         model=llm_qwen,
#         tools=file_tools.get_tools() + [execute_command],
#         checkpointer=memory,
#         # debug=True,
#         debug=False,
#     )
#     config = RunnableConfig(configurable={
#         "thread_id": 2
#     })

#     while True:
#         user_input = input("用户：")
#         # print(user_input)
#         if (user_input.lower() == 'exit' or user_input.lower() == "quit"):
#             break
#         resp = agent.invoke(input={"messages":user_input}, config=config)
#         print("助理",resp["messages"][-1].content)

#         print()
import pyaudio
import whisper
import numpy as np
import threading

# print("PyTorch 版本:", torch.__version__)
# print("绑定的 CUDA 版本:", torch.version.cuda)  # 必须 ≥12.0
# print("CUDA 是否可用:", torch.cuda.is_available())  # 必须为 True
# print("显卡计算能力:", torch.cuda.get_device_capability(0))  # 应为 (8, 9)
# 配置音频参数（需与模型要求一致）
FORMAT = pyaudio.paInt16
CHANNELS = 1  # 单声道
RATE = 16000  # 采样率16kHz
CHUNK = 1024  # 每次读取的音频块大小

# 加载Whisper模型
# model = whisper.load_model("base", device="cuda:0")  
model = whisper.load_model("base", device="cpu")  

def record_and_transcribe(model):  # 传入whisper模型
    p = pyaudio.PyAudio()
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )

    print("开始录音...（按回车键停止）")
    frames = []
    recording = True  # 录音状态标记

    # 录音线程函数
    def record():
        nonlocal frames, recording
        while recording:
            data = stream.read(CHUNK)
            frames.append(np.frombuffer(data, dtype=np.int16))

    # 启动录音线程
    record_thread = threading.Thread(target=record)
    record_thread.start()

    # 主线程等待用户按回车
    input("请说话")  # 等待回车输入
    recording = False  # 停止录音
    record_thread.join()  # 等待录音线程结束

    # 停止流并释放资源
    stream.stop_stream()
    stream.close()
    p.terminate()

    # 处理音频并转录
    if frames:  # 确保有录音数据
        audio_data = np.concatenate(frames).astype(np.float32) / 32768.0  # 归一化
        result = model.transcribe(audio_data, fp16=False,     # 禁用半精度，确保兼容性
            without_timestamps=True  # 不需要时间戳，加快处理
            )
        print("转换结果：", result["text"])
        return result["text"]
    else:
        print("未录制到音频")
        return ""


def format_debug_output(step_name:str,content:str,is_tool_call = False)->None:
    if is_tool_call:
        print(f"工具调用{step_name}")
        print("-" * 40)
        print(content)
        print("-" * 40)
    else:
        print(f" 【{step_name}】")
        print("-" * 40)
        print(content)
        print("-" * 40)

async def run_agent():
    memory = FileSaver()

    # memory =MemorySaver()
    # shell_tools = await get_stdio_shell_terminal_tools()
    tools = file_tools.get_tools() + [execute_command]

    agent = create_react_agent(
        model=llm_qwen,
        tools=tools,
        checkpointer=memory,
        # debug=True,
        debug=False,
    )
    config = RunnableConfig(configurable={
        "thread_id": 11
    })

    while True:
        user_input = record_and_transcribe(model)
        # print(user_input)
        if (user_input.lower() == 'exit' or user_input.lower() == "quit"):
            break
        print("="*60)
        print("\n助手正在思考和处理...")


        iteration_count = 0
        start_time = time.time()
        last_tool_time = start_time

        async for chunk in agent.astream(input={"messages": user_input}, config=config):
            iteration_count += 1


            print(f"\n 第{iteration_count}步执行：")
            print("-"*30)
            print("助理:")
            items = chunk.items()
            for node_name,node_output in items:
                if "messages" in node_output:
                    for msg in node_output["messages"]:
                        if isinstance(msg,AIMessage):
                            if msg.content:
                                format_debug_output("ai思考",msg.content)
                            else:
                                for tool in msg.tool_calls:
                                    format_debug_output("调用工具",f"{tool['name']}:{tool['args']}")
                        elif isinstance(msg,ToolMessage):
                            tool_name = getattr(msg,"name","unknown")
                            tool_content = msg.content
                            # print(f"{tool_name}:{tool_content}")

                            current_time = time.time()
                            tool_duration = current_time-last_tool_time
                            last_tool_time=current_time

                            tool_result =\
                        f"""工具：{tool_name}
结果：
{tool_content}
状态：执行完成，可以开始下一个任务
执行时间：{tool_duration:.2f}秒
"""
                            format_debug_output("工具执行结果",tool_result,is_tool_call=True)
                        else:
                            format_debug_output("未实现",f"暂未实现的打印内容{chunk}")
                # print(f"{node_name}:{node_output}")

        print()

asyncio.run(run_agent())


