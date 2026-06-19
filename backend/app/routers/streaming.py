"""WebSocket 流式通信路由"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.database import SessionLocal
from app.llm.router import get_active_provider
from app.llm import ChatMessage

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 通用聊天通道"""
    await websocket.accept()

    db = SessionLocal()
    try:
        while True:
            data = await websocket.receive_json()

            msg_type = data.get("type", "chat")
            if msg_type == "chat":
                messages_data = data.get("messages", [])
                provider_id = data.get("provider_id")

                # 获取 Provider
                if provider_id:
                    from app.llm.router import get_provider_by_id
                    result = get_provider_by_id(provider_id, db)
                else:
                    result = get_active_provider(db)

                if not result:
                    await websocket.send_json({
                        "type": "error",
                        "message": "No active LLM provider configured",
                    })
                    continue

                provider_impl, config = result

                # 转换消息格式
                messages = [
                    ChatMessage(role=m["role"], content=m["content"])
                    for m in messages_data
                ]

                try:
                    async for token in provider_impl.chat_stream(messages, config):
                        await websocket.send_json({
                            "type": "chunk",
                            "content": token,
                        })
                    await websocket.send_json({"type": "done"})
                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e),
                    })

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    finally:
        db.close()
