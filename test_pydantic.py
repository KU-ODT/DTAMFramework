from typing import Optional, Dict, Any, Type
import dataclasses
from pydantic import BaseModel, create_model, Field
from fastapi import FastAPI
from pydantic.dataclasses import dataclass as pydantic_dataclass

@dataclasses.dataclass
class Msg1001:
    timestamp: str = ""
    operationMode: str = "single"

app = FastAPI()

def create_model_for_msg(msg_id: str, icd_cls: Type):
    return create_model(
        f"PushRequest_{msg_id}",
        role=(Optional[str], Field(default="")),
        payload=(icd_cls, Field(...))
    )

Model1001 = create_model_for_msg("1001", Msg1001)

@app.post("/api/msg/1001")
async def handle(body: Model1001):
    return {"role": body.role, "payload": dataclasses.asdict(body.payload)}

import uvicorn
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8111)
