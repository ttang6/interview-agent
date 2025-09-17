import asyncio

async def start_initial_interview(session):
    opening = f"你好，我是今天的面试官，请把你最新的简历发给我。"
    print(f"\n面试官：{opening}")

    await session["resume_uploaded_event"].wait()

    opening = f"简历我已经收到了，我们正式就开始吧，你做个自我介绍吧。"
    print(f"\n面试官：{opening}")

    print("我：", end="")
    user_input = input()


if __name__ == "__main__":
    pass